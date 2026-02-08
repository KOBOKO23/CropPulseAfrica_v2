"""
Scoring App Serializers
"""

from rest_framework import serializers
from apps.scoring.models import (
    PulseScore, ScoreHistory, ScoreRecalculationLog,
    ScoreOverride, FraudAlert
)
from apps.farmers.serializers import FarmerSerializer
from apps.farms.serializers import FarmSerializer


class PulseScoreSerializer(serializers.ModelSerializer):
    """Read serializer with nested relations"""
    farmer_details = FarmerSerializer(source='farmer', read_only=True)
    farm_details = FarmSerializer(source='farm', read_only=True)
    grade = serializers.CharField(read_only=True)
    risk_category = serializers.CharField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = PulseScore
        fields = '__all__'
        read_only_fields = [
            'score', 'confidence_level', 'farm_size_score',
            'crop_health_score', 'climate_risk_score',
            'deforestation_score', 'payment_history_score',
            'max_loan_amount', 'recommended_interest_rate_min',
            'recommended_interest_rate_max', 'default_probability',
            'is_frozen', 'frozen_at', 'frozen_by_loan'
        ]


class ScoreHistorySerializer(serializers.ModelSerializer):
    """Score history entry"""
    farmer_name = serializers.CharField(source='farmer.full_name', read_only=True)
    
    class Meta:
        model = ScoreHistory
        fields = '__all__'
        read_only_fields = '__all__'


class ScoreRecalculationLogSerializer(serializers.ModelSerializer):
    """Recalculation log entry"""
    farmer_name = serializers.CharField(source='farmer.full_name', read_only=True)
    trigger_display = serializers.CharField(source='get_trigger_display', read_only=True)
    
    class Meta:
        model = ScoreRecalculationLog
        fields = '__all__'
        read_only_fields = '__all__'


class ScoreOverrideSerializer(serializers.ModelSerializer):
    """Score override record"""
    farmer_name = serializers.CharField(source='farmer.full_name', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = ScoreOverride
        fields = '__all__'


class FraudAlertSerializer(serializers.ModelSerializer):
    """Fraud alert record"""
    farmer_name = serializers.CharField(source='farmer.full_name', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True)
    
    class Meta:
        model = FraudAlert
        fields = '__all__'
        read_only_fields = [
            'farmer', 'farm', 'alert_type', 'severity',
            'description', 'evidence', 'score_impact'
        ]