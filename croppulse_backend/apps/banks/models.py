# apps/banks/models.py
# ---------------------------------------------------------------------------
# All bank-tenant models.  Dependency order: Bank first, then every table
# that FKs into it.
# ---------------------------------------------------------------------------

import hashlib
import secrets
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils import timezone

from apps.accounts.models import User


# ===========================================================================
# Subscription-tier constants  ← single source of truth for the whole project
# ===========================================================================

TIER_BASIC      = 'basic'
TIER_PRO        = 'pro'
TIER_ENTERPRISE = 'enterprise'

SUBSCRIPTION_TIERS = (
    (TIER_BASIC,      'Basic'),
    (TIER_PRO,        'Pro'),
    (TIER_ENTERPRISE, 'Enterprise'),
)

TIER_LIMITS = {
    TIER_BASIC: {
        'api_calls_per_day': 500,
        'max_api_keys':      3,
        'max_webhooks':      0,
        'satellite_access':  False,
        'full_reports':      False,
    },
    TIER_PRO: {
        'api_calls_per_day': 2_000,
        'max_api_keys':      10,
        'max_webhooks':      5,
        'satellite_access':  True,
        'full_reports':      True,
    },
    TIER_ENTERPRISE: {
        'api_calls_per_day': 10_000,
        'max_api_keys':      50,
        'max_webhooks':      20,
        'satellite_access':  True,
        'full_reports':      True,
    },
}


# ===========================================================================
# Bank
# ===========================================================================

