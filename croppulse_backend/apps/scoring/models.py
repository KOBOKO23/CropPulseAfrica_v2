# scoring/models.py

from django.db import models
from apps.farmers.models import Farmer
from apps.farms.models import Farm

class PulseScore(models.Model):
    """The core credit score for a farmer"""
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name='pulse_scores')
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='pulse_scores')
    
    # Score Components
    score = models.IntegerField()  # 0-100
    confidence_level = models.FloatField()  # 0.0-1.0
    
    # Score Breakdown
    farm_size_score = models.IntegerField()
    crop_health_score = models.IntegerField()
    climate_risk_score = models.IntegerField()
    deforestation_score = models.IntegerField()
    payment_history_score = models.IntegerField(default=0)
    
    # Credit Implications
    max_loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    recommended_interest_rate_min = models.FloatField()
    recommended_interest_rate_max = models.FloatField()
    default_probability = models.FloatField()  # 0-100%
    
    # Metadata
    calculation_method = models.CharField(max_length=50, default='v1.0')
    factors_used = models.JSONField()  # List of data points used
    
    # Validity
    valid_from = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField()
    is_current = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pulse_scores'
        indexes = [
            models.Index(fields=['farmer', '-created_at']),
            models.Index(fields=['is_current']),
        ]


class ScoreHistory(models.Model):
    """Track score changes over time"""
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name='score_history')
    date = models.DateField()
    score = models.IntegerField()
    change_from_previous = models.IntegerField()
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'score_history'
        unique_together = ['farmer', 'date']