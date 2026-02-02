# apps/farms/views.py

from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Sum, Avg, Count, Q
from .models import Farm, FarmBoundaryPoint
from apps.farmers.models import Farmer
from .serializers import (
    FarmSerializer,
    FarmCreateSerializer,
    FarmUpdateSerializer,
    FarmDetailSerializer,
    FarmGeoJSONSerializer,
    FarmStatisticsSerializer,
    FarmBoundaryPointSerializer
)
from core.permissions import IsFarmerOwnerOrAdmin


class FarmCreateView(generics.CreateAPIView):
    """
    POST /api/v1/farms/create/
    
    Create a new farm with boundary points
    """
    serializer_class = FarmCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        farm = serializer.save()
        
        # Trigger satellite scan if requested
        trigger_scan = request.data.get('trigger_scan', False)
        if trigger_scan:
            from apps.satellite.tasks import process_satellite_scan
            process_satellite_scan.delay(farm.id)
        
        return Response({
            'message': 'Farm created successfully',
            'farm': FarmDetailSerializer(farm).data,
            'scan_queued': trigger_scan
        }, status=status.HTTP_201_CREATED)


class FarmListView(generics.ListAPIView):
    """
    GET /api/v1/farms/
    
    List all farms (with filters)
    """
    serializer_class = FarmSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Farm.objects.select_related('farmer', 'farmer__user').all()
        
        # Farmers see only their own farms
        if self.request.user.user_type == 'farmer':
            queryset = queryset.filter(farmer__user=self.request.user)
        
        # Filter by farmer (pulse_id)
        pulse_id = self.request.query_params.get('pulse_id')
        if pulse_id:
            queryset = queryset.filter(farmer__pulse_id=pulse_id)
        
        # Filter by county
        county = self.request.query_params.get('county')
        if county:
            queryset = queryset.filter(county__iexact=county)
        
        # Filter by verification status
        verified = self.request.query_params.get('verified')
        if verified is not None:
            is_verified = verified.lower() == 'true'
            queryset = queryset.filter(satellite_verified=is_verified)
        
        # Filter by primary status
        primary = self.request.query_params.get('primary')
        if primary is not None:
            is_primary = primary.lower() == 'true'
            queryset = queryset.filter(is_primary=is_primary)
        
        # Filter by size
        min_size = self.request.query_params.get('min_size')
        if min_size:
            queryset = queryset.filter(size_acres__gte=float(min_size))
        
        max_size = self.request.query_params.get('max_size')
        if max_size:
            queryset = queryset.filter(size_acres__lte=float(max_size))
        
        return queryset.order_by('-created_at')


class FarmDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/farms/{farm_id}/
    
    Get detailed farm information
    """
    serializer_class = FarmDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'farm_id'
    
    def get_queryset(self):
        queryset = Farm.objects.select_related(
            'farmer',
            'farmer__user'
        ).prefetch_related('satellite_scans', 'boundary_points')
        
        # Farmers can only view their own farms
        if self.request.user.user_type == 'farmer':
            queryset = queryset.filter(farmer__user=self.request.user)
        
        return queryset


class FarmUpdateView(generics.UpdateAPIView):
    """
    PUT/PATCH /api/v1/farms/{farm_id}/update/
    
    Update farm details (not boundary)
    """
    serializer_class = FarmUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsFarmerOwnerOrAdmin]
    lookup_field = 'farm_id'
    
    def get_queryset(self):
        queryset = Farm.objects.all()
        
        if self.request.user.user_type == 'farmer':
            queryset = queryset.filter(farmer__user=self.request.user)
        
        return queryset
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            'message': 'Farm updated successfully',
            'farm': FarmDetailSerializer(instance).data
        })


class FarmBoundaryPointsView(generics.ListAPIView):
    """
    GET /api/v1/farms/{farm_id}/boundary-points/
    
    Get all boundary points for a farm
    """
    serializer_class = FarmBoundaryPointSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        farm_id = self.kwargs.get('farm_id')
        farm = get_object_or_404(Farm, farm_id=farm_id)
        
        # Check permissions
        if self.request.user.user_type == 'farmer':
            if farm.farmer.user != self.request.user:
                return FarmBoundaryPoint.objects.none()
        
        return FarmBoundaryPoint.objects.filter(farm=farm).order_by('sequence')


class FarmerFarmsView(APIView):
    """
    GET /api/v1/farms/farmer/{pulse_id}/
    
    Get all farms for a specific farmer
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, pulse_id):
        farmer = get_object_or_404(Farmer, pulse_id=pulse_id)
        
        # Check permissions
        if request.user.user_type == 'farmer':
            if farmer.user != request.user:
                return Response({
                    'error': 'Permission denied'
                }, status=status.HTTP_403_FORBIDDEN)
        
        farms = Farm.objects.filter(farmer=farmer).order_by('-is_primary', '-created_at')
        serializer = FarmSerializer(farms, many=True)
        
        # Calculate totals
        total_area = farms.aggregate(
            total_acres=Sum('size_acres'),
            total_hectares=Sum('size_hectares')
        )
        
        return Response({
            'farmer': {
                'pulse_id': farmer.pulse_id,
                'full_name': farmer.full_name,
                'county': farmer.county
            },
            'farms': serializer.data,
            'total_farms': farms.count(),
            'total_area': total_area
        }, status=status.HTTP_200_OK)


