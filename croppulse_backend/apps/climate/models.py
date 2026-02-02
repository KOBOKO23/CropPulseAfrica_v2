# climate/models.py

from django.db import models
from apps.farms.models import Farm

class ClimateData(models.Model):
    """NASA POWER climate data for farm location"""
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='climate_data')
    date = models.DateField()
    
    # Temperature (Celsius)
    temperature_max = models.FloatField()
    temperature_min = models.FloatField()
    temperature_avg = models.FloatField()
    
    # Precipitation (mm)
    rainfall = models.FloatField()
    rainfall_probability = models.FloatField()  # 0-100%
    
    # Other Metrics
    humidity = models.FloatField()
    wind_speed = models.FloatField()  # km/h
    solar_radiation = models.FloatField(null=True, blank=True)
    
    # Source
    data_source = models.CharField(max_length=50, default='NASA_POWER')
    is_forecast = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'climate_data'
        unique_together = ['farm', 'date']
        indexes = [
            models.Index(fields=['farm', '-date']),
        ]


class ClimateRiskAssessment(models.Model):
    """Climate risk calculation for a farm"""
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='risk_assessments')
    assessment_date = models.DateField(auto_now_add=True)
    
    # Risk Scores (0-100, higher = more risk)
    drought_risk = models.FloatField()
    flood_risk = models.FloatField()
    heat_stress_risk = models.FloatField()
    overall_climate_risk = models.FloatField()
    
    # Analysis Period
    analysis_start_date = models.DateField()
    analysis_end_date = models.DateField()
    
    # Historical Comparison
    historical_rainfall_avg = models.FloatField()  # 40-year average
    current_season_rainfall = models.FloatField()
    rainfall_deviation_percentage = models.FloatField()
    
    # Recommendations
    recommendations = models.JSONField(default=list)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'climate_risk_assessments'
        indexes = [
            models.Index(fields=['farm', '-assessment_date']),
        ]

# UPDATE: Add alert triggering mechanism based on risk thresholds