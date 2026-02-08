"""
Score Freezer

Manages score freezing during loan application process to ensure
consistent credit assessment even if farmer's situation changes.

Workflow:
1. Farmer applies for loan → Score is frozen
2. Bank reviews application → Uses frozen score
3. Loan approved/rejected/disbursed → Score unfrozen
"""

from django.utils import timezone
from django.db import transaction


class ScoreFreezer:
    """
    Freeze and unfreeze Pulse Scores for loan applications.
    
    Ensures loan decisions are based on consistent scores even if:
    - New satellite data arrives
    - Climate conditions change
    - Payment history updates
    """
    
    @staticmethod
    @transaction.atomic
    def freeze_for_loan(farmer, loan_application):
        """
        Freeze farmer's current score for loan application.
        
        Args:
            farmer: Farmer model instance
            loan_application: LoanApplication model instance
        
        Returns:
            PulseScore: The frozen score instance
        
        Raises:
            ValueError: If no current score exists or score already frozen
        """
        from apps.scoring.models import PulseScore
        
        # Get current active score
        current_score = PulseScore.objects.filter(
            farmer=farmer,
            is_current=True
        ).first()
        
        if not current_score:
            raise ValueError(
                f"No active score found for farmer {farmer.full_name}. "
                "Calculate score before applying for loan."
            )
        
        if current_score.is_frozen:
            raise ValueError(
                f"Score is already frozen for loan application "
                f"{current_score.frozen_by_loan.application_id}"
            )
        
        # Check if score is still valid
        if not current_score.is_valid:
            raise ValueError(
                f"Score expired on {current_score.valid_until.date()}. "
                "Recalculate score before applying for loan."
            )
        
        # Freeze the score
        current_score.freeze(loan_application)
        
        return current_score
    
    @staticmethod
    @transaction.atomic
    def unfreeze_for_loan(loan_application):
        """
        Unfreeze score after loan is processed (approved/rejected/disbursed).
        
        Args:
            loan_application: LoanApplication model instance
        
        Returns:
            PulseScore: The unfrozen score instance or None
        """
        from apps.scoring.models import PulseScore
        
        # Find frozen score for this loan
        frozen_score = PulseScore.objects.filter(
            frozen_by_loan=loan_application,
            is_frozen=True
        ).first()
        
        if frozen_score:
            frozen_score.unfreeze()
        
        return frozen_score
    
    @staticmethod
    def get_frozen_score(loan_application):
        """
        Get the frozen score for a loan application.
        
        Args:
            loan_application: LoanApplication model instance
        
        Returns:
            PulseScore or None
        """
        from apps.scoring.models import PulseScore
        
        return PulseScore.objects.filter(
            frozen_by_loan=loan_application,
            is_frozen=True
        ).first()
    
    @staticmethod
    def is_score_frozen(farmer):
        """
        Check if farmer has a frozen score.
        
        Args:
            farmer: Farmer model instance
        
        Returns:
            bool: True if score is frozen
        """
        from apps.scoring.models import PulseScore
        
        return PulseScore.objects.filter(
            farmer=farmer,
            is_frozen=True
        ).exists()
    
    @staticmethod
    @transaction.atomic
    def auto_unfreeze_expired_loans():
        """
        Unfreeze scores for loans that have been processed.
        
        Run as Celery task to clean up frozen scores for:
        - Approved loans
        - Rejected loans
        - Disbursed loans
        - Defaulted loans
        
        Returns:
            int: Number of scores unfrozen
        """
        from apps.scoring.models import PulseScore
        from apps.loans.models import LoanApplication
        
        # Find frozen scores where loan is no longer pending
        frozen_scores = PulseScore.objects.filter(
            is_frozen=True,
            frozen_by_loan__isnull=False
        ).select_related('frozen_by_loan')
        
        count = 0
        for score in frozen_scores:
            loan = score.frozen_by_loan
            
            # Unfreeze if loan is no longer pending
            if loan.status != 'pending':
                score.unfreeze()
                count += 1
        
        return count
    
    @staticmethod
    def get_loan_score_snapshot(loan_application):
        """
        Get score snapshot used for loan approval decision.
        
        Args:
            loan_application: LoanApplication model instance
        
        Returns:
            dict: Score details at time of application
        """
        frozen_score = ScoreFreezer.get_frozen_score(loan_application)
        
        if not frozen_score:
            return None
        
        return {
            'score': frozen_score.score,
            'grade': frozen_score.grade,
            'confidence': frozen_score.confidence_level,
            'frozen_at': frozen_score.frozen_at,
            'breakdown': {
                'farm_size': frozen_score.farm_size_score,
                'crop_health': frozen_score.crop_health_score,
                'climate_risk': frozen_score.climate_risk_score,
                'deforestation': frozen_score.deforestation_score,
                'payment_history': frozen_score.payment_history_score
            },
            'credit_terms': {
                'max_loan': frozen_score.max_loan_amount,
                'rate_min': frozen_score.recommended_interest_rate_min,
                'rate_max': frozen_score.recommended_interest_rate_max,
                'default_prob': frozen_score.default_probability
            }
        }