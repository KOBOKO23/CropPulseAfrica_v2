# apps/climate/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
import ee
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_climate_data(request):
    """
    Get real-time climate data from NASA POWER API
    """
    try:
        from apps.climate.services.nasa_power_service import NASAPowerService
        from datetime import datetime, timedelta
        
        # Get location from request or use default
        lat = float(request.GET.get('lat', -1.2921))
        lng = float(request.GET.get('lng', 36.8219))
        
        # Get last 7 days of data (NASA POWER has ~2 week delay)
        nasa_service = NASAPowerService()
        end_date = datetime.now() - timedelta(days=14)
        start_date = end_date - timedelta(days=7)
        
        climate_data = nasa_service.get_climate_data(lat, lng, start_date, end_date)
        
        if 'error' in climate_data:
            return Response({
                'error': 'Failed to fetch climate data',
                'details': climate_data['error']
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get latest data point
        latest = climate_data[-1] if climate_data else None
        
        if not latest:
            return Response({
                'error': 'No climate data available'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Format response
        response_data = {
            'current': {
                'temperature': latest.get('temperature_avg'),
                'temperature_max': latest.get('temperature_max'),
                'temperature_min': latest.get('temperature_min'),
                'precipitation': latest.get('precipitation'),
                'humidity': latest.get('humidity'),
                'wind_speed': latest.get('wind_speed'),
                'date': str(latest.get('date'))
            },
            'weekly_data': climate_data,
            'data_source': 'NASA POWER',
            'location': {'lat': lat, 'lng': lng},
            'timestamp': timezone.now().isoformat()
        }
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Climate data request failed: {str(e)}")
        return Response({
            'error': 'Failed to fetch climate data',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def schedule_climate_updates(request):
    """
    Schedule automatic climate data updates
    """
    try:
        from celery import current_app
        
        # Schedule climate data updates every 30 minutes
        current_app.send_task(
            'climate.update_climate_data',
            countdown=0,  # Start immediately
            kwargs={'user_id': request.user.id}
        )
        
        return Response({
            'success': True,
            'message': 'Climate data updates scheduled successfully',
            'update_interval': '30 minutes'
        })
        
    except Exception as e:
        logger.error(f"Failed to schedule climate updates: {str(e)}")
        return Response({
            'error': 'Failed to schedule updates',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
