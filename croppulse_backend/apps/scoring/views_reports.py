# Credit report API endpoint

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from apps.farmers.models import Farmer
from .services.credit_report import BankCreditReportGenerator

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_credit_report(request, farmer_id):
    """Download PDF credit report for bank"""
    
    try:
        farmer = Farmer.objects.get(id=farmer_id)
        
        # Generate report
        generator = BankCreditReportGenerator()
        pdf_buffer = generator.generate_report(farmer)
        
        # Return PDF
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="credit_report_{farmer.pulse_id}.pdf"'
        return response
        
    except Farmer.DoesNotExist:
        return Response({'error': 'Farmer not found'}, status=404)
