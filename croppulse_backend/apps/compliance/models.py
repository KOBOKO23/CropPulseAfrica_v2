# apps/compliance/models.py
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.farmers.models import Farmer
from apps.farms.models import Farm
from core.mixins.timestamp_mixin import TimestampMixin
from core.mixins.tenant_mixin import TenantMixin
import uuid
from datetime import timedelta, date

class ExportPassport(TenantMixin, TimestampMixin, models.Model):
    """EUDR Digital Export Passport - Compliant with EU Regulation 2023/1115"""
    
    # Primary Identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    passport_id = models.CharField(max_length=50, unique=True, db_index=True, blank=True)
    
    # Relationships
    farmer = models.ForeignKey(
        Farmer, 
        on_delete=models.CASCADE, 
        related_name='export_passports'
    )
    farm = models.ForeignKey(
        Farm, 
        on_delete=models.CASCADE, 
        related_name='export_passports'
    )
    
    # EUDR Compliance
    dds_reference_number = models.CharField(
        max_length=100, 
        unique=True, 
        db_index=True,
        help_text="Due Diligence Statement Reference Number"
    )
    operator_name = models.CharField(max_length=255, help_text="EU Operator/Trader Name")
    operator_eori = models.CharField(max_length=50, blank=True, null=True, help_text="EORI Number")
    commodity_type = models.CharField(
        max_length=50,
        choices=[
            ('COFFEE', 'Coffee'),
            ('COCOA', 'Cocoa'),
            ('PALM_OIL', 'Palm Oil'),
            ('CATTLE', 'Cattle'),
            ('WOOD', 'Wood'),
            ('RUBBER', 'Rubber'),
            ('SOY', 'Soy'),
        ],
        default='COFFEE'
    )
    commodity_code = models.CharField(max_length=20, help_text="CN/HS Code")
    
    # Deforestation Verification
    baseline_date = models.DateField(
        default=date(2020, 12, 31),
        help_text="EUDR baseline cutoff date"
    )
    deforestation_status = models.CharField(
        max_length=50,
        choices=[
            ('CLEAR', 'Clear - No Deforestation'),
            ('UNDER_REVIEW', 'Under Review'),
            ('FLAGGED', 'Flagged - Deforestation Detected'),
            ('REMEDIATED', 'Remediated'),
        ],
        default='UNDER_REVIEW'
    )
    risk_level = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Low Risk'),
            ('STANDARD', 'Standard Risk'),
            ('HIGH', 'High Risk'),
        ],
        default='STANDARD'
    )
    satellite_proof_url = models.URLField(max_length=500, blank=True, null=True)
    satellite_analysis_date = models.DateField(auto_now_add=True)
    
    # Geolocation Data (EUDR Article 9)
    gps_coordinates = models.JSONField(
        help_text="Farm corner coordinates: [{lat, lng}, ...]",
        default=list
    )
    centroid_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        default=0.0,
    )
    centroid_longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        default=0.0,
    )
    farm_size_hectares = models.DecimalField(
        max_digits=10, 
        decimal_places=4,
        validators=[MinValueValidator(0.01)]
    )
    plot_area_sqm = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Land Tenure & Ownership
    land_ownership_verified = models.BooleanField(default=False)
    land_tenure_type = models.CharField(
        max_length=50,
        choices=[
            ('FREEHOLD', 'Freehold'),
            ('LEASEHOLD', 'Leasehold'),
            ('CUSTOMARY', 'Customary Rights'),
            ('COMMUNAL', 'Communal Land'),
            ('COOPERATIVE', 'Cooperative'),
        ],
        null=True,
        blank=True
    )
    land_document_url = models.URLField(max_length=500, null=True, blank=True)
    land_document_type = models.CharField(
        max_length=50,
        choices=[
            ('TITLE_DEED', 'Title Deed'),
            ('LEASE_AGREEMENT', 'Lease Agreement'),
            ('CUSTOMARY_CERT', 'Customary Certificate'),
            ('COOPERATIVE_CERT', 'Cooperative Certificate'),
        ],
        null=True,
        blank=True
    )
    
    # Production Data
    harvest_season = models.CharField(max_length=50, blank=True, null=True)
    estimated_production_kg = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0)]
    )
    
    # Blockchain Anchoring
    blockchain_hash = models.CharField(max_length=66, blank=True, null=True, db_index=True)
    blockchain_network = models.CharField(
        max_length=50,
        choices=[
            ('ETHEREUM', 'Ethereum'),
            ('POLYGON', 'Polygon'),
            ('AVALANCHE', 'Avalanche'),
            ('CELO', 'Celo'),
        ],
        null=True,
        blank=True
    )
    blockchain_tx_hash = models.CharField(max_length=66, blank=True, null=True)
    blockchain_timestamp = models.DateTimeField(null=True, blank=True)
    
    # Audit Trail (5-year retention as per EUDR)
    audit_trail = models.JSONField(
        default=list,
        help_text="Chronological log of all verification steps and updates"
    )
    
    # Validity & Status
    issued_date = models.DateField(auto_now_add=True)
    valid_until = models.DateField(help_text="Passport expires after 1 year typically", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.CharField(max_length=255, blank=True, null=True)
    verified_date = models.DateTimeField(null=True, blank=True)
    
    # QR Code & Documents
    qr_code = models.ImageField(upload_to='compliance/qr_codes/', null=True, blank=True)
    qr_data = models.JSONField(null=True, blank=True, help_text="Data encoded in QR code")
    pdf_document = models.FileField(upload_to='compliance/passports/', null=True, blank=True)
    
    # Translation Support
    language = models.CharField(
        max_length=10,
        choices=[
            ('en', 'English'),
            ('fr', 'French'),
            ('de', 'German'),
            ('es', 'Spanish'),
            ('sw', 'Swahili'),
        ],
        default='en'
    )
    
    # Additional Metadata
    notes = models.TextField(blank=True, null=True)
    internal_reference = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        db_table = 'export_passports'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['farmer', '-issued_date']),
            models.Index(fields=['deforestation_status', 'is_active']),
            models.Index(fields=['dds_reference_number']),
            models.Index(fields=['blockchain_hash']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Export Passport'
        verbose_name_plural = 'Export Passports'
    
    def __str__(self):
        return f"{self.passport_id} - {self.farmer.full_name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate passport ID if not set
        if not self.passport_id:
            self.passport_id = self.generate_passport_id()
        
        # Set valid_until to 1 year from issue if not set
        if not self.pk and not self.valid_until:  # Only on creation
            self.valid_until = timezone.now().date() + timedelta(days=365)
        
        super().save(*args, **kwargs)
    
    def generate_passport_id(self):
        """Generate unique passport ID: EU-{COUNTRY}-{YEAR}-{SEQUENCE}"""
        from django.db.models import Max
        
        country_code = 'KE'  # Default to Kenya, adjust based on your needs
        year = timezone.now().year
        
        # Get last sequence number for this year
        last_passport = ExportPassport.objects.filter(
            passport_id__startswith=f'EU-{country_code}-{year}-'
        ).aggregate(Max('passport_id'))
        
        if last_passport['passport_id__max']:
            last_seq = int(last_passport['passport_id__max'].split('-')[-1])
            new_seq = last_seq + 1
        else:
            new_seq = 1
        
        return f'EU-{country_code}-{year}-{new_seq:05d}'
    
    def add_audit_entry(self, action, user, details=None):
        """Add entry to audit trail"""
        entry = {
            'timestamp': timezone.now().isoformat(),
            'action': action,
            'user': user,
            'details': details or {}
        }
        if self.audit_trail is None:
            self.audit_trail = []
        self.audit_trail.append(entry)
        self.save(update_fields=['audit_trail', 'updated_at'])
    
    def is_expired(self):
        """Check if passport has expired"""
        if not self.valid_until:
            return False
        return timezone.now().date() > self.valid_until
    
    def days_until_expiry(self):
        """Calculate days remaining until expiry"""
        if not self.valid_until or self.is_expired():
            return 0
        return (self.valid_until - timezone.now().date()).days


class DeforestationCheck(TenantMixin, TimestampMixin, models.Model):
    """Historical deforestation verification using satellite imagery"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    farm = models.ForeignKey(
        Farm, 
        on_delete=models.CASCADE, 
        related_name='deforestation_checks'
    )
    export_passport = models.ForeignKey(
        ExportPassport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deforestation_checks'
    )
    
    # Check Details
    check_date = models.DateField(auto_now_add=True)
    check_type = models.CharField(
        max_length=50,
        choices=[
            ('INITIAL', 'Initial Assessment'),
            ('PERIODIC', 'Periodic Review'),
            ('TRIGGERED', 'Alert-Triggered'),
            ('RENEWAL', 'Passport Renewal'),
        ],
        default='INITIAL'
    )
    
    # Analysis Period
    analysis_start_date = models.DateField(help_text="Start of analysis period")
    analysis_end_date = models.DateField(help_text="End of analysis period")
    baseline_date = models.DateField(default=date(2020, 12, 31))
    
    # Forest Cover Analysis
    deforestation_detected = models.BooleanField(default=False)
    forest_cover_percentage = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Current forest cover percentage"
    )
    baseline_forest_cover = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
        help_text="Forest cover at baseline date"
    )
    change_in_forest_cover = models.FloatField(
        help_text="Percentage point change (can be negative)"
    )
    forest_loss_hectares = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Estimated forest loss in hectares"
    )
    
    # Satellite Data Sources
    satellite_provider = models.CharField(
        max_length=50,
        choices=[
            ('SENTINEL2', 'Sentinel-2'),
            ('LANDSAT8', 'Landsat 8'),
            ('PLANET', 'Planet Labs'),
            ('GLOBAL_FOREST_WATCH', 'Global Forest Watch'),
        ],
        default='SENTINEL2'
    )
    satellite_imagery_urls = models.JSONField(
        default=list,
        help_text="URLs to satellite imagery used in analysis"
    )
    cloud_cover_percentage = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # NDVI Analysis
    ndvi_baseline = models.FloatField(null=True, blank=True)
    ndvi_current = models.FloatField(null=True, blank=True)
    ndvi_change = models.FloatField(null=True, blank=True)
    
    # Risk Assessment
    risk_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0,
        help_text="Deforestation risk score (0-100)"
    )
    risk_factors = models.JSONField(
        default=list,
        help_text="List of identified risk factors"
    )
    
    # Results & Status
    status = models.CharField(
        max_length=50,
        choices=[
            ('PENDING', 'Analysis Pending'),
            ('IN_PROGRESS', 'Analysis In Progress'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed'),
            ('REQUIRES_REVIEW', 'Requires Manual Review'),
        ],
        default='PENDING'
    )
    result = models.CharField(
        max_length=50,
        choices=[
            ('CLEAR', 'Clear - No Deforestation'),
            ('WARNING', 'Warning - Minor Changes'),
            ('VIOLATION', 'Violation - Deforestation Detected'),
            ('INCONCLUSIVE', 'Inconclusive - Needs Review'),
        ],
        null=True,
        blank=True
    )
    
    # Analysis Details
    analysis_method = models.CharField(max_length=100, blank=True, null=True)
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        null=True,
        blank=True,
        help_text="Confidence in analysis result (0-1)"
    )
    analysis_metadata = models.JSONField(
        default=dict,
        help_text="Additional analysis parameters and results"
    )
    
    # Reviewer Information
    reviewed_by = models.CharField(max_length=255, blank=True, null=True)
    reviewed_date = models.DateTimeField(null=True, blank=True)
    reviewer_notes = models.TextField(blank=True, null=True)
    
    # Evidence & Documentation
    evidence_urls = models.JSONField(default=list)
    report_url = models.URLField(max_length=500, blank=True, null=True)
    
    class Meta:
        db_table = 'deforestation_checks'
        ordering = ['-check_date']
        indexes = [
            models.Index(fields=['farm', '-check_date']),
            models.Index(fields=['status', 'result']),
            models.Index(fields=['deforestation_detected']),
        ]
        verbose_name = 'Deforestation Check'
        verbose_name_plural = 'Deforestation Checks'
    
    def __str__(self):
        return f"Deforestation Check - {self.farm.farm_name} ({self.check_date})"
    
    def calculate_risk_score(self):
        """Calculate risk score based on various factors"""
        score = 0
        
        # Forest cover change
        if self.change_in_forest_cover < -10:
            score += 40
        elif self.change_in_forest_cover < -5:
            score += 25
        elif self.change_in_forest_cover < 0:
            score += 10
        
        # Deforestation detection
        if self.deforestation_detected:
            score += 30
        
        # NDVI decline
        if self.ndvi_change and self.ndvi_change < -0.2:
            score += 20
        elif self.ndvi_change and self.ndvi_change < -0.1:
            score += 10
        
        # Confidence penalty
        if self.confidence_score and self.confidence_score < 0.7:
            score += 10
        
        self.risk_score = min(score, 100)
        return self.risk_score


class ComplianceDocument(TenantMixin, TimestampMixin, models.Model):
    """Supporting compliance documents"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    export_passport = models.ForeignKey(
        ExportPassport,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    # Document Details
    document_type = models.CharField(
        max_length=50,
        choices=[
            ('LAND_TITLE', 'Land Title'),
            ('SATELLITE_REPORT', 'Satellite Analysis Report'),
            ('AUDIT_CERTIFICATE', 'Audit Certificate'),
            ('FARMERS_DECLARATION', 'Farmer\'s Declaration'),
            ('PHOTO_EVIDENCE', 'Photo Evidence'),
            ('GPS_TRACE', 'GPS Trace'),
            ('OTHER', 'Other'),
        ]
    )
    document_name = models.CharField(max_length=255)
    document_file = models.FileField(upload_to='compliance/documents/')
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    file_hash = models.CharField(max_length=64, blank=True, null=True, help_text="SHA-256 hash")
    
    # Metadata
    description = models.TextField(blank=True, null=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.CharField(max_length=255)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verified_by = models.CharField(max_length=255, blank=True, null=True)
    verified_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'compliance_documents'
        ordering = ['-upload_date']
        verbose_name = 'Compliance Document'
        verbose_name_plural = 'Compliance Documents'
    
    def __str__(self):
        return f"{self.document_type} - {self.document_name}"


class AuditLog(TenantMixin, TimestampMixin, models.Model):
    """Comprehensive audit logging for compliance"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # What was changed
    entity_type = models.CharField(
        max_length=50,
        choices=[
            ('EXPORT_PASSPORT', 'Export Passport'),
            ('DEFORESTATION_CHECK', 'Deforestation Check'),
            ('COMPLIANCE_DOCUMENT', 'Compliance Document'),
        ]
    )
    entity_id = models.UUIDField()
    
    # Who made the change
    user_id = models.CharField(max_length=255)
    user_name = models.CharField(max_length=255)
    user_role = models.CharField(max_length=100, blank=True, null=True)
    
    # What happened
    action = models.CharField(
        max_length=50,
        choices=[
            ('CREATE', 'Created'),
            ('UPDATE', 'Updated'),
            ('DELETE', 'Deleted'),
            ('VERIFY', 'Verified'),
            ('APPROVE', 'Approved'),
            ('REJECT', 'Rejected'),
            ('EXPORT', 'Exported'),
            ('BLOCKCHAIN_ANCHOR', 'Blockchain Anchored'),
            ('DEFORESTATION_CHECK', 'Deforestation Check'),
        ]
    )
    
    # Change details
    changes = models.JSONField(
        default=dict,
        help_text="Before/after values for updates"
    )
    reason = models.TextField(blank=True, null=True)
    
    # Context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'audit_logs_compliance'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user_id', '-timestamp']),
        ]
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
    
    def __str__(self):
        return f"{self.action} - {self.entity_type} by {self.user_name}"


class TranslationCache(models.Model):
    """Cache for translated compliance documents"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    source_language = models.CharField(max_length=10)
    target_language = models.CharField(max_length=10)
    source_text = models.TextField()
    translated_text = models.TextField()
    
    # Caching
    cache_key = models.CharField(max_length=64, unique=True, db_index=True)
    hit_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'translation_cache'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['cache_key']),
            models.Index(fields=['expires_at']),
        ]