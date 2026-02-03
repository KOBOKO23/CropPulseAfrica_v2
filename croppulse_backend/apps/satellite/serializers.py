# apps/satellite/serializers.py

from rest_framework import serializers
from .models import SatelliteScan, NDVIHistory
from apps.farms.models import Farm


class SatelliteScanSerializer(serializers.ModelSerializer):
    """Serializer for SatelliteScan model"""
    
    farm_id = serializers.CharField(source='farm.farm_id', read_only=True)
    farmer_name = serializers.CharField(source='farm.farmer.full_name', read_only=True)
    pulse_id = serializers.CharField(source='farm.farmer.pulse_id', read_only=True)
    
    class Meta:
        model = SatelliteScan
        fields = [
            'id',
            'scan_id',
            'farm',
            'farm_id',
            'farmer_name',
            'pulse_id',
            'satellite_type',
            'acquisition_date',
            'processing_date',
            'processing_status',
            'processing_error',
            'image_url',
            'cloud_cover_percentage',
            'sar_penetrated_clouds',
            'cloud_mask_url',
            'clear_pixel_percentage',
            'ndvi',
            'evi',
            'savi',
            'ndwi',
            'msavi',
            'soil_moisture',
            'crop_stage',
            'crop_health_status',
            'vh_backscatter',
            'vv_backscatter',
            'vh_vv_ratio',
            'verified_farm_size',
            'matches_declared_size',
            'size_difference_percentage',
            'data_quality_score',
            'resolution_meters',
            'orbit_direction',
            'raw_satellite_data',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'scan_id',
            'processing_date',
            'created_at',
        ]


class SatelliteScanDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer with nested farm information"""
    
    farm_details = serializers.SerializerMethodField()
    vegetation_indices = serializers.SerializerMethodField()
    health_assessment = serializers.SerializerMethodField()
    sar_metrics = serializers.SerializerMethodField()
    
    class Meta:
        model = SatelliteScan
        fields = [
            'id',
            'scan_id',
            'farm_details',
            'satellite_type',
            'acquisition_date',
            'processing_date',
            'processing_status',
            'image_url',
            'cloud_cover_percentage',
            'sar_penetrated_clouds',
            'cloud_mask_url',
            'clear_pixel_percentage',
            'vegetation_indices',
            'sar_metrics',
            'health_assessment',
            'verified_farm_size',
            'matches_declared_size',
            'size_difference_percentage',
            'data_quality_score',
            'resolution_meters',
            'orbit_direction',
            'created_at',
        ]
    
    def get_farm_details(self, obj):
        """Get farm details"""
        return {
            'farm_id': obj.farm.farm_id,
            'farmer_name': obj.farm.farmer.full_name,
            'pulse_id': obj.farm.farmer.pulse_id,
            'declared_size': float(obj.farm.size_acres),
            'county': obj.farm.county,
            'location': {
                'latitude': obj.farm.center_point.y if obj.farm.center_point else None,
                'longitude': obj.farm.center_point.x if obj.farm.center_point else None,
            },
        }
    
    def get_vegetation_indices(self, obj):
        """Get all vegetation indices including ndwi and msavi"""
        return {
            'ndvi': obj.ndvi,
            'evi': obj.evi,
            'savi': obj.savi,
            'ndwi': obj.ndwi,
            'msavi': obj.msavi,
            'interpretation': self._interpret_ndvi(obj.ndvi),
        }
    
    def get_sar_metrics(self, obj):
        """Get SAR-specific metrics"""
        return {
            'vh_backscatter': obj.vh_backscatter,
            'vv_backscatter': obj.vv_backscatter,
            'vh_vv_ratio': obj.vh_vv_ratio,
            'orbit_direction': obj.orbit_direction,
        }
    
    def get_health_assessment(self, obj):
        """Get health assessment details"""
        return {
            'status': obj.crop_health_status,
            'soil_moisture': obj.soil_moisture,
            'crop_stage': obj.crop_stage,
            'recommendation': self._get_recommendation(obj),
        }
    
    def _interpret_ndvi(self, ndvi):
        """Interpret NDVI value"""
        if ndvi is None:
            return 'No data available'
        elif ndvi >= 0.75:
            return 'Excellent - Dense healthy vegetation'
        elif ndvi >= 0.60:
            return 'Good - Healthy vegetation'
        elif ndvi >= 0.40:
            return 'Moderate - Some vegetation stress'
        elif ndvi >= 0.20:
            return 'Poor - Significant vegetation stress'
        else:
            return 'Very Poor - Little to no vegetation'
    
    def _get_recommendation(self, obj):
        """Generate recommendation based on scan data"""
        recommendations = []
        
        if obj.ndvi and obj.ndvi < 0.50:
            recommendations.append('Consider irrigation or fertilization')
        
        if obj.soil_moisture and obj.soil_moisture < 30:
            recommendations.append('Low soil moisture - irrigation recommended')
        
        if obj.crop_health_status == 'Stressed':
            recommendations.append('Monitor crop closely for pests or disease')
        
        if obj.ndwi is not None and obj.ndwi > 0.3:
            recommendations.append('High water index detected - check for waterlogging')
        
        if not recommendations:
            recommendations.append('Continue current farming practices')
        
        return recommendations


class SatelliteScanCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/triggering satellite scans"""
    
    farm_id = serializers.CharField(write_only=True)
    
    class Meta:
        model = SatelliteScan
        fields = ['farm_id']
    
    def validate_farm_id(self, value):
        """Validate farm exists"""
        try:
            farm = Farm.objects.get(farm_id=value)
            return farm
        except Farm.DoesNotExist:
            raise serializers.ValidationError(f"Farm with ID {value} does not exist")
    
    def create(self, validated_data):
        """Trigger satellite scan task"""
        from .tasks import process_satellite_scan
        
        farm = validated_data['farm_id']
        
        # Trigger async task
        task = process_satellite_scan.delay(farm.id)
        
        # Return a placeholder response
        return {
            'farm_id': farm.farm_id,
            'task_id': task.id,
            'status': 'Scan queued for processing',
        }


