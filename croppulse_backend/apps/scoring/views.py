"""
Scoring App Views
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta

from apps.scoring.models import PulseScore, ScoreHistory, FraudAlert
from apps.scoring.serializers import (
    PulseScoreSerializer, ScoreHistorySerializer, FraudAlertSerializer
)
from apps.scoring.algorithms import PulseScoreEngine, FraudDetector
from apps.farmers.models import Farmer
from apps.farms.models import Farm


class CalculateScoreView(APIView):
    """POST: Calculate Pulse Score for farmer"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        farmer_id = request.data.get('farmer_id')
        farm_id = request.data.get('farm_id')
        
        farmer = get_object_or_404(Farmer, id=farmer_id)
        farm = get_object_or_404(Farm, id=farm_id, farmer=farmer)
        
        # Calculate score
        engine = PulseScoreEngine()
        result = engine.calculate_score(farmer, farm)
        
        # Mark old scores as non-current
        PulseScore.objects.filter(
            farmer=farmer,
            is_current=True
        ).update(is_current=False)
        
        # Create new score
        score = PulseScore.objects.create(
            farmer=farmer,
            farm=farm,
            score=result['score'],
            confidence_level=result['confidence'],
            farm_size_score=result['breakdown']['farm_size'],
            crop_health_score=result['breakdown']['crop_health'],
            climate_risk_score=result['breakdown']['climate_risk'],
            deforestation_score=result['breakdown']['deforestation'],
            payment_history_score=result['breakdown']['payment_history'],
            max_loan_amount=result['max_loan_amount'],
            recommended_interest_rate_min=result['recommended_interest_rate'][0],
            recommended_interest_rate_max=result['recommended_interest_rate'][1],
            default_probability=result['default_probability'],
            calculation_method='v1.0',
            factors_used=result['factors_used'],
            satellite_data_date=result['factors_used'].get('satellite_data_date'),
            climate_data_date=result['factors_used'].get('climate_data_date'),
            valid_until=result['valid_until'],
            is_current=True
        )
        
        serializer = PulseScoreSerializer(score)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class FarmerScoreView(APIView):
    """GET: Get current score for farmer"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, farmer_id):
        farmer = get_object_or_404(Farmer, id=farmer_id)
        
        score = PulseScore.objects.filter(
            farmer=farmer,
            is_current=True
        ).first()
        
        if not score:
            return Response(
                {'error': 'No score found. Calculate score first.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = PulseScoreSerializer(score)
        return Response(serializer.data)


class ScoreHistoryView(APIView):
    """GET: Score trend over time"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, farmer_id):
        farmer = get_object_or_404(Farmer, id=farmer_id)
        
        history = ScoreHistory.objects.filter(
            farmer=farmer
        ).order_by('-date')[:30]
        
        serializer = ScoreHistorySerializer(history, many=True)
        return Response(serializer.data)


class FraudAlertsView(APIView):
    """GET: Fraud alerts for farmer"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, farmer_id):
        farmer = get_object_or_404(Farmer, id=farmer_id)
        
        alerts = FraudAlert.objects.filter(
            farmer=farmer
        ).order_by('-created_at')
        
        serializer = FraudAlertSerializer(alerts, many=True)
        return Response(serializer.data)