# Serializers for verification features

from rest_framework import serializers
from .models_verification import GroundTruthReport, ProofOfAction

class GroundTruthReportSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source='farmer.user.username', read_only=True)
    farm_name = serializers.CharField(source='farm.name', read_only=True)
    
    class Meta:
        model = GroundTruthReport
        fields = ['id', 'farmer', 'farmer_name', 'farm', 'farm_name', 
                  'weather_condition', 'temperature_feel', 'rainfall_amount',
                  'report_time', 'weather_time', 'notes', 'photo', 
                  'verified', 'verified_by']
        read_only_fields = ['verified', 'verified_by']


class ProofOfActionSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source='farmer.user.username', read_only=True)
    farm_name = serializers.CharField(source='farm.name', read_only=True)
    
    class Meta:
        model = ProofOfAction
        fields = ['id', 'farmer', 'farmer_name', 'farm', 'farm_name',
                  'action_type', 'description', 'action_date',
                  'photo', 'voice_note', 'verified', 'verified_by',
                  'verified_at', 'points_earned', 'blockchain_hash', 'created_at']
        read_only_fields = ['verified', 'verified_by', 'verified_at', 
                            'points_earned', 'blockchain_hash']
