# apps/satellite/views.py

from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Avg, Max, Min, Count
from datetime import timedelta
from .models import SatelliteScan, NDVIHistory
from apps.farms.models import Farm
from .serializers import (
    SatelliteScanSerializer,
    SatelliteScanDetailSerializer,
    SatelliteScanCreateSerializer,
    NDVIHistorySerializer,
    NDVITrendSerializer,
    FarmHealthSummarySerializer,
    BulkScanRequestSerializer
)
from .tasks import process_satellite_scan, bulk_process_scans
from core.permissions import IsFarmerOrAdmin, IsBankOrAdmin


class TriggerSatelliteScanView(APIView):
    """
    POST /api/v1/satellite/scan/trigger/
    
    Trigger a new satellite scan for a farm
    """
    permission_classes = [permissions.IsAuthenticated, IsFarmerOrAdmin]
    
    def post(self, request):
        serializer = SatelliteScanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        result = serializer.save()
        
        return Response({
            'message': 'Satellite scan initiated successfully',
            'data': result
        }, status=status.HTTP_202_ACCEPTED)


class SatelliteScanListView(generics.ListAPIView):
    """
    GET /api/v1/satellite/scans/
    
    List all satellite scans (with filters)
    """
    serializer_class = SatelliteScanSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = SatelliteScan.objects.select_related(
            'farm',
            'farm__farmer'
        ).order_by('-acquisition_date')
        
        # Filter by farm
        farm_id = self.request.query_params.get('farm_id')
        if farm_id:
            queryset = queryset.filter(farm__farm_id=farm_id)
        
        # Filter by farmer (if user is farmer, show only their scans)
        if self.request.user.user_type == 'farmer':
            queryset = queryset.filter(farm__farmer__user=self.request.user)
        
        # Filter by satellite type
        satellite_type = self.request.query_params.get('satellite_type')
        if satellite_type:
            queryset = queryset.filter(satellite_type=satellite_type)
        
        # Filter by health status
        health_status = self.request.query_params.get('health_status')
        if health_status:
            queryset = queryset.filter(crop_health_status=health_status)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(acquisition_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(acquisition_date__lte=end_date)
        
        return queryset


class SatelliteScanDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/satellite/scans/{scan_id}/
    
    Get detailed information about a specific scan
    """
    serializer_class = SatelliteScanDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'scan_id'
    
    def get_queryset(self):
        queryset = SatelliteScan.objects.select_related(
            'farm',
            'farm__farmer'
        )
        
        # Farmers can only see their own scans
        if self.request.user.user_type == 'farmer':
            queryset = queryset.filter(farm__farmer__user=self.request.user)
        
        return queryset


class FarmLatestScanView(APIView):
    """
    GET /api/v1/satellite/farms/{farm_id}/latest-scan/
    
    Get the latest satellite scan for a farm
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, farm_id):
        farm = get_object_or_404(Farm, farm_id=farm_id)
        
        # Check permissions
        if request.user.user_type == 'farmer':
            if farm.farmer.user != request.user:
                return Response({
                    'error': 'You do not have permission to view this farm'
                }, status=status.HTTP_403_FORBIDDEN)
        
        latest_scan = SatelliteScan.objects.filter(farm=farm).order_by('-acquisition_date').first()
        
        if not latest_scan:
            return Response({
                'message': 'No scans available for this farm',
                'farm_id': farm_id
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = SatelliteScanDetailSerializer(latest_scan)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NDVIHistoryListView(generics.ListAPIView):
    """
    GET /api/v1/satellite/ndvi-history/
    
    Get NDVI history for a farm
    """
    serializer_class = NDVIHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = NDVIHistory.objects.select_related('farm', 'satellite_scan')
        
        # Filter by farm (required)
        farm_id = self.request.query_params.get('farm_id')
        if not farm_id:
            return queryset.none()
        
        farm = get_object_or_404(Farm, farm_id=farm_id)
        
        # Check permissions
        if self.request.user.user_type == 'farmer':
            if farm.farmer.user != self.request.user:
                return queryset.none()
        
        queryset = queryset.filter(farm=farm)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        return queryset.order_by('-date')


class NDVITrendView(APIView):
    """
    GET /api/v1/satellite/ndvi-trend/{farm_id}/
    
    Get NDVI trend analysis for a farm
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, farm_id):
        farm = get_object_or_404(Farm, farm_id=farm_id)
        
        # Check permissions
        if request.user.user_type == 'farmer':
            if farm.farmer.user != request.user:
                return Response({
                    'error': 'You do not have permission to view this farm'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Get date range (default: last 90 days)
        days = int(request.query_params.get('days', 90))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get NDVI history
        history = NDVIHistory.objects.filter(
            farm=farm,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        if not history.exists():
            return Response({
                'message': 'No NDVI data available for this period',
                'farm_id': farm_id
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Calculate statistics
        data_points = [
            {
                'date': h.date.isoformat(),
                'ndvi': h.ndvi_value
            }
            for h in history
        ]
        
        ndvi_values = [h.ndvi_value for h in history]
        avg_ndvi = sum(ndvi_values) / len(ndvi_values)
        min_ndvi = min(ndvi_values)
        max_ndvi = max(ndvi_values)
        
        # Calculate trend
        if len(ndvi_values) > 1:
            first_value = ndvi_values[0]
            last_value = ndvi_values[-1]
            change_percentage = ((last_value - first_value) / first_value) * 100
            
            if change_percentage > 5:
                trend = 'Improving'
            elif change_percentage < -5:
                trend = 'Declining'
            else:
                trend = 'Stable'
        else:
            change_percentage = 0
            trend = 'Insufficient data'
        
        response_data = {
            'farm_id': farm_id,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'data_points': data_points,
            'trend': trend,
            'average_ndvi': round(avg_ndvi, 3),
            'min_ndvi': round(min_ndvi, 3),
            'max_ndvi': round(max_ndvi, 3),
            'change_percentage': round(change_percentage, 2)
        }
        
        serializer = NDVITrendSerializer(response_data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FarmHealthSummaryView(APIView):
    """
    GET /api/v1/satellite/farms/{farm_id}/health-summary/
    
    Get comprehensive health summary for a farm
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, farm_id):
        farm = get_object_or_404(Farm, farm_id=farm_id)
        
        # Check permissions
        if request.user.user_type == 'farmer':
            if farm.farmer.user != request.user:
                return Response({
                    'error': 'You do not have permission to view this farm'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Get latest scan
        latest_scan = SatelliteScan.objects.filter(farm=farm).order_by('-acquisition_date').first()
        
        if not latest_scan:
            return Response({
                'message': 'No satellite data available for this farm',
                'farm_id': farm_id
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get NDVI trend (last 30 days)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        ndvi_history = NDVIHistory.objects.filter(
            farm=farm,
            date__gte=start_date
        ).order_by('date')
        
        if ndvi_history.exists():
            ndvi_values = [h.ndvi_value for h in ndvi_history]
            avg_ndvi = sum(ndvi_values) / len(ndvi_values)
            
            if len(ndvi_values) > 1:
                change = ndvi_values[-1] - ndvi_values[0]
                trend = 'improving' if change > 0 else 'declining' if change < 0 else 'stable'
            else:
                trend = 'stable'
        else:
            avg_ndvi = latest_scan.ndvi if latest_scan.ndvi else 0
            trend = 'stable'
        
        # Calculate health score (0-100)
        health_score = self._calculate_health_score(latest_scan, avg_ndvi)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(latest_scan, trend)
        
        response_data = {
            'farm_id': farm_id,
            'latest_scan': SatelliteScanSerializer(latest_scan).data,
            'ndvi_trend': {
                'average': round(avg_ndvi, 3),
                'trend': trend,
                'period_days': 30
            },
            'health_score': health_score,
            'recommendations': recommendations,
            'last_updated': latest_scan.acquisition_date
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    def _calculate_health_score(self, scan, avg_ndvi):
        """Calculate overall health score"""
        score = 0
        
        # NDVI contribution (40 points)
        if avg_ndvi >= 0.75:
            score += 40
        elif avg_ndvi >= 0.60:
            score += 35
        elif avg_ndvi >= 0.40:
            score += 25
        else:
            score += 15
        
        # Soil moisture contribution (30 points)
        if scan.soil_moisture:
            if scan.soil_moisture >= 60:
                score += 30
            elif scan.soil_moisture >= 40:
                score += 20
            else:
                score += 10
        else:
            score += 20  # Default if no data
        
        # Crop health status contribution (30 points)
        if scan.crop_health_status == 'Healthy':
            score += 30
        elif scan.crop_health_status == 'Stressed':
            score += 15
        else:
            score += 5
        
        return min(score, 100)
    
    def _generate_recommendations(self, scan, trend):
        """Generate recommendations based on scan data"""
        recommendations = []
        
        if scan.ndvi and scan.ndvi < 0.50:
            recommendations.append('NDVI is low - consider fertilization or pest control')
        
        if scan.soil_moisture and scan.soil_moisture < 30:
            recommendations.append('Soil moisture is low - irrigation recommended')
        
        if trend == 'declining':
            recommendations.append('NDVI trend is declining - investigate potential issues')
        
        if scan.crop_health_status == 'Stressed':
            recommendations.append('Crops showing stress - inspect for pests or disease')
        
        if scan.cloud_cover_percentage > 70 and not scan.sar_penetrated_clouds:
            recommendations.append('High cloud cover detected - SAR scan recommended for clarity')
        
        if not recommendations:
            recommendations.append('Farm health is good - continue current practices')
        
        return recommendations


class BulkScanTriggerView(APIView):
    """
    POST /api/v1/satellite/scan/bulk-trigger/
    
    Trigger satellite scans for multiple farms
    """
    permission_classes = [permissions.IsAdminUser]
    
    def post(self, request):
        serializer = BulkScanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        farm_ids = serializer.validated_data['farm_ids']
        
        # Get farm objects
        farms = Farm.objects.filter(farm_id__in=farm_ids)
        
        # Trigger bulk scan task
        task = bulk_process_scans.delay([farm.id for farm in farms])
        
        return Response({
            'message': f'Bulk scan initiated for {len(farm_ids)} farms',
            'task_id': task.id,
            'farm_count': len(farm_ids)
        }, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def satellite_statistics(request):
    """
    GET /api/v1/satellite/statistics/
    
    Get satellite scan statistics
    """
    stats = {
        'total_scans': SatelliteScan.objects.count(),
        'scans_last_7_days': SatelliteScan.objects.filter(
            acquisition_date__gte=timezone.now() - timedelta(days=7)
        ).count(),
        'scans_last_30_days': SatelliteScan.objects.filter(
            acquisition_date__gte=timezone.now() - timedelta(days=30)
        ).count(),
        'average_cloud_cover': SatelliteScan.objects.aggregate(
            Avg('cloud_cover_percentage')
        )['cloud_cover_percentage__avg'] or 0,
        'average_ndvi': SatelliteScan.objects.filter(
            ndvi__isnull=False
        ).aggregate(Avg('ndvi'))['ndvi__avg'] or 0,
        'health_distribution': {
            'healthy': SatelliteScan.objects.filter(crop_health_status='Healthy').count(),
            'stressed': SatelliteScan.objects.filter(crop_health_status='Stressed').count(),
            'poor': SatelliteScan.objects.filter(crop_health_status='Poor').count(),
        },
        'satellite_types': SatelliteScan.objects.values('satellite_type').annotate(
            count=Count('id')
        )
    }
    
    return Response(stats, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsFarmerOrAdmin])
def rescan_farm(request, farm_id):
    """
    POST /api/v1/satellite/farms/{farm_id}/rescan/
    
    Trigger a rescan for a specific farm
    """
    farm = get_object_or_404(Farm, farm_id=farm_id)
    
    # Check permissions
    if request.user.user_type == 'farmer':
        if farm.farmer.user != request.user:
            return Response({
                'error': 'You do not have permission to scan this farm'
            }, status=status.HTTP_403_FORBIDDEN)
    
    # Trigger scan task
    task = process_satellite_scan.delay(farm.id)
    
    return Response({
        'message': 'Farm rescan initiated',
        'farm_id': farm_id,
        'task_id': task.id
    }, status=status.HTTP_202_ACCEPTED)