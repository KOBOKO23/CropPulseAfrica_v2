# apps/satellite/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.farms.models import Farm


class SatelliteScan(models.Model):
    """Record of satellite imagery analysis"""
    
    SATELLITE_TYPES = (
        ('sentinel1', 'Sentinel-1 SAR'),
        ('sentinel2', 'Sentinel-2 Optical'),
        ('landsat', 'Landsat'),
    )
    
    PROCESSING_STATUS = (
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    HEALTH_STATUS = (
        ('Healthy', 'Healthy'),
        ('Stressed', 'Stressed'),
        ('Poor', 'Poor'),
        ('Unknown', 'Unknown'),  # Used when scan fails or no optical data is available
    )
    
    # Identification
    scan_id = models.CharField(max_length=100, unique=True, db_index=True)
    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        related_name='satellite_scans'
    )
    
    # Satellite Details
    satellite_type = models.CharField(max_length=20, choices=SATELLITE_TYPES)
    acquisition_date = models.DateTimeField(db_index=True)
    processing_date = models.DateTimeField(auto_now_add=True)
    
    # Processing Status
    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS,
        default='completed'
    )
    processing_error = models.TextField(null=True, blank=True)
    
    # Image Data
    image_url = models.URLField(max_length=500, blank=True)
    cloud_cover_percentage = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    sar_penetrated_clouds = models.BooleanField(default=False)
    
    # Cloud Detection
    cloud_mask_url = models.URLField(max_length=500, null=True, blank=True)
    clear_pixel_percentage = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Vegetation Indices
    ndvi = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-1), MaxValueValidator(1)],
        help_text='Normalized Difference Vegetation Index (-1 to 1)'
    )
    evi = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-1), MaxValueValidator(3)],
        help_text='Enhanced Vegetation Index'
    )
    savi = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-1), MaxValueValidator(1)],
        help_text='Soil Adjusted Vegetation Index'
    )
    
    # Additional Indices
    ndwi = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-1), MaxValueValidator(1)],
        help_text='Normalized Difference Water Index'
    )
    msavi = models.FloatField(
        null=True,
        blank=True,
        help_text='Modified Soil Adjusted Vegetation Index'
    )
    
    # Soil & Crop Data
    soil_moisture = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Soil moisture percentage'
    )
    crop_stage = models.CharField(max_length=100, null=True, blank=True)
    crop_health_status = models.CharField(
        max_length=50,
        choices=HEALTH_STATUS,
        default='Healthy'
    )
    
    # SAR Specific Data
    vh_backscatter = models.FloatField(
        null=True,
        blank=True,
        help_text='VH polarization backscatter in dB'
    )
    vv_backscatter = models.FloatField(
        null=True,
        blank=True,
        help_text='VV polarization backscatter in dB'
    )
    vh_vv_ratio = models.FloatField(
        null=True,
        blank=True,
        help_text='VH/VV ratio for crop discrimination'
    )
    
    # Verification
    verified_farm_size = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    matches_declared_size = models.BooleanField(default=True)
    size_difference_percentage = models.FloatField(
        null=True,
        blank=True,
        help_text='Percentage difference between declared and verified size'
    )
    
    # Quality Metrics
    data_quality_score = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Overall data quality score (0-100)'
    )
    
    # Raw Data
    raw_satellite_data = models.JSONField(default=dict)
    
    # Metadata
    resolution_meters = models.FloatField(
        null=True,
        blank=True,
        help_text='Spatial resolution in meters'
    )
    orbit_direction = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text='Ascending or Descending'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'satellite_scans'
        ordering = ['-acquisition_date']
        indexes = [
            models.Index(fields=['farm', '-acquisition_date']),
            models.Index(fields=['satellite_type', '-acquisition_date']),
            models.Index(fields=['crop_health_status']),
            models.Index(fields=['processing_status']),
        ]
        verbose_name = 'Satellite Scan'
        verbose_name_plural = 'Satellite Scans'
    
    def __str__(self):
        return f"{self.scan_id} - {self.farm.farm_id}"
    
    def calculate_size_difference(self):
        """Calculate percentage difference in farm size"""
        declared = float(self.farm.size_acres)
        verified = float(self.verified_farm_size)
        
        if declared == 0:
            return 0
        
        diff = ((verified - declared) / declared) * 100
        return round(diff, 2)
    
    def is_high_quality(self):
        """Check if scan is high quality"""
        if self.data_quality_score:
            return self.data_quality_score >= 70
        
        # Fallback logic
        if self.cloud_cover_percentage > 50 and not self.sar_penetrated_clouds:
            return False
        
        if self.ndvi is None:
            return False
        
        return True
    
    def needs_rescan(self):
        """Check if scan needs to be redone"""
        from django.utils import timezone
        from datetime import timedelta
        
        # If failed or low quality
        if self.processing_status == 'failed' or not self.is_high_quality():
            return True
        
        # If older than 30 days
        if self.acquisition_date < timezone.now() - timedelta(days=30):
            return True
        
        return False


class NDVIHistory(models.Model):
    """Time-series NDVI data for trend analysis"""
    
    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        related_name='ndvi_history'
    )
    date = models.DateField(db_index=True)
    ndvi_value = models.FloatField(
        validators=[MinValueValidator(-1), MaxValueValidator(1)]
    )
    satellite_scan = models.ForeignKey(
        SatelliteScan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Additional Context
    evi_value = models.FloatField(null=True, blank=True)
    savi_value = models.FloatField(null=True, blank=True)
    soil_moisture = models.FloatField(null=True, blank=True)
    temperature = models.FloatField(
        null=True,
        blank=True,
        help_text='Temperature in Celsius'
    )
    rainfall_mm = models.FloatField(
        null=True,
        blank=True,
        help_text='Rainfall in mm'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ndvi_history'
        unique_together = ['farm', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['farm', '-date']),
            models.Index(fields=['date']),
        ]
        verbose_name = 'NDVI History'
        verbose_name_plural = 'NDVI History'
    
    def __str__(self):
        return f"{self.farm.farm_id} - {self.date} - NDVI: {self.ndvi_value:.3f}"
    
    def get_trend_indicator(self):
        """Get trend compared to previous entry"""
        previous = NDVIHistory.objects.filter(
            farm=self.farm,
            date__lt=self.date
        ).order_by('-date').first()
        
        if not previous:
            return 'stable'
        
        diff = self.ndvi_value - previous.ndvi_value
        
        if diff > 0.05:
            return 'improving'
        elif diff < -0.05:
            return 'declining'
        else:
            return 'stable'