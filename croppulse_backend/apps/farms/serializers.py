# apps/farms/serializers.py

from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer, GeometryField
from django.contrib.gis.geos import Point, Polygon
from .models import Farm, FarmBoundaryPoint
from apps.farmers.models import Farmer
from .services import AreaCalculator, BoundaryService


class FarmBoundaryPointSerializer(serializers.ModelSerializer):
    """Serializer for individual boundary points"""
    
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    
    class Meta:
        model = FarmBoundaryPoint
        fields = [
            'id',
            'sequence',
            'latitude',
            'longitude',
            'altitude',
            'accuracy',
            'recorded_at',
            'created_at'
        ]
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
    area_info = serializers.SerializerMethodField()
    
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
            'area_info',
            'elevation',
            'soil_type',
            'slope_percentage',
            'county',
            'sub_county',
            'ward',
            'center_latitude',
            'center_longitude',
            'boundary_coordinates',
            'satellite_verified',
            'verification_confidence',
            'last_verified',
            'boundary_source',
            'boundary_accuracy_meters',
            'land_ownership_type',
            'is_primary',
            'is_active',
            'irrigation_available',
            'water_source',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'farm_id',
            'size_hectares',
            'satellite_verified',
            'verification_confidence',
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
        return obj.get_boundary_coordinates()
    
    def get_area_info(self, obj):
        """Get area in different units"""
        return {
            'acres': float(obj.size_acres),
            'hectares': float(obj.size_hectares),
            'square_meters': obj.get_area_in_square_meters()
        }


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
            'soil_type',
            'slope_percentage',
            'boundary_points',
            'boundary_source',
            'land_ownership_type',
            'ownership_document',
            'is_primary',
            'irrigation_available',
            'water_source'
        ]
    
    def validate_boundary_points(self, value):
        """Validate boundary points using service"""
        is_valid, errors, warnings = BoundaryService.validate_boundary_points(value)
        
        if not is_valid:
            raise serializers.ValidationError({
                'errors': errors,
                'warnings': warnings
            })
        
        # Store warnings in context for later use
        if warnings:
            self.context['boundary_warnings'] = warnings
        
        return value
    
    def validate_farmer(self, value):
        """Validate farmer exists and is active"""
        if not value.is_active:
            raise serializers.ValidationError(
                "Cannot create farm for inactive farmer"
            )
        
        if not value.user.is_verified:
            raise serializers.ValidationError(
                "Farmer's phone number must be verified before adding farms"
            )
        
        return value
    
    def validate_elevation(self, value):
        """Validate elevation is reasonable for Kenya"""
        if value is not None:
            if value < -100:
                raise serializers.ValidationError("Elevation cannot be below -100m")
            if value > 6000:
                raise serializers.ValidationError("Elevation cannot exceed 6000m (higher than Mt. Kenya)")
        return value
    
    def validate_slope_percentage(self, value):
        """Validate slope percentage"""
        if value is not None:
            if value < 0:
                raise serializers.ValidationError("Slope cannot be negative")
            if value > 100:
                raise serializers.ValidationError("Slope cannot exceed 100%")
        return value
    
    def create(self, validated_data):
        """Create farm with boundary"""
        boundary_points_data = validated_data.pop('boundary_points')
        
        # Create polygon from boundary points
        polygon = BoundaryService.create_polygon_from_points(boundary_points_data)
        
        # Calculate center point
        center_point = AreaCalculator.calculate_centroid(polygon)
        
        # Calculate area
        area_result = AreaCalculator.calculate_polygon_area(polygon)
        
        # Generate farm ID
        farm_id = self._generate_farm_id(validated_data['farmer'])
        
        # Estimate boundary accuracy if points have accuracy data
        avg_accuracy = None
        if any('accuracy' in p for p in boundary_points_data):
            accuracies = [p['accuracy'] for p in boundary_points_data if 'accuracy' in p]
            if accuracies:
                avg_accuracy = sum(accuracies) / len(accuracies)
        
        # Create farm
        farm = Farm.objects.create(
            farm_id=farm_id,
            boundary=polygon,
            center_point=center_point,
            size_acres=area_result['acres'],
            size_hectares=area_result['hectares'],
            boundary_accuracy_meters=avg_accuracy,
            **validated_data
        )
        
        # Create boundary point records
        BoundaryService.create_farm_boundary(farm, boundary_points_data)
        
        # Check for overlaps (async or log warning)
        overlap_result = BoundaryService.check_boundary_overlap(farm)
        if overlap_result['has_overlaps']:
            # Log warning or create notification
            print(f"Warning: Farm {farm_id} overlaps with {overlap_result['overlap_count']} farms")
        
        return farm
    
    def _generate_farm_id(self, farmer):
        """Generate unique farm ID"""
        import random
        
        # Format: FARM-{pulse_id_number}-{random}
        pulse_parts = farmer.pulse_id.split('-')
        pulse_number = pulse_parts[1] if len(pulse_parts) > 1 else '000'
        
        while True:
            number = random.randint(10, 99)
            farm_id = f"FARM-{pulse_number}-{number}"
            
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
            'soil_type',
            'slope_percentage',
            'land_ownership_type',
            'ownership_document',
            'is_primary',
            'irrigation_available',
            'water_source'
        ]
    
    def validate_elevation(self, value):
        """Validate elevation"""
        if value is not None:
            if value < -100 or value > 6000:
                raise serializers.ValidationError("Elevation must be between -100m and 6000m")
        return value


