# apps/farms/serializers.py

from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer, GeometryField
from django.contrib.gis.geos import Point, Polygon
from .models import Farm, FarmBoundaryPoint
from apps.farmers.models import Farmer


class FarmBoundaryPointSerializer(serializers.ModelSerializer):
    """Serializer for individual boundary points"""
    
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    
    class Meta:
        model = FarmBoundaryPoint
        fields = ['id', 'sequence', 'latitude', 'longitude', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_latitude(self, obj):
        """Get latitude from point"""
        return obj.point.y
    
    def get_longitude(self, obj):
        """Get longitude from point"""
        return obj.point.x


class FarmSerializer(serializers.ModelSerializer):
    """Basic serializer for Farm model"""
    
    farmer_name = serializers.CharField(source='farmer.full_name', read_only=True)
    pulse_id = serializers.CharField(source='farmer.pulse_id', read_only=True)
    center_latitude = serializers.SerializerMethodField()
    center_longitude = serializers.SerializerMethodField()
    boundary_coordinates = serializers.SerializerMethodField()
    
    class Meta:
        model = Farm
        fields = [
            'id',
            'farm_id',
            'farmer',
            'farmer_name',
            'pulse_id',
            'size_acres',
            'size_hectares',
            'elevation',
            'county',
            'sub_county',
            'ward',
            'center_latitude',
            'center_longitude',
            'boundary_coordinates',
            'satellite_verified',
            'last_verified',
            'is_primary',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'farm_id',
            'size_hectares',
            'satellite_verified',
            'last_verified',
            'created_at',
            'updated_at'
        ]
    
    def get_center_latitude(self, obj):
        """Get center point latitude"""
        return obj.center_point.y if obj.center_point else None
    
    def get_center_longitude(self, obj):
        """Get center point longitude"""
        return obj.center_point.x if obj.center_point else None
    
    def get_boundary_coordinates(self, obj):
        """Get boundary coordinates as array"""
        if obj.boundary:
            coords = obj.boundary.coords[0]
            return [{'lat': point[1], 'lng': point[0]} for point in coords]
        return []


class FarmCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new farm"""
    
    boundary_points = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        help_text="List of {lat, lng} objects defining farm boundary"
    )
    
    class Meta:
        model = Farm
        fields = [
            'farmer',
            'county',
            'sub_county',
            'ward',
            'elevation',
            'boundary_points',
            'ownership_document',
            'is_primary'
        ]
    
    def validate_boundary_points(self, value):
        """Validate boundary points"""
        if len(value) < 3:
            raise serializers.ValidationError(
                "At least 3 points are required to define a boundary"
            )
        
        # Validate each point has lat and lng
        for i, point in enumerate(value):
            if 'lat' not in point or 'lng' not in point:
                raise serializers.ValidationError(
                    f"Point {i} must have 'lat' and 'lng' fields"
                )
            
            # Validate coordinate ranges
            try:
                lat = float(point['lat'])
                lng = float(point['lng'])
                
                if not (-90 <= lat <= 90):
                    raise serializers.ValidationError(
                        f"Point {i}: Latitude must be between -90 and 90"
                    )
                
                if not (-180 <= lng <= 180):
                    raise serializers.ValidationError(
                        f"Point {i}: Longitude must be between -180 and 180"
                    )
                
                # Validate Kenya coordinates (rough bounds)
                if not (-5 <= lat <= 5 and 33 <= lng <= 42):
                    raise serializers.ValidationError(
                        f"Point {i}: Coordinates appear to be outside Kenya"
                    )
            
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    f"Point {i}: Invalid coordinate values"
                )
        
        return value
    
    def validate_farmer(self, value):
        """Validate farmer exists and is active"""
        if not value.is_active:
            raise serializers.ValidationError(
                "Cannot create farm for inactive farmer"
            )
        return value
    
    def create(self, validated_data):
        """Create farm with boundary"""
        boundary_points_data = validated_data.pop('boundary_points')
        
        # Create polygon from boundary points
        # Format: [(lng, lat), (lng, lat), ...]
        coords = [
            (float(point['lng']), float(point['lat']))
            for point in boundary_points_data
        ]
        
        # Close the polygon (first point = last point)
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        
        # Create polygon
        boundary = Polygon(coords)
        
        # Calculate center point
        center_point = boundary.centroid
        
        # Calculate area in acres
        # boundary.area returns square meters (with geography=True)
        area_sq_meters = boundary.area
        area_acres = area_sq_meters / 4046.86
        area_hectares = area_sq_meters / 10000
        
        # Generate farm ID
        farm_id = self._generate_farm_id(validated_data['farmer'])
        
        # Create farm
        farm = Farm.objects.create(
            farm_id=farm_id,
            boundary=boundary,
            center_point=center_point,
            size_acres=round(area_acres, 2),
            size_hectares=round(area_hectares, 2),
            **validated_data
        )
        
        # Create boundary point records
        for i, point_data in enumerate(boundary_points_data):
            point = Point(float(point_data['lng']), float(point_data['lat']))
            FarmBoundaryPoint.objects.create(
                farm=farm,
                point=point,
                sequence=i
            )
        
        return farm
    
    def _generate_farm_id(self, farmer):
        """Generate unique farm ID"""
        import random
        
        # Format: FARM-{pulse_id}-{number}
        pulse_id = farmer.pulse_id.split('-')[1]  # Get middle part (e.g., "882")
        
        while True:
            number = random.randint(10, 99)
            farm_id = f"FARM-{pulse_id}-{number}"
            
            if not Farm.objects.filter(farm_id=farm_id).exists():
                return farm_id


class FarmUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating farm details"""
    
    class Meta:
        model = Farm
        fields = [
            'county',
            'sub_county',
            'ward',
            'elevation',
            'ownership_document',
            'is_primary'
        ]


class FarmDetailSerializer(serializers.ModelSerializer):
    """Detailed farm serializer with additional information"""
    
    farmer_details = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    boundary_geojson = serializers.SerializerMethodField()
    satellite_scan_summary = serializers.SerializerMethodField()
    nearby_farms = serializers.SerializerMethodField()
    
    class Meta:
        model = Farm
        fields = [
            'id',
            'farm_id',
            'farmer_details',
            'location',
            'size_acres',
            'size_hectares',
            'elevation',
            'county',
            'sub_county',
            'ward',
            'boundary_geojson',
            'satellite_verified',
            'last_verified',
            'satellite_scan_summary',
            'ownership_document',
            'is_primary',
            'nearby_farms',
            'created_at',
            'updated_at'
        ]
        read_only_fields = fields
    
    def get_farmer_details(self, obj):
        """Get farmer details"""
        return {
            'pulse_id': obj.farmer.pulse_id,
            'full_name': obj.farmer.full_name,
            'phone_number': obj.farmer.user.phone_number,
            'county': obj.farmer.county,
            'primary_crop': obj.farmer.primary_crop
        }
    
    def get_location(self, obj):
        """Get location details"""
        return {
            'center': {
                'latitude': obj.center_point.y,
                'longitude': obj.center_point.x
            },
            'address': {
                'county': obj.county,
                'sub_county': obj.sub_county,
                'ward': obj.ward
            },
            'elevation': obj.elevation
        }
    
    def get_boundary_geojson(self, obj):
        """Get boundary as GeoJSON"""
        if obj.boundary:
            # GeoJSON format
            coords = obj.boundary.coords[0]
            return {
                'type': 'Polygon',
                'coordinates': [[
                    [point[0], point[1]] for point in coords
                ]]
            }
        return None
    
    def get_satellite_scan_summary(self, obj):
        """Get satellite scan summary"""
        latest_scan = obj.satellite_scans.order_by('-acquisition_date').first()
        
        if not latest_scan:
            return {
                'total_scans': 0,
                'latest_scan': None
            }
        
        return {
            'total_scans': obj.satellite_scans.count(),
            'latest_scan': {
                'scan_id': latest_scan.scan_id,
                'acquisition_date': latest_scan.acquisition_date,
                'ndvi': latest_scan.ndvi,
                'crop_health': latest_scan.crop_health_status,
                'satellite_type': latest_scan.satellite_type
            }
        }
    
    def get_nearby_farms(self, obj):
        """Get nearby farms (within 5km)"""
        from django.contrib.gis.measure import D
        
        # Find farms within 5km
        nearby = Farm.objects.filter(
            center_point__distance_lte=(obj.center_point, D(km=5))
        ).exclude(id=obj.id).select_related('farmer')[:5]
        
        return [
            {
                'farm_id': farm.farm_id,
                'farmer_name': farm.farmer.full_name,
                'distance_km': round(
                    obj.center_point.distance(farm.center_point) / 1000,
                    2
                )
            }
            for farm in nearby
        ]


class FarmGeoJSONSerializer(GeoFeatureModelSerializer):
    """GeoJSON serializer for mapping applications"""
    
    class Meta:
        model = Farm
        geo_field = 'boundary'
        fields = [
            'farm_id',
            'size_acres',
            'county',
            'satellite_verified',
            'is_primary'
        ]


class FarmStatisticsSerializer(serializers.Serializer):
    """Serializer for farm statistics"""
    
    total_farms = serializers.IntegerField()
    total_area_acres = serializers.FloatField()
    total_area_hectares = serializers.FloatField()
    average_farm_size = serializers.FloatField()
    verified_farms = serializers.IntegerField()
    by_county = serializers.ListField()
    by_size_category = serializers.DictField()


class FarmSearchSerializer(serializers.Serializer):
    """Serializer for farm search results"""
    
    farm_id = serializers.CharField()
    farmer_name = serializers.CharField()
    pulse_id = serializers.CharField()
    county = serializers.CharField()
    size_acres = serializers.FloatField()
    satellite_verified = serializers.BooleanField()
    distance_km = serializers.FloatField(required=False)