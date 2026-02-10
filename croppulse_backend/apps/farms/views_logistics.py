# API endpoints for insurance and logistics

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils.dateparse import parse_date
from apps.farmers.models import Farmer

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_insurance_claim(request):
    """Verify insurance claim with fraud detection"""
    
    farmer_id = request.data.get('farmer_id')
    farm_id = request.data.get('farm_id')
    claim_date = parse_date(request.data.get('date'))
    claim_type = request.data.get('type')
    
    if not all([farmer_id, farm_id, claim_date, claim_type]):
        return Response({'error': 'Missing required fields'}, status=400)
    
    try:
        farmer = Farmer.objects.get(id=farmer_id)
        
        from apps.loans.services.fraud_detection import InsuranceFraudDetector
        detector = InsuranceFraudDetector()
        
        verification = detector.verify_claim(farmer, {
            'farm_id': farm_id,
            'date': claim_date,
            'type': claim_type
        })
        
        return Response(verification)
        
    except Farmer.DoesNotExist:
        return Response({'error': 'Farmer not found'}, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analyze_harvest_timing(request, farm_id):
    """Get optimal harvest timing and logistics"""
    
    from apps.farms.services.logistics import LogisticsIntelligence
    logistics = LogisticsIntelligence()
    
    analysis = logistics.analyze_harvest_window(farm_id)
    
    return Response(analysis)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def estimate_harvest_loss(request, farm_id):
    """Estimate post-harvest losses from delay"""
    
    delay_days = int(request.GET.get('delay_days', 0))
    
    from apps.farms.services.logistics import LogisticsIntelligence
    logistics = LogisticsIntelligence()
    
    estimate = logistics.estimate_post_harvest_loss(farm_id, delay_days)
    
    return Response(estimate)