class Bank(models.Model):
    """Top-level tenant.  Every other banks-app model FKs here."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='bank_profile',
    )
    bank_id = models.CharField(max_length=50, unique=True, db_index=True)

    # --- Institution details -------------------------------------------------
    name                = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=100)
    contact_email       = models.EmailField(blank=True, default='')
    contact_phone       = models.CharField(max_length=20, blank=True, default='')

    # --- Subscription ---------------------------------------------------------
    subscription_tier = models.CharField(
        max_length=50,
        choices=SUBSCRIPTION_TIERS,
        default=TIER_BASIC,
    )
    is_active = models.BooleanField(default=True)

    # --- Timestamps -----------------------------------------------------------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table  = 'banks'
        ordering  = ['-created_at']

    def __str__(self):
        return f'{self.bank_id} – {self.name}'

    # --- helpers consumed by services / views / serializers -------------------
    @property
    def tier_limits(self) -> dict:
        return TIER_LIMITS.get(self.subscription_tier, TIER_LIMITS[TIER_BASIC])

    @property
    def daily_api_limit(self) -> int:
        return self.tier_limits['api_calls_per_day']

    @property
    def max_webhooks(self) -> int:
        return self.tier_limits['max_webhooks']

    @property
    def max_api_keys(self) -> int:
        return self.tier_limits['max_api_keys']

    def active_webhook_count(self) -> int:
        return self.webhooks.filter(is_active=True).count()

    def active_api_key_count(self) -> int:
        return self.api_keys.filter(status='active').count()


# ===========================================================================
# APIKey
# ===========================================================================

class APIKey(models.Model):
    """
    Hashed API credential.  Raw token is shown once at creation; only
    the SHA-256 digest is persisted.  ``key_prefix`` lets the owner
    recognise which key is which without knowing the full value.
    """

    STATUS_ACTIVE   = 'active'
    STATUS_REVOKED  = 'revoked'
    STATUS_EXPIRED  = 'expired'
    STATUS_CHOICES  = (
        (STATUS_ACTIVE,  'Active'),
        (STATUS_REVOKED, 'Revoked'),
        (STATUS_EXPIRED, 'Expired'),
    )

    PERMISSION_CHOICES = (
        ('read_farmers',    'Read Farmers'),
        ('read_farms',      'Read Farms'),
        ('read_satellite',  'Read Satellite Data'),
        ('read_loans',      'Read Loans'),
        ('write_loans',     'Write Loans'),
        ('read_compliance', 'Read Compliance'),
        ('read_analytics',  'Read Analytics'),
        ('manage_webhooks', 'Manage Webhooks'),
    )

    bank        = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name='api_keys')
    name        = models.CharField(max_length=100)
    key_prefix  = models.CharField(max_length=8,  editable=False)
    key_hash    = models.CharField(max_length=64, unique=True, editable=False)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    permissions = models.JSONField(default=list)   # list of permission strings

    created_at   = models.DateTimeField(auto_now_add=True)
    expires_at   = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at   = models.DateTimeField(null=True, blank=True)
    revoked_by   = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='revoked_api_keys',
    )

    class Meta:
        db_table  = 'api_keys'
        ordering  = ['-created_at']
        indexes   = [
            models.Index(fields=['key_hash']),
            models.Index(fields=['bank', '-created_at']),
            models.Index(fields=['status', 'expires_at']),
        ]

    def __str__(self):
        return f'{self.bank.bank_id} – {self.name} ({self.key_prefix}…)'

    def clean(self):
        valid = {c[0] for c in self.PERMISSION_CHOICES}
        bad   = set(self.permissions) - valid
        if bad:
            raise ValidationError({'permissions': f'Unknown permissions: {bad}'})

    @property
    def is_active(self) -> bool:
        if self.status != self.STATUS_ACTIVE:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True

    def has_permission(self, perm: str) -> bool:
        return perm in self.permissions


# ===========================================================================
# Webhook
# ===========================================================================

class Webhook(models.Model):
    """Outbound endpoint; payloads are HMAC-SHA256 signed."""

    EVENT_TYPES = (
        ('scan.completed',            'Satellite Scan Completed'),
        ('scan.failed',               'Satellite Scan Failed'),
        ('loan.approved',             'Loan Approved'),
        ('loan.rejected',             'Loan Rejected'),
        ('loan.repayment',            'Loan Repayment Received'),
        ('farmer.registered',         'Farmer Registered'),
        ('farm.verified',             'Farm Verified'),
        ('compliance.report_ready',   'Compliance Report Ready'),
        ('alert.crop_health',         'Crop Health Alert'),
        ('alert.fraud',               'Fraud Alert'),
        ('billing.invoice_generated', 'Invoice Generated'),
    )

    bank                = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name='webhooks')
    name                = models.CharField(max_length=100)
    url                 = models.URLField(max_length=500)
    signing_secret_hash = models.CharField(max_length=64, editable=False)
    secret_prefix       = models.CharField(max_length=8,  editable=False)
    subscribed_events   = models.JSONField(default=list)   # empty == all
    is_active           = models.BooleanField(default=True)
    max_retries         = models.IntegerField(default=3,  validators=[MinValueValidator(0)])
    timeout_seconds     = models.IntegerField(default=10, validators=[MinValueValidator(1)])

    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        db_table  = 'webhooks'
        ordering  = ['-created_at']
        indexes   = [models.Index(fields=['bank', 'is_active'])]

    def __str__(self):
        return f'{self.bank.bank_id} – {self.name}'

    def clean(self):
        if not self.url.startswith('https://'):
            raise ValidationError({'url': 'Webhook URLs must use HTTPS.'})

        valid = {e[0] for e in self.EVENT_TYPES}
        bad   = set(self.subscribed_events) - valid
        if bad:
            raise ValidationError({'subscribed_events': f'Unknown event types: {bad}'})

        if self.is_active:
            qs = self.bank.webhooks.filter(is_active=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.count() >= self.bank.max_webhooks:
                raise ValidationError(
                    'Subscription tier does not allow more active webhooks.'
                )

    def is_subscribed_to(self, event_type: str) -> bool:
        return (not self.subscribed_events) or (event_type in self.subscribed_events)


# ===========================================================================
# WebhookDelivery  (one row per attempted POST)
# ===========================================================================

class WebhookDelivery(models.Model):
    STATUS_PENDING  = 'pending'
    STATUS_SUCCESS  = 'success'
    STATUS_FAILED   = 'failed'
    STATUS_RETRYING = 'retrying'
    STATUS_CHOICES  = (
        (STATUS_PENDING,  'Pending'),
        (STATUS_SUCCESS,  'Success'),
        (STATUS_FAILED,   'Failed'),
        (STATUS_RETRYING, 'Retrying'),
    )

    webhook          = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name='deliveries')
    event_type       = models.CharField(max_length=60)
    payload          = models.JSONField()
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    http_status_code = models.IntegerField(null=True, blank=True)
    response_body    = models.TextField(blank=True, default='', max_length=4096)
    attempts         = models.IntegerField(default=0)
    next_retry_at    = models.DateTimeField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    completed_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table  = 'webhook_deliveries'
        ordering  = ['-created_at']
        indexes   = [
            models.Index(fields=['webhook',    '-created_at']),
            models.Index(fields=['status',     'next_retry_at']),
            models.Index(fields=['event_type', '-created_at']),
        ]

    def __str__(self):
        return f'{self.event_type} → {self.webhook.name} [{self.status}]'


# ===========================================================================
# UsageLog  (one row per bank per day)
# ===========================================================================

class UsageLog(models.Model):
    bank             = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name='usage_logs')
    date             = models.DateField(db_index=True)
    api_calls        = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    unique_endpoints = models.JSONField(default=list)
    peak_calls_hour  = models.IntegerField(null=True, blank=True)   # 0-23 UTC

    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'usage_logs'
        unique_together = [('bank', 'date')]
        ordering        = ['-date']
        indexes         = [models.Index(fields=['bank', '-date'])]

    def __str__(self):
        return f'{self.bank.bank_id} | {self.date} | {self.api_calls} calls'


# ===========================================================================
# BillingRecord  (monthly invoice snapshot)
# ===========================================================================

class BillingRecord(models.Model):
    STATUS_DRAFT   = 'draft'
    STATUS_ISSUED  = 'issued'
    STATUS_PAID    = 'paid'
    STATUS_OVERDUE = 'overdue'
    STATUS_CHOICES = (
        (STATUS_DRAFT,   'Draft'),
        (STATUS_ISSUED,  'Issued'),
        (STATUS_PAID,    'Paid'),
        (STATUS_OVERDUE, 'Overdue'),
    )

    bank              = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name='billing_records')
    billing_month     = models.DateField(help_text='First day of the billing month (YYYY-MM-01)')
    subscription_tier = models.CharField(max_length=50, choices=SUBSCRIPTION_TIERS)

    total_api_calls   = models.IntegerField(default=0,  validators=[MinValueValidator(0)])
    overage_calls     = models.IntegerField(default=0,  validators=[MinValueValidator(0)])

    base_amount       = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    overage_amount    = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    total_amount      = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    issued_at         = models.DateTimeField(null=True, blank=True)
    paid_at           = models.DateTimeField(null=True, blank=True)
    notes             = models.TextField(blank=True, default='')

    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'billing_records'
        unique_together = [('bank', 'billing_month')]
        ordering        = ['-billing_month']
        indexes         = [
            models.Index(fields=['bank',   '-billing_month']),
            models.Index(fields=['status', '-billing_month']),
        ]

    def __str__(self):
        return f'{self.bank.bank_id} | {self.billing_month:%Y-%m} | {self.status}'