class FarmDetailSerializer(serializers.ModelSerializer):
    """Detailed farm serializer with additional information"""
    
    farmer_details = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    boundary_geojson = serializers.SerializerMethodField()
    boundary_analysis = serializers.SerializerMethodField()
    satellite_scan_summary = serializers.SerializerMethodField()
    nearby_farms = serializers.SerializerMethodField()
    area_breakdown = serializers.SerializerMethodField()
    
    class Meta:
        model = Farm
        fields = [
            'id',
            'farm_id',
            'farmer_details',
            'location',
            'area_breakdown',
            'elevation',
            'soil_type',
            'slope_percentage',
            'county',
            'sub_county',
            'ward',
            'boundary_geojson',
            'boundary_analysis',
            'satellite_verified',
            'verification_confidence',
            'last_verified',
            'satellite_scan_summary',
            'boundary_source',
            'boundary_accuracy_meters',
            'land_ownership_type',
            'ownership_document',
            'is_primary',
            'is_active',
            'irrigation_available',
            'water_source',
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
            'primary_crop': obj.farmer.primary_crop,
            'years_farming': obj.farmer.years_farming
        }
    
    def get_location(self, obj):
        """Get location details"""
        return {
            'center': obj.get_center_coordinates(),
            'address': {
                'county': obj.county,
                'sub_county': obj.sub_county,
                'ward': obj.ward
            },
            'elevation': obj.elevation,
            'within_kenya': BoundaryService.validate_kenya_location(obj.center_point)
        }
    
    def get_boundary_geojson(self, obj):
        """Get boundary as GeoJSON"""
        return BoundaryService.convert_to_geojson(obj)
    
    def get_boundary_analysis(self, obj):
        """Get boundary analysis"""
        # Calculate shape complexity
        complexity = AreaCalculator.calculate_shape_complexity(obj.boundary)
        
        # Calculate perimeter
        perimeter = AreaCalculator.calculate_perimeter(obj.boundary)
        
        # Get bounding box
        bbox = AreaCalculator.calculate_bounding_box(obj.boundary)
        
        # Check for anomalies
        anomalies = AreaCalculator.detect_anomalies(obj.boundary)
        
        # Get boundary accuracy
        boundary_points = obj.boundary_points.all()
        accuracy = BoundaryService.calculate_boundary_accuracy(boundary_points)
        
        return {
            'vertices_count': len(obj.boundary.coords[0]),
            'perimeter_meters': perimeter,
            'shape_complexity': complexity,
            'bounding_box': bbox,
            'anomalies': anomalies,
            'boundary_accuracy': accuracy
        }
    
    def get_satellite_scan_summary(self, obj):
        """Get satellite scan summary"""
        latest_scan = obj.satellite_scans.order_by('-acquisition_date').first()
        
        if not latest_scan:
            return {
                'total_scans': 0,
                'latest_scan': None,
                'needs_scan': True
            }
        
        return {
            'total_scans': obj.satellite_scans.count(),
            'latest_scan': {
                'scan_id': latest_scan.scan_id,
                'acquisition_date': latest_scan.acquisition_date,
                'ndvi': latest_scan.ndvi,
                'crop_health': latest_scan.crop_health_status,
                'satellite_type': latest_scan.satellite_type
            },
            'needs_scan': obj.needs_verification()
        }
    
    def get_nearby_farms(self, obj):
        """Get nearby farms (within 5km)"""
        from django.contrib.gis.measure import D
        
        nearby = Farm.objects.filter(
            center_point__distance_lte=(obj.center_point, D(km=5)),
            is_active=True
        ).exclude(id=obj.id).select_related('farmer')[:5]
        
        results = []
        for farm in nearby:
            distance = BoundaryService.calculate_distance_between_farms(obj, farm)
            results.append({
                'farm_id': farm.farm_id,
                'farmer_name': farm.farmer.full_name,
                'distance_km': distance['distance_km'],
                'size_acres': float(farm.size_acres)
            })
        
        return results
    
    def get_area_breakdown(self, obj):
        """Get area in all units"""
        return {
            'acres': float(obj.size_acres),
            'hectares': float(obj.size_hectares),
            'square_meters': obj.get_area_in_square_meters(),
            'perimeter_meters': obj.get_perimeter_meters()
        }


class FarmGeoJSONSerializer(GeoFeatureModelSerializer):
    """GeoJSON serializer for mapping applications"""
    
    farmer_name = serializers.CharField(source='farmer.full_name', read_only=True)
    
    class Meta:
        model = Farm
        geo_field = 'boundary'
        fields = [
            'farm_id',
            'farmer_name',
            'size_acres',
            'county',
            'satellite_verified',
            'is_primary',
            'is_active'
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


class BoundaryValidationSerializer(serializers.Serializer):
    """Serializer for boundary validation results"""
    
    is_valid = serializers.BooleanField()
    errors = serializers.ListField(child=serializers.CharField())
    warnings = serializers.ListField(child=serializers.CharField())
    calculated_area = serializers.DictField(required=False)
    shape_complexity = serializers.FloatField(required=False)


class FarmOverlapCheckSerializer(serializers.Serializer):
    """Serializer for farm overlap check results"""
    
    has_overlaps = serializers.BooleanField()
    overlap_count = serializers.IntegerField()
    overlaps = serializers.ListField()


class NearbyFarmSerializer(serializers.Serializer):
    """Serializer for nearby farm results"""
    
    farm_id = serializers.CharField()
    farmer_name = serializers.CharField()
    pulse_id = serializers.CharField()
    size_acres = serializers.FloatField()
    county = serializers.CharField()
    distance_km = serializers.FloatField()
    satellite_verified = serializers.BooleanField()