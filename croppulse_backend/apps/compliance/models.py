# compliance/models.py

from django.db import models
from apps.farmers.models import Farmer
from apps.farms.models import Farm

class ExportPassport(models.Model):
    """EUDR Digital Export Passport"""
    passport_id = models.CharField(max_length=50, unique=True)  # e.g., EU-KE-2026-7821
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name='export_passports')
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='export_passports')
    
    # EUDR Compliance
    dds_reference_number = models.CharField(max_length=100, unique=True)
    
    # Deforestation Verification
    baseline_date = models.DateField(default='2020-12-31')  # EUDR cutoff
    deforestation_status = models.CharField(max_length=50)  # Clear, Under Review, Flagged
    satellite_proof_url = models.URLField(max_length=500)
    
    # Geolocation Data
    gps_coordinates = models.JSONField()  # {lat, lng}
    farm_size_hectares = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Land Tenure
    land_ownership_verified = models.BooleanField(default=False)
    land_document_url = models.URLField(max_length=500, null=True, blank=True)
    
    # Audit Trail
    audit_trail = models.JSONField(default=list)  # 5-year history
    
    # Validity
    issued_date = models.DateField(auto_now_add=True)
    valid_until = models.DateField()
    is_active = models.BooleanField(default=True)
    
    # QR Code
    qr_code = models.ImageField(upload_to='qr_codes/', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'export_passports'
        indexes = [
            models.Index(fields=['farmer', '-issued_date']),
        ]


class DeforestationCheck(models.Model):
    """Historical deforestation verification"""
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='deforestation_checks')
    check_date = models.DateField()
    
    # Analysis Period
    analysis_start_date = models.DateField()
    analysis_end_date = models.DateField()
    
    # Results
    deforestation_detected = models.BooleanField(default=False)
    forest_cover_percentage = models.FloatField()
    change_in_forest_cover = models.FloatField()  # Can be negative
    
    # Evidence
    satellite_imagery_urls = models.JSONField(default=list)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'deforestation_checks'

# UPDATE: Add blockchain hash, QR data