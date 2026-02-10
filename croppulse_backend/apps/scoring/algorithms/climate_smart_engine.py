# Enhanced Climate-Smart Score Engine

from apps.scoring.models import PulseScore
from apps.farmers.models_verification import ProofOfAction, GroundTruthReport
from django.db.models import Count, Q
from datetime import timedelta
from django.utils import timezone

class ClimateSmartScoreEngine:
    """Enhanced scoring with proof-of-action"""
    
    def calculate_action_score(self, farmer):
        """Calculate score based on verified actions (0-100)"""
        
        # Get actions from last 90 days
        cutoff = timezone.now() - timedelta(days=90)
        actions = ProofOfAction.objects.filter(
            farmer=farmer,
            action_date__gte=cutoff
        )
        
        total_actions = actions.count()
        verified_actions = actions.filter(verified=True).count()
        
        if total_actions == 0:
            return 0
        
        # Base score from verification rate
        verification_rate = (verified_actions / total_actions) * 100
        
        # Bonus for action diversity
        action_types = actions.filter(verified=True).values('action_type').distinct().count()
        diversity_bonus = min(action_types * 5, 20)  # Max 20 points
        
        # Bonus for consistency (actions per month)
        months_active = actions.filter(verified=True).dates('action_date', 'month').count()
        consistency_bonus = min(months_active * 3, 15)  # Max 15 points
        
        score = min(verification_rate * 0.65 + diversity_bonus + consistency_bonus, 100)
        return round(score)
    
    def calculate_ground_truth_score(self, farmer):
        """Calculate score based on weather reporting (0-100)"""
        
        cutoff = timezone.now() - timedelta(days=90)
        reports = GroundTruthReport.objects.filter(
            farmer=farmer,
            report_time__gte=cutoff
        )
        
        total_reports = reports.count()
        verified_reports = reports.filter(verified=True).count()
        
        if total_reports == 0:
            return 0
        
        # Score based on reporting frequency and accuracy
        reporting_rate = min((total_reports / 12) * 100, 100)  # 12 reports = 100%
        accuracy_rate = (verified_reports / total_reports) * 100 if total_reports > 0 else 0
        
        score = (reporting_rate * 0.4 + accuracy_rate * 0.6)
        return round(score)
    
    def update_climate_smart_score(self, farmer):
        """Update farmer's overall climate-smart score"""
        
        try:
            pulse_score = PulseScore.objects.get(farmer=farmer)
        except PulseScore.DoesNotExist:
            return None
        
        # Get component scores
        action_score = self.calculate_action_score(farmer)
        ground_truth_score = self.calculate_ground_truth_score(farmer)
        
        # Existing scores
        farm_size_score = pulse_score.farm_size_score or 0
        crop_health_score = pulse_score.crop_health_score or 0
        climate_risk_score = pulse_score.climate_risk_score or 0
        payment_history_score = pulse_score.payment_history_score or 0
        deforestation_score = pulse_score.deforestation_score or 0
        
        # New weighted calculation
        # 40% traditional factors + 30% actions + 30% ground-truth
        traditional_score = (
            farm_size_score * 0.15 +
            crop_health_score * 0.25 +
            climate_risk_score * 0.20 +
            payment_history_score * 0.25 +
            deforestation_score * 0.15
        )
        
        final_score = (
            traditional_score * 0.40 +
            action_score * 0.30 +
            ground_truth_score * 0.30
        )
        
        pulse_score.score = round(final_score)
        pulse_score.save()
        
        return pulse_score
