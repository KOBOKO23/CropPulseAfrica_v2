# apps/banks/services/billing_service.py

import calendar
import logging
from decimal import Decimal
from datetime import date, timedelta

from django.db.models import Sum
from django.utils import timezone

from ..models import (
    Bank, BillingRecord, UsageLog,
    TIER_BASIC, TIER_PRO, TIER_ENTERPRISE, TIER_LIMITS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pricing  (KES) — single source of truth.
#
# base_fee          flat monthly charge
# overage_per_1000  charged per 1 000 calls above the tier's monthly allowance
# ---------------------------------------------------------------------------
TIER_PRICING = {
    TIER_BASIC: {
        'base_fee':          Decimal('5_000.00'),
        'overage_per_1000':  Decimal('500.00'),
    },
    TIER_PRO: {
        'base_fee':          Decimal('15_000.00'),
        'overage_per_1000':  Decimal('350.00'),
    },
    TIER_ENTERPRISE: {
        'base_fee':          Decimal('50_000.00'),
        'overage_per_1000':  Decimal('200.00'),
    },
}


class BillingService:
    """
    All billing logic.  Typical entry-point is a Celery task that runs
    on the 1st of every month::

        BillingService.generate_monthly_invoice(bank)
    """

    # ------------------------------------------------------------------
    # generate
    # ------------------------------------------------------------------
    @staticmethod
    def generate_monthly_invoice(
        bank: Bank,
        billing_month: date | None = None,
    ) -> BillingRecord:
        """
        Aggregate UsageLog for *billing_month*, compute fees, upsert a
        BillingRecord.

        ``billing_month`` defaults to **last** calendar month so the
        task can run safely on the 1st without worrying about the
        current month being incomplete.
        """
        if billing_month is None:
            first_this = timezone.now().date().replace(day=1)
            billing_month = (first_this - timedelta(days=1)).replace(day=1)

        year, month      = billing_month.year, billing_month.month
        days_in_month    = calendar.monthrange(year, month)[1]

        # --- total calls --------------------------------------------------
        agg            = (
            UsageLog.objects
            .filter(bank=bank, date__year=year, date__month=month)
            .aggregate(total=Sum('api_calls'))
        )
        total_api_calls = agg['total'] or 0

        # --- allowed calls = daily_limit × days ---------------------------
        tier           = bank.subscription_tier
        daily_limit    = TIER_LIMITS.get(tier, TIER_LIMITS[TIER_BASIC])['api_calls_per_day']
        monthly_allow  = daily_limit * days_in_month
        overage_calls  = max(0, total_api_calls - monthly_allow)

        # --- fee ----------------------------------------------------------
        pricing        = TIER_PRICING.get(tier, TIER_PRICING[TIER_BASIC])
        base_amount    = pricing['base_fee']
        overage_amount = (Decimal(overage_calls) / Decimal(1_000)) * pricing['overage_per_1000']
        total_amount   = base_amount + overage_amount

        # --- upsert -------------------------------------------------------
        record, created = BillingRecord.objects.update_or_create(
            bank          = bank,
            billing_month = billing_month,
            defaults={
                'subscription_tier': tier,
                'total_api_calls':   total_api_calls,
                'overage_calls':     overage_calls,
                'base_amount':       base_amount,
                'overage_amount':    overage_amount,
                'total_amount':      total_amount,
                'status':            BillingRecord.STATUS_DRAFT,
            },
        )

        logger.info(
            '%s billing record for %s – %d-%02d  (calls=%d, total=KES %.2f)',
            'Created' if created else 'Updated',
            bank.bank_id, year, month, total_api_calls, total_amount,
        )
        return record

    # ------------------------------------------------------------------
    # status transitions
    # ------------------------------------------------------------------
    @staticmethod
    def issue_invoice(record: BillingRecord) -> BillingRecord:
        """Draft → Issued."""
        if record.status != BillingRecord.STATUS_DRAFT:
            raise ValueError(f"Cannot issue a record in '{record.status}' status.")
        record.status   = BillingRecord.STATUS_ISSUED
        record.issued_at = timezone.now()
        record.save(update_fields=['status', 'issued_at', 'updated_at'])
        logger.info('Issued invoice %s – %s', record.bank.bank_id, record.billing_month)
        return record

    @staticmethod
    def mark_paid(record: BillingRecord, notes: str = '') -> BillingRecord:
        """Issued | Overdue → Paid."""
        if record.status not in (BillingRecord.STATUS_ISSUED, BillingRecord.STATUS_OVERDUE):
            raise ValueError(f"Cannot mark '{record.status}' as paid.")
        record.status  = BillingRecord.STATUS_PAID
        record.paid_at = timezone.now()
        if notes:
            record.notes = notes
        record.save(update_fields=['status', 'paid_at', 'notes', 'updated_at'])
        logger.info('Marked invoice paid %s – %s', record.bank.bank_id, record.billing_month)
        return record

    @staticmethod
    def mark_overdue(record: BillingRecord) -> BillingRecord:
        """Issued → Overdue."""
        if record.status != BillingRecord.STATUS_ISSUED:
            raise ValueError(f"Cannot mark '{record.status}' as overdue.")
        record.status = BillingRecord.STATUS_OVERDUE
        record.save(update_fields=['status', 'updated_at'])
        logger.info('Marked invoice overdue %s – %s', record.bank.bank_id, record.billing_month)
        return record

    # ------------------------------------------------------------------
    # bulk helpers  (Celery beat)
    # ------------------------------------------------------------------
    @staticmethod
    def generate_all_pending_invoices() -> int:
        """
        Generate last-month invoices for every active bank that doesn't
        have one yet.  Idempotent (update_or_create).
        """
        first_this   = timezone.now().date().replace(day=1)
        last_month   = (first_this - timedelta(days=1)).replace(day=1)
        generated    = 0

        for bank in Bank.objects.filter(is_active=True):
            try:
                BillingService.generate_monthly_invoice(bank, billing_month=last_month)
                generated += 1
            except Exception as exc:                          # pragma: no cover
                logger.error('Invoice gen failed for %s: %s', bank.bank_id, exc)

        logger.info('Generated invoices for %d bank(s)', generated)
        return generated

    @staticmethod
    def flag_overdue_invoices(days_overdue: int = 30) -> int:
        """Move any ISSUED invoice older than *days_overdue* to OVERDUE."""
        cutoff = timezone.now() - timedelta(days=days_overdue)
        count  = 0
        for rec in BillingRecord.objects.filter(
            status=BillingRecord.STATUS_ISSUED,
            issued_at__lt=cutoff,
        ):
            BillingService.mark_overdue(rec)
            count += 1
        logger.info('Flagged %d invoice(s) as overdue', count)
        return count