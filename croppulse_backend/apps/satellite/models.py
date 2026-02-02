# satellite/models.py

from django.db import models
from apps.farms.models import Farm

class SatelliteScan(models.Model):
    """Record of satellite imagery analysis"""
    SATELLITE_TYPES = (
        ('sentinel1', 'Sentinel-1 SAR'),
        ('sentinel2', 'Sentinel-2 Optical'),
        ('landsat', 'Landsat'),
    )
    
    scan_id = models.CharField(max_length=100, unique=True)
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='satellite_scans')
    
    # Satellite Details
    satellite_type = models.CharField(max_length=20, choices=SATELLITE_TYPES)
    acquisition_date = models.DateTimeField()  # When satellite captured image
    processing_date = models.DateTimeField(auto_now_add=True)
    
    # Image Data
    image_url = models.URLField(max_length=500)
    cloud_cover_percentage = models.FloatField()
    sar_penetrated_clouds = models.BooleanField(default=False)
    
    # Vegetation Indices
    ndvi = models.FloatField(null=True, blank=True)  # Normalized Difference Vegetation Index
    evi = models.FloatField(null=True, blank=True)   # Enhanced Vegetation Index
    savi = models.FloatField(null=True, blank=True)  # Soil Adjusted Vegetation Index
    
    # Soil & Crop Data
    soil_moisture = models.FloatField(null=True, blank=True)  # Percentage
    crop_stage = models.CharField(max_length=100, null=True, blank=True)
    crop_health_status = models.CharField(max_length=50)  # Healthy, Stressed, Poor
    
    # Verification
    verified_farm_size = models.DecimalField(max_digits=10, decimal_places=2)
    matches_declared_size = models.BooleanField(default=True)
    
    # Raw Data
    raw_satellite_data = models.JSONField()  # Full satellite response
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'satellite_scans'
        indexes = [
            models.Index(fields=['farm', '-acquisition_date']),
        ]


class NDVIHistory(models.Model):
    """Time-series NDVI data for trend analysis"""
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='ndvi_history')
    date = models.DateField()
    ndvi_value = models.FloatField()
    satellite_scan = models.ForeignKey(SatelliteScan, on_delete=models.SET_NULL, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ndvi_history'
        unique_together = ['farm', 'date']
        indexes = [
            models.Index(fields=['farm', '-date']),
        ]

    # update: Add scan status, cloud cover, and SAR penetration fields to SatelliteScan model