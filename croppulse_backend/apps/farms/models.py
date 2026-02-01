# farms/models.py

from django.contrib.gis.db import models as gis_models
from django.db import models
from apps.farmers.models import Farmer

class Farm(models.Model):
    """Farm location and boundary data"""
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name='farms')
    farm_id = models.CharField(max_length=50, unique=True)
    
    # Location Data (Using PostGIS for geographical queries)
    boundary = gis_models.PolygonField(geography=True)  # Farm boundary polygon
    center_point = gis_models.PointField(geography=True)  # Farm center GPS
    
    # Size & Details
    size_acres = models.DecimalField(max_digits=10, decimal_places=2)
    size_hectares = models.DecimalField(max_digits=10, decimal_places=2)
    elevation = models.FloatField(null=True, blank=True)  # meters above sea level
    
    # Address
    county = models.CharField(max_length=100)
    sub_county = models.CharField(max_length=100)
    ward = models.CharField(max_length=100)
    
    # Verification Status
    satellite_verified = models.BooleanField(default=False)
    last_verified = models.DateTimeField(null=True, blank=True)
    
    # Ownership
    ownership_document = models.FileField(upload_to='land_documents/', null=True, blank=True)
    is_primary = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'farms'
        indexes = [
            models.Index(fields=['farmer', 'is_primary']),
        ]


class FarmBoundaryPoint(models.Model):
    """Individual points that make up farm boundary"""
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='boundary_points')
    point = gis_models.PointField(geography=True)
    sequence = models.IntegerField()  # Order of points in polygon
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'farm_boundary_points'
        ordering = ['sequence']