class NDVIHistorySerializer(serializers.ModelSerializer):
    """Serializer for NDVI History — includes all context fields from the model"""
    
    farm_id = serializers.CharField(source='farm.farm_id', read_only=True)
    scan_id = serializers.CharField(source='satellite_scan.scan_id', read_only=True, allow_null=True)
    trend_indicator = serializers.SerializerMethodField()
    
    class Meta:
        model = NDVIHistory
        fields = [
            'id',
            'farm',
            'farm_id',
            'date',
            'ndvi_value',
            'evi_value',
            'savi_value',
            'soil_moisture',
            'temperature',
            'rainfall_mm',
            'satellite_scan',
            'scan_id',
            'trend_indicator',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_trend_indicator(self, obj):
        """Expose the model helper as a read-only computed field"""
        return obj.get_trend_indicator()


class NDVITrendSerializer(serializers.Serializer):
    """Serializer for NDVI trend analysis"""
    
    farm_id = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    data_points = serializers.ListField(child=serializers.DictField())
    trend = serializers.CharField()
    average_ndvi = serializers.FloatField()
    min_ndvi = serializers.FloatField()
    max_ndvi = serializers.FloatField()
    change_percentage = serializers.FloatField()


class FarmHealthSummarySerializer(serializers.Serializer):
    """Serializer for farm health summary"""
    
    farm_id = serializers.CharField()
    latest_scan = SatelliteScanSerializer()
    ndvi_trend = serializers.DictField()
    health_score = serializers.IntegerField()
    recommendations = serializers.ListField(child=serializers.CharField())
    last_updated = serializers.DateTimeField()


class BulkScanRequestSerializer(serializers.Serializer):
    """Serializer for bulk scan requests"""
    
    farm_ids = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
        max_length=50,
    )
    
    def validate_farm_ids(self, value):
        """Validate all farm IDs exist"""
        existing_farms = Farm.objects.filter(farm_id__in=value).values_list('farm_id', flat=True)
        missing = set(value) - set(existing_farms)
        
        if missing:
            raise serializers.ValidationError(
                f"The following farm IDs do not exist: {', '.join(missing)}"
            )
        
        return value


class SatelliteStatusSerializer(serializers.Serializer):
    """Serializer for satellite scan status"""
    
    scan_id = serializers.CharField()
    status = serializers.ChoiceField(choices=[
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ])
    progress = serializers.IntegerField(min_value=0, max_value=100)
    message = serializers.CharField()
    estimated_completion = serializers.DateTimeField(allow_null=True)


class CloudCoverageSerializer(serializers.Serializer):
    """Serializer for cloud coverage analysis"""
    
    farm_id = serializers.CharField()
    date_range = serializers.DictField()
    average_cloud_cover = serializers.FloatField()
    optimal_scan_dates = serializers.ListField(child=serializers.DateField())
    sar_availability = serializers.BooleanField()