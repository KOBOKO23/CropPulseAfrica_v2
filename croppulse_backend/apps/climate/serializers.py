# apps/climate/serializers.py
from rest_framework import serializers
from apps.climate.models import ClimateData, ClimateRiskAssessment


class ClimateDataSerializer(serializers.ModelSerializer):
    """Serializer for climate data"""
    
    class Meta:
        model = ClimateData
        fields = [
            'id',
            'farm',
            'date',
            'temperature_max',
            'temperature_min',
            'temperature_avg',
            'rainfall',
            'rainfall_probability',
            'humidity',
            'wind_speed',
            'solar_radiation',
            'data_source',
            'is_forecast',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ClimateDataDetailSerializer(serializers.ModelSerializer):
    """Detailed climate data with additional computed fields"""
    
    temperature_range = serializers.SerializerMethodField()
    rainfall_category = serializers.SerializerMethodField()
    heat_stress_indicator = serializers.SerializerMethodField()
    
    class Meta:
        model = ClimateData
        fields = [
            'id',
            'farm',
            'date',
            'temperature_max',
            'temperature_min',
            'temperature_avg',
            'temperature_range',
            'rainfall',
            'rainfall_probability',
            'rainfall_category',
            'humidity',
            'wind_speed',
            'solar_radiation',
            'heat_stress_indicator',
            'data_source',
            'is_forecast',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_temperature_range(self, obj):
        """Calculate daily temperature range"""
        return round(obj.temperature_max - obj.temperature_min, 2)
    
    def get_rainfall_category(self, obj):
        """Categorize rainfall amount"""
        if obj.rainfall == 0:
            return 'none'
        elif obj.rainfall < 5:
            return 'light'
        elif obj.rainfall < 20:
            return 'moderate'
        elif obj.rainfall < 50:
            return 'heavy'
        else:
            return 'very_heavy'
    
    def get_heat_stress_indicator(self, obj):
        """Indicate if heat stress conditions exist"""
        if obj.temperature_max >= 35:
            return 'critical'
        elif obj.temperature_max >= 32:
            return 'warning'
        else:
            return 'normal'


class ClimateRiskAssessmentSerializer(serializers.ModelSerializer):
    """Serializer for climate risk assessment"""
    
    overall_risk_level = serializers.SerializerMethodField()
    drought_risk_level = serializers.SerializerMethodField()
    flood_risk_level = serializers.SerializerMethodField()
    heat_stress_risk_level = serializers.SerializerMethodField()
    
    class Meta:
        model = ClimateRiskAssessment
        fields = [
            'id',
            'farm',
            'assessment_date',
            'drought_risk',
            'drought_risk_level',
            'flood_risk',
            'flood_risk_level',
            'heat_stress_risk',
            'heat_stress_risk_level',
            'overall_climate_risk',
            'overall_risk_level',
            'analysis_start_date',
            'analysis_end_date',
            'historical_rainfall_avg',
            'current_season_rainfall',
            'rainfall_deviation_percentage',
            'recommendations',
            'created_at'
        ]
        read_only_fields = ['id', 'assessment_date', 'created_at']
    
    def get_overall_risk_level(self, obj):
        """Convert risk score to level"""
        return self._get_risk_level(obj.overall_climate_risk)
    
    def get_drought_risk_level(self, obj):
        """Convert drought risk score to level"""
        return self._get_risk_level(obj.drought_risk)
    
    def get_flood_risk_level(self, obj):
        """Convert flood risk score to level"""
        return self._get_risk_level(obj.flood_risk)
    
    def get_heat_stress_risk_level(self, obj):
        """Convert heat stress risk score to level"""
        return self._get_risk_level(obj.heat_stress_risk)
    
    def _get_risk_level(self, risk_score):
        """Helper to convert score to level"""
        if risk_score >= 70:
            return 'CRITICAL'
        elif risk_score >= 40:
            return 'HIGH'
        elif risk_score >= 20:
            return 'MODERATE'
        else:
            return 'LOW'


class HistoricalAnalysisSerializer(serializers.Serializer):
    """Serializer for historical climate analysis"""
    
    period_days = serializers.IntegerField()
    average_temperature = serializers.FloatField()
    maximum_temperature = serializers.FloatField()
    minimum_temperature = serializers.FloatField()
    total_rainfall_mm = serializers.FloatField()
    rainy_days = serializers.IntegerField()
    heavy_rain_days = serializers.IntegerField()
    dry_spell_days = serializers.IntegerField()
    extreme_heat_days = serializers.IntegerField()
    extreme_cold_days = serializers.IntegerField()


class RainfallAnomalySerializer(serializers.Serializer):
    """Serializer for rainfall anomaly data"""
    
    current_rainfall = serializers.FloatField()
    historical_average = serializers.FloatField()
    deviation_mm = serializers.FloatField()
    deviation_percentage = serializers.FloatField()
    status = serializers.CharField()


class WeatherForecastSerializer(serializers.Serializer):
    """Serializer for weather forecast data"""
    
    date = serializers.DateField()
    temperature_avg = serializers.FloatField()
    temperature_max = serializers.FloatField()
    temperature_min = serializers.FloatField()
    rainfall = serializers.FloatField()
    rainfall_probability = serializers.FloatField()
    humidity = serializers.FloatField()
    wind_speed = serializers.FloatField()
    conditions = serializers.CharField(required=False)
    is_forecast = serializers.BooleanField()
    data_source = serializers.CharField()


class AlertSerializer(serializers.Serializer):
    """Serializer for climate alerts"""
    
    id = serializers.CharField()
    farm_id = serializers.IntegerField()
    type = serializers.CharField()
    severity = serializers.CharField()
    risk_score = serializers.FloatField(required=False)
    title = serializers.CharField()
    message = serializers.CharField()
    recommendations = serializers.ListField(child=serializers.CharField())
    created_at = serializers.DateTimeField()
    data = serializers.DictField(required=False)


class InsuranceTriggerSerializer(serializers.Serializer):
    """Serializer for insurance trigger data"""
    
    triggered = serializers.BooleanField()
    trigger_type = serializers.CharField()
    trigger_date = serializers.DateField(required=False)
    coverage_period_days = serializers.IntegerField(required=False)
    payout_percentage = serializers.IntegerField()
    reason = serializers.CharField()
    confidence = serializers.CharField(required=False)


class InsurancePayoutSerializer(serializers.Serializer):
    """Serializer for insurance payout calculation"""
    
    policy_sum_insured = serializers.FloatField()
    triggered_perils = serializers.ListField(child=serializers.CharField())
    max_payout_percentage = serializers.IntegerField()
    payout_amount = serializers.FloatField()
    currency = serializers.CharField()
    payout_eligible = serializers.BooleanField()


class GrowingSeasonSerializer(serializers.Serializer):
    """Serializer for growing season suitability"""
    
    crop_type = serializers.CharField()
    suitability = serializers.CharField()
    average_temperature = serializers.FloatField()
    total_rainfall = serializers.FloatField()
    average_humidity = serializers.FloatField()
    temperature_suitable = serializers.BooleanField()
    rainfall_suitable = serializers.BooleanField()


class ClimateDataBulkCreateSerializer(serializers.Serializer):
    """Serializer for bulk climate data creation"""
    
    farm_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    def validate(self, data):
        """Validate date range"""
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("start_date must be before end_date")
        
        # Limit to reasonable range
        date_diff = (data['end_date'] - data['start_date']).days
        if date_diff > 365:
            raise serializers.ValidationError("Date range cannot exceed 365 days")
        
        return data