class NearbyFarmsView(APIView):
    """
    GET /api/v1/farms/{farm_id}/nearby/?radius_km=5
    
    Get farms within a certain radius
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, farm_id):
        farm = get_object_or_404(Farm, farm_id=farm_id)
        
        # Get radius (default 5km)
        radius_km = float(request.query_params.get('radius_km', 5))
        
        if radius_km > 50:
            return Response({
                'error': 'Maximum radius is 50km'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Find nearby farms using PostGIS distance query
        nearby_farms = Farm.objects.filter(
            center_point__distance_lte=(farm.center_point, D(km=radius_km))
        ).exclude(id=farm.id).select_related('farmer')[:20]
        
        results = []
        for nearby_farm in nearby_farms:
            # Calculate exact distance
            distance = farm.center_point.distance(nearby_farm.center_point)
            distance_km = distance / 1000  # Convert meters to km
            
            results.append({
                'farm_id': nearby_farm.farm_id,
                'farmer_name': nearby_farm.farmer.full_name,
                'pulse_id': nearby_farm.farmer.pulse_id,
                'size_acres': float(nearby_farm.size_acres),
                'county': nearby_farm.county,
                'distance_km': round(distance_km, 2),
                'satellite_verified': nearby_farm.satellite_verified
            })
        
        return Response({
            'farm_id': farm_id,
            'radius_km': radius_km,
            'nearby_farms': results,
            'count': len(results)
        }, status=status.HTTP_200_OK)


class FarmsInAreaView(APIView):
    """
    GET /api/v1/farms/in-area/?lat=-1.2921&lng=36.8219&radius_km=10
    
    Get all farms within a radius of a point
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Get parameters
        try:
            lat = float(request.query_params.get('lat'))
            lng = float(request.query_params.get('lng'))
            radius_km = float(request.query_params.get('radius_km', 10))
        except (TypeError, ValueError):
            return Response({
                'error': 'Invalid parameters. Required: lat, lng (optional: radius_km)'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if radius_km > 100:
            return Response({
                'error': 'Maximum radius is 100km'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create point
        point = Point(lng, lat, srid=4326)
        
        # Find farms within radius
        farms = Farm.objects.filter(
            center_point__distance_lte=(point, D(km=radius_km))
        ).select_related('farmer')[:50]
        
        results = []
        for farm in farms:
            distance = point.distance(farm.center_point)
            distance_km = distance / 1000
            
            results.append({
                'farm_id': farm.farm_id,
                'farmer_name': farm.farmer.full_name,
                'pulse_id': farm.farmer.pulse_id,
                'size_acres': float(farm.size_acres),
                'county': farm.county,
                'distance_km': round(distance_km, 2)
            })
        
        return Response({
            'search_point': {'latitude': lat, 'longitude': lng},
            'radius_km': radius_km,
            'farms': results,
            'count': len(results)
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def farm_geojson(request, farm_id):
    """
    GET /api/v1/farms/{farm_id}/geojson/
    
    Get farm as GeoJSON (for mapping)
    """
    farm = get_object_or_404(Farm, farm_id=farm_id)
    
    # Check permissions
    if request.user.user_type == 'farmer':
        if farm.farmer.user != request.user:
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = FarmGeoJSONSerializer(farm)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsFarmerOwnerOrAdmin])
def trigger_farm_scan(request, farm_id):
    """
    POST /api/v1/farms/{farm_id}/scan/
    
    Trigger satellite scan for a farm
    """
    farm = get_object_or_404(Farm, farm_id=farm_id)
    
    # Check permissions
    if request.user.user_type == 'farmer':
        if farm.farmer.user != request.user:
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
    
    # Trigger scan
    from apps.satellite.tasks import process_satellite_scan
    task = process_satellite_scan.delay(farm.id)
    
    return Response({
        'message': 'Satellite scan initiated',
        'farm_id': farm_id,
        'task_id': task.id
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([permissions.IsAdminUser])
def farm_statistics(request):
    """
    GET /api/v1/farms/statistics/
    
    Get farm statistics (admin only)
    """
    total_farms = Farm.objects.count()
    
    # Calculate total area
    area_stats = Farm.objects.aggregate(
        total_acres=Sum('size_acres'),
        total_hectares=Sum('size_hectares'),
        avg_size=Avg('size_acres')
    )
    
    verified_farms = Farm.objects.filter(satellite_verified=True).count()
    
    # By county
    by_county = list(
        Farm.objects.values('county')
        .annotate(count=Count('id'), total_area=Sum('size_acres'))
        .order_by('-total_area')[:10]
    )
    
    # By size category
    size_categories = {
        'small': Farm.objects.filter(size_acres__lt=2).count(),
        'medium': Farm.objects.filter(size_acres__gte=2, size_acres__lt=5).count(),
        'large': Farm.objects.filter(size_acres__gte=5).count()
    }
    
    data = {
        'total_farms': total_farms,
        'total_area_acres': round(area_stats['total_acres'] or 0, 2),
        'total_area_hectares': round(area_stats['total_hectares'] or 0, 2),
        'average_farm_size': round(area_stats['avg_size'] or 0, 2),
        'verified_farms': verified_farms,
        'by_county': by_county,
        'by_size_category': size_categories
    }
    
    serializer = FarmStatisticsSerializer(data)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated, IsFarmerOwnerOrAdmin])
def delete_farm(request, farm_id):
    """
    DELETE /api/v1/farms/{farm_id}/delete/
    
    Delete a farm
    """
    farm = get_object_or_404(Farm, farm_id=farm_id)
    
    # Check permissions
    if request.user.user_type == 'farmer':
        if farm.farmer.user != request.user:
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
    
    # Require password confirmation
    password = request.data.get('password')
    if not password:
        return Response({
            'error': 'Password is required to delete farm'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not farm.farmer.user.check_password(password):
        return Response({
            'error': 'Incorrect password'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Delete farm
    farm_id_copy = farm.farm_id
    farm.delete()
    
    return Response({
        'message': f'Farm {farm_id_copy} deleted successfully'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsFarmerOwnerOrAdmin])
def set_primary_farm(request, farm_id):
    """
    POST /api/v1/farms/{farm_id}/set-primary/
    
    Set a farm as the primary farm
    """
    farm = get_object_or_404(Farm, farm_id=farm_id)
    
    # Check permissions
    if request.user.user_type == 'farmer':
        if farm.farmer.user != request.user:
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
    
    # Unset all other farms for this farmer
    Farm.objects.filter(farmer=farm.farmer).update(is_primary=False)
    
    # Set this farm as primary
    farm.is_primary = True
    farm.save(update_fields=['is_primary'])
    
    return Response({
        'message': f'Farm {farm_id} set as primary',
        'farm': FarmSerializer(farm).data
    }, status=status.HTTP_200_OK)