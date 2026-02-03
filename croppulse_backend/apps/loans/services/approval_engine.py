"""
Approval Engine Service

Handles:
- Credit assessment based on Pulse Score
- Interest rate assignment
- Auto-approval/rejection logic
- Rate capping enforcement
"""

from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from django.db import transaction

from apps.loans.models import (
    LoanApplication, 
    InterestRatePolicy,
    LoanAuditLog,
    PLATFORM_MAX_INTEREST_RATE,
    PLATFORM_MIN_INTEREST_RATE,
    MINIMUM_PULSE_SCORE
)


class ApprovalEngine:
    """
    Loan approval engine with pulse-score-based rate assignment.
    
    Logic:
    1. Check if pulse_score meets minimum threshold (300)
    2. Load bank's InterestRatePolicy
    3. Map pulse_score to interest_rate (higher score = lower rate)
    4. Enforce platform-wide and bank-specific rate caps
    5. Set climate_risk_at_application from climate service
    6. Auto-approve if all checks pass
    """
    
    @staticmethod
    def evaluate(loan: LoanApplication) -> dict:
        """
        Evaluate loan application without changing status.
        
        Returns:
            {
                'approved': bool,
                'suggested_rate': float,
                'reason': str,
                'pulse_score': int
            }
        """
        pulse_score = loan.pulse_score_at_application
        
        # Check minimum score threshold
        if pulse_score < MINIMUM_PULSE_SCORE:
            return {
                'approved': False,
                'suggested_rate': None,
                'reason': f'Pulse Score {pulse_score} below minimum threshold ({MINIMUM_PULSE_SCORE})',
                'pulse_score': pulse_score
            }
        
        # Get bank's rate policy
        policy = InterestRatePolicy.objects.filter(
            bank=loan.bank,
            is_active=True
        ).first()
        
        if not policy:
            # Fallback to default rates if bank has no policy
            policy_min = 5.0
            policy_max = 24.0
        else:
            policy_min = policy.min_rate
            policy_max = policy.max_rate
        
        # Map pulse_score to interest_rate (linear interpolation)
        # Score 1000 → min_rate
        # Score 300 → max_rate
        # Higher score = lower rate (better credit = cheaper loan)
        score_range = 1000 - MINIMUM_PULSE_SCORE
        rate_range = policy_max - policy_min
        
        # Normalize score to [0, 1]
        normalized_score = (pulse_score - MINIMUM_PULSE_SCORE) / score_range
        
        # Invert (high score = low rate)
        suggested_rate = policy_max - (normalized_score * rate_range)
        
        # Clamp to platform bounds
        suggested_rate = max(PLATFORM_MIN_INTEREST_RATE, 
                           min(PLATFORM_MAX_INTEREST_RATE, suggested_rate))
        
        return {
            'approved': True,
            'suggested_rate': round(suggested_rate, 2),
            'reason': f'Pulse Score {pulse_score} qualifies for {suggested_rate:.2f}% rate',
            'pulse_score': pulse_score
        }
    
    @staticmethod
    @transaction.atomic
    def approve(
        loan: LoanApplication,
        reviewed_by=None,
        override_rate: float = None
    ) -> LoanApplication:
        """
        Approve loan and assign interest rate.
        
        Args:
            loan: LoanApplication instance
            reviewed_by: User who approved (optional)
            override_rate: Manual rate override (optional)
        
        Returns:
            Updated LoanApplication
        """
        if loan.status != 'pending':
            raise ValueError(f"Cannot approve loan with status '{loan.status}'")
        
        evaluation = ApprovalEngine.evaluate(loan)
        
        if not evaluation['approved']:
            raise ValueError(evaluation['reason'])
        
        # Use override rate or suggested rate
        final_rate = override_rate if override_rate else evaluation['suggested_rate']
        
        # Enforce caps
        final_rate = max(PLATFORM_MIN_INTEREST_RATE, 
                        min(PLATFORM_MAX_INTEREST_RATE, final_rate))
        
        # Get bank's rate cap for this loan
        policy = InterestRatePolicy.objects.filter(
            bank=loan.bank,
            is_active=True
        ).first()
        
        rate_cap = policy.max_rate if policy else PLATFORM_MAX_INTEREST_RATE
        
        # Set approved amount (can be same as requested or manually adjusted)
        if not loan.approved_amount:
            loan.approved_amount = loan.requested_amount
        
        # Update loan
        loan.status = 'approved'
        loan.interest_rate = final_rate
        loan.interest_rate_cap = rate_cap
        loan.reviewed_at = timezone.now()
        
        # TODO: Integrate with climate service to get current risk level
        # For now, set a placeholder
        loan.climate_risk_at_application = 'low'
        
        loan.save()
        
        # Create audit log
        LoanAuditLog.objects.create(
            loan=loan,
            action='status_change',
            old_value={'status': 'pending'},
            new_value={
                'status': 'approved',
                'interest_rate': final_rate,
                'interest_rate_cap': rate_cap,
                'approved_amount': str(loan.approved_amount)
            },
            details=f"Approved with {final_rate}% interest rate (Pulse Score: {loan.pulse_score_at_application})",
            performed_by=reviewed_by,
            triggered_by_system=(reviewed_by is None)
        )
        
        return loan
    
    @staticmethod
    @transaction.atomic
    def reject(
        loan: LoanApplication,
        reason: str,
        reviewed_by=None
    ) -> LoanApplication:
        """
        Reject loan application.
        
        Args:
            loan: LoanApplication instance
            reason: Rejection reason
            reviewed_by: User who rejected (optional)
        
        Returns:
            Updated LoanApplication
        """
        if loan.status != 'pending':
            raise ValueError(f"Cannot reject loan with status '{loan.status}'")
        
        loan.status = 'rejected'
        loan.reviewed_at = timezone.now()
        loan.save()
        
        # Create audit log
        LoanAuditLog.objects.create(
            loan=loan,
            action='status_change',
            old_value={'status': 'pending'},
            new_value={'status': 'rejected'},
            details=f"Rejected: {reason}",
            performed_by=reviewed_by,
            triggered_by_system=(reviewed_by is None)
        )
        
        return loan
    
    @staticmethod
    def bulk_evaluate(bank_id: int) -> dict:
        """
        Evaluate all pending loans for a bank.
        
        Args:
            bank_id: Bank ID
        
        Returns:
            {
                'total_pending': int,
                'auto_approvable': int,
                'auto_rejectable': int,
                'require_manual_review': int
            }
        """
        pending_loans = LoanApplication.objects.filter(
            bank_id=bank_id,
            status='pending'
        )
        
        auto_approve = 0
        auto_reject = 0
        manual_review = 0
        
        for loan in pending_loans:
            eval_result = ApprovalEngine.evaluate(loan)
            
            if not eval_result['approved']:
                auto_reject += 1
            elif eval_result['pulse_score'] >= 700:
                # High confidence - can auto-approve
                auto_approve += 1
            else:
                # Medium scores need manual review
                manual_review += 1
        
        return {
            'total_pending': pending_loans.count(),
            'auto_approvable': auto_approve,
            'auto_rejectable': auto_reject,
            'require_manual_review': manual_review
        }