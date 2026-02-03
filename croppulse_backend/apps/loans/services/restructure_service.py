"""
Restructure Service

Handles:
- Climate-triggered interest rate resets
- Full loan restructuring (rate + tenor changes)
- Approval workflow for rate adjustments
- Automatic vs. manual reset modes
"""

from decimal import Decimal
from datetime import date
from django.db import transaction
from django.utils import timezone
from typing import List

from apps.loans.models import (
    LoanApplication,
    InterestRatePolicy,
    ClimateRateAdjustment,
    LoanRestructure,
    LoanAuditLog
)
from apps.loans.services.repayment_scheduler import RepaymentScheduler


class RestructureService:
    """
    Service for climate-protected loan restructuring.
    
    Two main flows:
    1. Climate event → rate adjustment (may be automatic or pending approval)
    2. Full restructure → rate + tenor change (always requires approval)
    """
    
    # Climate severity order (for threshold comparison)
    SEVERITY_ORDER = ['low', 'moderate', 'high', 'critical']
    
    @staticmethod
    def _severity_level(severity: str) -> int:
        """Convert severity string to numeric level for comparison"""
        return RestructureService.SEVERITY_ORDER.index(severity.lower())
    
    @staticmethod
    @transaction.atomic
    def on_climate_event(
        event_id: str,
        severity: str,
        region: str,
        description: str = ''
    ) -> List[ClimateRateAdjustment]:
        """
        Process climate event and create rate adjustments for affected loans.
        
        Called by climate app when severe weather event is detected.
        
        Process:
        1. Find all active loans (status='disbursed')
        2. For each bank, check InterestRatePolicy
        3. If severity >= threshold, create ClimateRateAdjustment
        4. If auto_reset_enabled=True, apply immediately
        5. If auto_reset_enabled=False, create pending adjustment for bank review
        
        Args:
            event_id: Unique climate event ID
            severity: 'low', 'moderate', 'high', or 'critical'
            region: Geographic region affected
            description: Human-readable event description
        
        Returns:
            List of ClimateRateAdjustment records created
        """
        severity_level = RestructureService._severity_level(severity)
        adjustments = []
        
        # Find all active loans
        active_loans = LoanApplication.objects.filter(
            status='disbursed'
        ).select_related('bank')
        
        # Group by bank to check policies
        banks_processed = set()
        
        for loan in active_loans:
            if loan.bank_id in banks_processed:
                continue
            
            banks_processed.add(loan.bank_id)
            
            # Get bank's rate policy
            policy = InterestRatePolicy.objects.filter(
                bank=loan.bank,
                is_active=True
            ).first()
            
            if not policy:
                # Bank has no policy - skip
                continue
            
            # Check if severity meets threshold
            threshold_level = RestructureService._severity_level(
                policy.climate_reset_threshold
            )
            
            if severity_level < threshold_level:
                # Event not severe enough - skip this bank
                continue
            
            # Event triggers rate reset for this bank
            # Create adjustments for all their active loans
            bank_loans = active_loans.filter(bank=loan.bank)
            
            for bank_loan in bank_loans:
                # Skip if loan is already at or below floor rate
                if bank_loan.interest_rate <= policy.climate_floor_rate:
                    continue
                
                # Create adjustment
                adjustment = ClimateRateAdjustment.objects.create(
                    loan=bank_loan,
                    bank=bank_loan.bank,
                    climate_event_id=event_id,
                    climate_severity=severity,
                    climate_region=region,
                    old_rate=bank_loan.interest_rate,
                    new_rate=policy.climate_floor_rate,
                    reason=description or f"{severity.title()} climate event in {region}",
                    status='pending'
                )
                
                adjustments.append(adjustment)
                
                # Auto-apply if enabled
                if policy.auto_reset_enabled:
                    RestructureService._apply_rate_adjustment(
                        adjustment,
                        auto_applied=True
                    )
        
        return adjustments
    
    @staticmethod
    @transaction.atomic
    def _apply_rate_adjustment(
        adjustment: ClimateRateAdjustment,
        reviewed_by=None,
        auto_applied: bool = False
    ):
        """
        Apply a climate rate adjustment to the loan.
        
        Updates:
        - adjustment.status = 'applied'
        - loan.interest_rate = adjustment.new_rate
        - loan.climate_protected = True
        
        If loan is disbursed, triggers full restructure to regenerate schedule.
        
        Args:
            adjustment: ClimateRateAdjustment instance
            reviewed_by: User who reviewed (for manual approval)
            auto_applied: True if triggered automatically by policy
        """
        loan = adjustment.loan
        
        # Update adjustment status
        adjustment.status = 'applied'
        adjustment.reviewed_by = reviewed_by
        adjustment.reviewed_at = timezone.now()
        adjustment.applied_at = timezone.now()
        adjustment.save()
        
        # Update loan rate
        old_rate = loan.interest_rate
        loan.interest_rate = adjustment.new_rate
        loan.climate_protected = True
        loan.save()
        
        # Create audit log
        LoanAuditLog.objects.create(
            loan=loan,
            action='climate_adjustment',
            old_value={'interest_rate': old_rate},
            new_value={
                'interest_rate': adjustment.new_rate,
                'climate_protected': True,
                'climate_event_id': adjustment.climate_event_id
            },
            details=f"Climate rate reset: {old_rate}% → {adjustment.new_rate}% (Event: {adjustment.climate_severity})",
            performed_by=reviewed_by,
            triggered_by_system=auto_applied
        )
        
        # If loan is already disbursed, need to regenerate schedule
        if loan.status == 'disbursed':
            # Initiate full restructure
            restructure = RestructureService.initiate_restructure(
                loan=loan,
                new_interest_rate=adjustment.new_rate,
                new_repayment_period_months=loan.repayment_period_months,
                reason='climate_event',
                climate_adjustment=adjustment,
                notes=f"Auto-restructure from climate event: {adjustment.reason}",
                auto_approve=True  # Auto-approve climate adjustments
            )
    
    @staticmethod
    @transaction.atomic
    def apply_climate_adjustment(
        adjustment: ClimateRateAdjustment,
        reviewed_by
    ) -> ClimateRateAdjustment:
        """
        Manually approve and apply a pending climate rate adjustment.
        
        Used when bank policy has auto_reset_enabled=False.
        
        Args:
            adjustment: ClimateRateAdjustment in 'pending' status
            reviewed_by: User approving the adjustment
        
        Returns:
            Updated ClimateRateAdjustment
        """
        if adjustment.status != 'pending':
            raise ValueError(
                f"Cannot apply adjustment in '{adjustment.status}' status"
            )
        
        RestructureService._apply_rate_adjustment(
            adjustment,
            reviewed_by=reviewed_by,
            auto_applied=False
        )
        
        return adjustment
    
    @staticmethod
    @transaction.atomic
    def initiate_restructure(
        loan: LoanApplication,
        new_interest_rate: float,
        new_repayment_period_months: int,
        reason: str,
        climate_adjustment: ClimateRateAdjustment = None,
        notes: str = '',
        auto_approve: bool = False
    ) -> LoanRestructure:
        """
        Initiate a full loan restructure.
        
        Creates LoanRestructure record in 'pending' status.
        Optionally auto-approve if triggered by climate event.
        
        Args:
            loan: LoanApplication to restructure
            new_interest_rate: New rate
            new_repayment_period_months: New tenor
            reason: Reason code (climate_event, default_risk, etc.)
            climate_adjustment: Link to ClimateRateAdjustment if applicable
            notes: Additional context
            auto_approve: If True, immediately approve and complete
        
        Returns:
            LoanRestructure instance
        """
        if loan.status not in ['approved', 'disbursed']:
            raise ValueError(
                f"Cannot restructure loan in '{loan.status}' status"
            )
        
        # Get current schedule for old values
        current_schedule = RepaymentScheduler.get_current_schedule(loan)
        
        if not current_schedule and loan.status == 'disbursed':
            raise ValueError("No current schedule found for disbursed loan")
        
        old_monthly_payment = current_schedule.monthly_payment if current_schedule else Decimal('0.00')
        
        # Create restructure record
        restructure = LoanRestructure.objects.create(
            loan=loan,
            bank=loan.bank,
            reason=reason,
            climate_adjustment=climate_adjustment,
            notes=notes,
            old_interest_rate=loan.interest_rate,
            old_repayment_period_months=loan.repayment_period_months,
            old_monthly_payment=old_monthly_payment,
            old_outstanding_balance=loan.outstanding_balance if loan.status == 'disbursed' else loan.approved_amount,
            new_interest_rate=new_interest_rate,
            new_repayment_period_months=new_repayment_period_months,
            status='pending'
        )
        
        # Auto-approve if requested (for climate events)
        if auto_approve:
            restructure = RestructureService.approve_restructure(
                restructure,
                reviewed_by=None
            )
        
        return restructure
    
    @staticmethod
    @transaction.atomic
    def approve_restructure(
        restructure: LoanRestructure,
        reviewed_by
    ) -> LoanRestructure:
        """
        Approve a pending restructure and regenerate schedule.
        
        Args:
            restructure: LoanRestructure in 'pending' status
            reviewed_by: User approving (None for system)
        
        Returns:
            Updated LoanRestructure
        """
        if restructure.status != 'pending':
            raise ValueError(
                f"Cannot approve restructure in '{restructure.status}' status"
            )
        
        restructure.status = 'approved'
        restructure.reviewed_by = reviewed_by
        restructure.reviewed_at = timezone.now()
        restructure.save()
        
        # Auto-complete for disbursed loans
        if restructure.loan.status == 'disbursed':
            restructure = RestructureService.complete_restructure(restructure)
        
        return restructure
    
    @staticmethod
    @transaction.atomic
    def complete_restructure(
        restructure: LoanRestructure
    ) -> LoanRestructure:
        """
        Complete a restructure by regenerating the repayment schedule.
        
        Args:
            restructure: LoanRestructure in 'approved' status
        
        Returns:
            Updated LoanRestructure
        """
        if restructure.status != 'approved':
            raise ValueError(
                f"Cannot complete restructure in '{restructure.status}' status"
            )
        
        loan = restructure.loan
        
        # Regenerate schedule
        new_schedule = RepaymentScheduler.regenerate(
            loan=loan,
            new_interest_rate=restructure.new_interest_rate,
            new_repayment_period_months=restructure.new_repayment_period_months,
            outstanding_balance=restructure.old_outstanding_balance
        )
        
        # Update restructure
        restructure.new_monthly_payment = new_schedule.monthly_payment
        restructure.status = 'completed'
        restructure.completed_at = timezone.now()
        restructure.save()
        
        # Mark loan as climate protected if climate-triggered
        if restructure.reason == 'climate_event':
            loan.climate_protected = True
            loan.save()
        
        return restructure
    
    @staticmethod
    @transaction.atomic
    def reject_restructure(
        restructure: LoanRestructure,
        reviewed_by,
        notes: str = ''
    ) -> LoanRestructure:
        """
        Reject a pending restructure.
        
        Args:
            restructure: LoanRestructure in 'pending' status
            reviewed_by: User rejecting
            notes: Rejection reason
        
        Returns:
            Updated LoanRestructure
        """
        if restructure.status != 'pending':
            raise ValueError(
                f"Cannot reject restructure in '{restructure.status}' status"
            )
        
        restructure.status = 'rejected'
        restructure.reviewed_by = reviewed_by
        restructure.reviewed_at = timezone.now()
        restructure.notes = f"{restructure.notes}\nRejection: {notes}".strip()
        restructure.save()
        
        # Also reject linked climate adjustment if exists
        if restructure.climate_adjustment:
            adjustment = restructure.climate_adjustment
            adjustment.status = 'rejected'
            adjustment.reviewed_by = reviewed_by
            adjustment.reviewed_at = timezone.now()
            adjustment.save()
        
        return restructure