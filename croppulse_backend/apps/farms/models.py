from django.contrib.gis.db import models as gis_models
from django.db import models
from django.core.validators import MinValueValidator
from apps.farmers.models import Farmer

class Farm(models.Model):
    """Farm location and boundary data with PostGIS support"""
    
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
    
    # Location Data
    boundary = gis_models.PolygonField(geography=True, help_text='Farm boundary polygon')
    center_point = gis_models.PointField(geography=True, help_text='Farm center GPS coordinates')
    
    # Size & Details
    size_acres = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    size_hectares = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    elevation = models.FloatField(null=True, blank=True, help_text='Elevation in meters above sea level')
    
    # Address
    county = models.CharField(max_length=100, db_index=True)
    sub_county = models.CharField(max_length=100)
    ward = models.CharField(max_length=100)
    
    # Verification Status
    satellite_verified = models.BooleanField(default=False, db_index=True)
    last_verified = models.DateTimeField(null=True, blank=True)
    verification_confidence = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MinValueValidator(1.0)],
        help_text='Satellite verification confidence score (0.0-1.0)'
    )
    
    # Ownership
    ownership_document = models.FileField(upload_to='land_documents/%Y/%m/', null=True, blank=True)
    land_ownership_type = models.CharField(
        max_length=50,
        choices=[('owned', 'Owned'), ('leased', 'Leased'), ('communal', 'Communal'), ('family', 'Family Land')],
        default='owned'
    )
    
    # Status
    is_primary = models.BooleanField(default=True, help_text='Primary farm for this farmer')
    is_active = models.BooleanField(default=True, db_index=True)
    
    # Metadata
    irrigation_available = models.BooleanField(default=False)
    water_source = models.CharField(max_length=100, null=True, blank=True, help_text='e.g., River, Borehole, Rain-fed')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # GPS Trace Data
    gps_trace_points = models.JSONField(default=list, help_text='Raw GPS points from mobile trace')
    gps_trace_quality = models.FloatField(null=True, blank=True, help_text='GPS trace quality score (0-100)')
    
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

    # Convenience methods
    def get_area_in_acres(self):
        return float(self.size_acres)
    
    def get_area_in_hectares(self):
        return float(self.size_hectares)
    
    def get_area_in_square_meters(self):
        return float(self.size_hectares) * 10000
    
    def get_perimeter_meters(self):
        if self.boundary:
            return self.boundary.length
        return 0
    
    def is_verified(self):
        return self.satellite_verified
    
    def needs_verification(self):
        if not self.satellite_verified:
            return True
        if self.last_verified:
            from django.utils import timezone
            from datetime import timedelta
            return timezone.now() - self.last_verified > timedelta(days=180)
        return True
    
    def get_center_coordinates(self):
        return {'latitude': self.center_point.y, 'longitude': self.center_point.x}
    
    def get_boundary_coordinates(self):
        if self.boundary:
            return [{'lat': point[1], 'lng': point[0]} for point in self.boundary.coords[0]]
        return []


class FarmBoundaryPoint(models.Model):
    """Individual points that make up farm boundary"""
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='boundary_points')
    point = gis_models.PointField(geography=True, help_text='GPS point coordinates')
    sequence = models.IntegerField(help_text='Order of points in polygon (0-indexed)')
    altitude = models.FloatField(null=True, blank=True, help_text='Altitude in meters')
    accuracy = models.FloatField(null=True, blank=True, help_text='GPS accuracy in meters')
    recorded_at = models.DateTimeField(null=True, blank=True, help_text='When this point was recorded')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'farm_boundary_points'
        ordering = ['sequence']
        unique_together = ['farm', 'sequence']
        indexes = [models.Index(fields=['farm', 'sequence'])]
        verbose_name = 'Farm Boundary Point'
        verbose_name_plural = 'Farm Boundary Points'
    
    def __str__(self):
        return f"{self.farm.farm_id} - Point {self.sequence}"
    
    def get_coordinates(self):
        return {'latitude': self.point.y, 'longitude': self.point.x, 'altitude': self.altitude}
