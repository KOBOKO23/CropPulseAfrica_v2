# apps/farms/models.py

from django.contrib.gis.db import models as gis_models
from django.db import models
from django.core.validators import MinValueValidator
from apps.farmers.models import Farmer


class Farm(models.Model):
    """
    Farm location and boundary data with PostGIS support
    """
    
    # Relationships
    farmer = models.ForeignKey(
        Farmer,
        on_delete=models.CASCADE,
        related_name='farms'
    )
    
    # Unique Identifier
    farm_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text='Unique farm identifier (e.g., FARM-882-01)'
    )
    
    # Location Data (PostGIS for geographical queries)
    boundary = gis_models.PolygonField(
        geography=True,
        help_text='Farm boundary polygon'
    )
    center_point = gis_models.PointField(
        geography=True,
        help_text='Farm center GPS coordinates'
    )
    
    # Size & Details
    size_acres = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    size_hectares = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    elevation = models.FloatField(
        null=True,
        blank=True,
        help_text='Elevation in meters above sea level'
    )
    
    # Soil & Terrain (NEW)
    soil_type = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text='Primary soil type (e.g., clay, loam, sandy)'
    )
    slope_percentage = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MinValueValidator(100)],
        help_text='Average slope percentage'
    )
    
    # Address
    county = models.CharField(max_length=100, db_index=True)
    sub_county = models.CharField(max_length=100)
    ward = models.CharField(max_length=100)
    
    # Verification Status
    satellite_verified = models.BooleanField(
        default=False,
        db_index=True
    )
    last_verified = models.DateTimeField(null=True, blank=True)
    verification_confidence = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MinValueValidator(1.0)],
        help_text='Satellite verification confidence score (0.0-1.0)'
    )
    
    # Boundary Accuracy (NEW)
    boundary_source = models.CharField(
        max_length=50,
        choices=[
            ('gps_walk', 'GPS Walk'),
            ('mobile_map', 'Mobile Map Drawing'),
            ('satellite_trace', 'Satellite Image Trace'),
            ('survey', 'Professional Survey'),
        ],
        default='mobile_map'
    )
    boundary_accuracy_meters = models.FloatField(
        null=True,
        blank=True,
        help_text='Estimated boundary accuracy in meters'
    )
    
    # Ownership
    ownership_document = models.FileField(
        upload_to='land_documents/%Y/%m/',
        null=True,
        blank=True
    )
    land_ownership_type = models.CharField(
        max_length=50,
        choices=[
            ('owned', 'Owned'),
            ('leased', 'Leased'),
            ('communal', 'Communal'),
            ('family', 'Family Land'),
        ],
        default='owned'
    )
    
    # Status
    is_primary = models.BooleanField(
        default=True,
        help_text='Primary farm for this farmer'
    )
    is_active = models.BooleanField(default=True, db_index=True)
    
    # Metadata (NEW)
    irrigation_available = models.BooleanField(default=False)
    water_source = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text='e.g., River, Borehole, Rain-fed'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'farms'
        ordering = ['-is_primary', '-created_at']
        indexes = [
            models.Index(fields=['farmer', 'is_primary']),
            models.Index(fields=['county', 'sub_county']),
            models.Index(fields=['satellite_verified']),
            models.Index(fields=['is_active']),
        ]
        verbose_name = 'Farm'
        verbose_name_plural = 'Farms'
    
    def __str__(self):
        return f"{self.farm_id} - {self.farmer.full_name}"
    
    def get_area_in_acres(self):
        """Get area in acres"""
        return float(self.size_acres)
    
    def get_area_in_hectares(self):
        """Get area in hectares"""
        return float(self.size_hectares)
    
    def get_area_in_square_meters(self):
        """Get area in square meters"""
        return float(self.size_hectares) * 10000
    
    def get_perimeter_meters(self):
        """Calculate farm perimeter in meters"""
        if self.boundary:
            # Get the linear ring (exterior boundary)
            return self.boundary.length
        return 0
    
    def is_verified(self):
        """Check if farm is satellite verified"""
        return self.satellite_verified
    
    def needs_verification(self):
        """Check if farm needs verification (unverified or old)"""
        if not self.satellite_verified:
            return True
        
        if self.last_verified:
            from django.utils import timezone
            from datetime import timedelta
            # Re-verify after 6 months
            return timezone.now() - self.last_verified > timedelta(days=180)
        
        return True
    
    def get_center_coordinates(self):
        """Get center point as dict"""
        return {
            'latitude': self.center_point.y,
            'longitude': self.center_point.x
        }
    
    def get_boundary_coordinates(self):
        """Get boundary coordinates as list of dicts"""
        if self.boundary:
            coords = self.boundary.coords[0]
            return [
                {'lat': point[1], 'lng': point[0]}
                for point in coords
            ]
        return []


class FarmBoundaryPoint(models.Model):
    """
    Individual points that make up farm boundary
    Stored for reference and reconstruction
    """
    
    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        related_name='boundary_points'
    )
    
    point = gis_models.PointField(
        geography=True,
        help_text='GPS point coordinates'
    )
    
    sequence = models.IntegerField(
        help_text='Order of points in polygon (0-indexed)'
    )
    
    # Point Metadata (NEW)
    altitude = models.FloatField(
        null=True,
        blank=True,
        help_text='Altitude in meters'
    )
    accuracy = models.FloatField(
        null=True,
        blank=True,
        help_text='GPS accuracy in meters'
    )
    recorded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When this point was recorded'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'farm_boundary_points'
        ordering = ['sequence']
        unique_together = ['farm', 'sequence']
        indexes = [
            models.Index(fields=['farm', 'sequence']),
        ]
        verbose_name = 'Farm Boundary Point'
        verbose_name_plural = 'Farm Boundary Points'
    
    def __str__(self):
        return f"{self.farm.farm_id} - Point {self.sequence}"
    
    def get_coordinates(self):
        """Get point coordinates as dict"""
        return {
            'latitude': self.point.y,
            'longitude': self.point.x,
            'altitude': self.altitude
        }