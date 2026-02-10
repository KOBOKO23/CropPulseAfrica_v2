# Views for verification features

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from .models_verification import GroundTruthReport, ProofOfAction
from .serializers_verification import GroundTruthReportSerializer, ProofOfActionSerializer
from apps.scoring.models import PulseScore
from integrations.africas_talking.sms import SMSService

# Ground Truth Reporting
class GroundTruthReportListCreateView(generics.ListCreateAPIView):
    serializer_class = GroundTruthReportSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.user_type == 'farmer':
            return GroundTruthReport.objects.filter(farmer__user=self.request.user)
        return GroundTruthReport.objects.all()
    
    def perform_create(self, serializer):
        farmer = self.request.user.farmer
        serializer.save(farmer=farmer)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_ground_truth(request, pk):
    """Verify a ground truth report"""
    try:
        report = GroundTruthReport.objects.get(pk=pk)
        report.verified = True
        report.verified_by = request.user
        report.save()
        return Response({'status': 'verified'})
    except GroundTruthReport.DoesNotExist:
        return Response({'error': 'Report not found'}, status=404)


# Proof of Action
class ProofOfActionListCreateView(generics.ListCreateAPIView):
    serializer_class = ProofOfActionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.user_type == 'farmer':
            return ProofOfAction.objects.filter(farmer__user=self.request.user)
        return ProofOfAction.objects.all()
    
    def perform_create(self, serializer):
        farmer = self.request.user.farmer
        serializer.save(farmer=farmer)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_proof_of_action(request, pk):
    """Verify proof of action and award points"""
    try:
        action = ProofOfAction.objects.get(pk=pk)
        action.verified = True
        action.verified_by = request.user
        action.verified_at = timezone.now()
        action.points_earned = 5  # Base points
        
        # Log to blockchain
        from integrations.celo.blockchain import CeloBlockchain
        blockchain = CeloBlockchain()
        result = blockchain.log_action(
            farmer_id=action.farmer.id,
            action_type=action.action_type,
            description=action.description,
            timestamp=action.action_date.isoformat()
        )
        
        if result['status'] in ['success', 'disabled']:
            action.blockchain_hash = result.get('hash', '')
        
        action.save()
        
        # Update climate-smart score
        from apps.scoring.algorithms.climate_smart_engine import ClimateSmartScoreEngine
        engine = ClimateSmartScoreEngine()
        updated_score = engine.update_climate_smart_score(action.farmer)
        
        return Response({
            'status': 'verified',
            'points_earned': action.points_earned,
            'blockchain_hash': action.blockchain_hash,
            'new_score': updated_score.score if updated_score else None
        })
    except ProofOfAction.DoesNotExist:
        return Response({'error': 'Action not found'}, status=404)


# SMS Alerts
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_sms_alert(request):
    """Send SMS alert to farmers"""
    phone_numbers = request.data.get('phone_numbers', [])
    message = request.data.get('message', '')
    
    if not phone_numbers or not message:
        return Response({'error': 'phone_numbers and message required'}, status=400)
    
    sms_service = SMSService()
    result = sms_service.broadcast_alert(phone_numbers, message)
    
    return Response(result)
