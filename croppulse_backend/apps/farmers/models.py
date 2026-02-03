# apps/farmers/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.accounts.models import User


class Farmer(models.Model):
    """
    Farmer profile with Pulse ID and fraud detection status
    """
    
    FRAUD_STATUS_CHOICES = (
        ('clean', 'Clean'),
        ('flagged', 'Flagged'),
        ('under_review', 'Under Review'),
        ('verified', 'Verified Clean'),
        ('suspended', 'Suspended'),
    )
    
    # User Relationship
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='farmer_profile'
    )
    
    # Unique Identifier
    pulse_id = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text='Unique Pulse ID (e.g., CP-882-NK)'
    )
    
    # Personal Information
    full_name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    id_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text='National ID or Passport number'
    )
    
    # Location Information
    county = models.CharField(max_length=100, db_index=True)
    sub_county = models.CharField(max_length=100)
    nearest_town = models.CharField(max_length=100)
    
    # GPS Coordinates (NEW)
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        help_text='Home/primary location latitude'
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        help_text='Home/primary location longitude'
    )
    
    # Farming Details
    years_farming = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(80)]
    )
    primary_crop = models.CharField(max_length=100, db_index=True)
    secondary_crops = models.JSONField(
        default=list,
        help_text='List of secondary crops, e.g., ["beans", "vegetables"]'
    )
    
    # Farming Methods (NEW)
    farming_method = models.CharField(
        max_length=50,
        choices=[
            ('traditional', 'Traditional'),
            ('organic', 'Organic'),
            ('conventional', 'Conventional'),
            ('mixed', 'Mixed'),
        ],
        default='traditional'
    )
    
    irrigation_access = models.BooleanField(default=False)
    
    # Biometric Data
    voice_signature = models.TextField(
        null=True,
        blank=True,
        help_text='Voice biometric hash'
    )
    photo = models.ImageField(
        upload_to='farmer_photos/%Y/%m/',
        null=True,
        blank=True
    )
    
    # Fraud Detection (NEW)
    fraud_status = models.CharField(
        max_length=20,
        choices=FRAUD_STATUS_CHOICES,
        default='clean',
        db_index=True
    )
    fraud_notes = models.TextField(
        null=True,
        blank=True,
        help_text='Internal notes about fraud checks'
    )
    last_fraud_check = models.DateTimeField(null=True, blank=True)
    
    # Onboarding & Status
    onboarding_completed = models.BooleanField(default=False, db_index=True)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    
    # Metadata (NEW)
    preferred_language = models.CharField(
        max_length=10,
        choices=[
            ('en', 'English'),
            ('sw', 'Swahili'),
            ('ki', 'Kikuyu'),
        ],
        default='sw'
    )
    
    referral_source = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text='How farmer heard about CropPulse'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'farmers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['pulse_id']),
            models.Index(fields=['county', 'sub_county']),
            models.Index(fields=['primary_crop']),
            models.Index(fields=['fraud_status', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]
        verbose_name = 'Farmer'
        verbose_name_plural = 'Farmers'
    
    def __str__(self):
        return f"{self.full_name} ({self.pulse_id})"
    
    def get_full_location(self):
        """Get full location string"""
        return f"{self.nearest_town}, {self.sub_county}, {self.county}"
    
    def get_total_farm_size(self):
        """Calculate total farm size across all farms"""
        from decimal import Decimal
        total = self.farms.aggregate(
            total_size=models.Sum('size_acres')
        )['total_size']
        return total or Decimal('0.00')
    
    def get_crops_list(self):
        """Get all crops (primary + secondary)"""
        crops = [self.primary_crop]
        if self.secondary_crops:
            crops.extend(self.secondary_crops)
        return crops
    
    def is_fraud_flagged(self):
        """Check if farmer is flagged for fraud"""
        return self.fraud_status in ['flagged', 'under_review', 'suspended']
    
    def mark_onboarding_complete(self):
        """Mark onboarding as complete"""
        from django.utils import timezone
        self.onboarding_completed = True
        self.onboarding_completed_at = timezone.now()
        self.save(update_fields=['onboarding_completed', 'onboarding_completed_at'])


class VoiceRegistration(models.Model):
    """
    Voice recording data from farmer registration
    Stores audio files and transcription results
    """
    
    farmer = models.ForeignKey(
        Farmer,
        on_delete=models.CASCADE,
        related_name='voice_recordings'
    )
    
    audio_file = models.FileField(
        upload_to='voice_recordings/%Y/%m/',
        help_text='Original audio recording'
    )
    
    # Audio Metadata (NEW)
    audio_duration = models.FloatField(
        null=True,
        blank=True,
        help_text='Duration in seconds'
    )
    audio_format = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text='e.g., mp3, wav, ogg'
    )
    audio_size = models.IntegerField(
        null=True,
        blank=True,
        help_text='File size in bytes'
    )
    
    # Transcription
    transcript = models.TextField(help_text='Full transcription of audio')
    detected_language = models.CharField(
        max_length=20,
        help_text='Detected language code (en, sw, ki)'
    )
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text='Transcription confidence (0.0-1.0)'
    )
    
    # Processed Data
    processed_data = models.JSONField(
        default=dict,
        help_text='Structured data extracted from voice'
    )
    
    # Field Confidence Scores (NEW)
    field_confidence = models.JSONField(
        default=dict,
        help_text='Confidence scores per extracted field'
    )
    
    # Processing Status (NEW)
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    processing_error = models.TextField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'voice_registrations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['farmer', '-created_at']),
            models.Index(fields=['detected_language']),
            models.Index(fields=['processing_status']),
        ]
        verbose_name = 'Voice Registration'
        verbose_name_plural = 'Voice Registrations'
    
    def __str__(self):
        return f"Voice recording for {self.farmer.full_name} ({self.created_at.date()})"
    
    def get_confidence_percentage(self):
        """Get confidence as percentage"""
        return round(self.confidence_score * 100, 1)
    
    def is_high_confidence(self):
        """Check if confidence is above 90%"""
        return self.confidence_score >= 0.9
    
    def get_field_confidence(self, field_name):
        """Get confidence for a specific field"""
        return self.field_confidence.get(field_name, 0.0)


class FarmerNote(models.Model):
    """
    Internal notes about farmers (for banks/admins)
    NEW MODEL
    """
    
    farmer = models.ForeignKey(
        Farmer,
        on_delete=models.CASCADE,
        related_name='notes'
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='farmer_notes_created'
    )
    
    note_type = models.CharField(
        max_length=50,
        choices=[
            ('general', 'General'),
            ('fraud_alert', 'Fraud Alert'),
            ('verification', 'Verification'),
            ('loan_application', 'Loan Application'),
            ('customer_service', 'Customer Service'),
        ],
        default='general'
    )
    
    content = models.TextField()
    
    is_internal = models.BooleanField(
        default=True,
        help_text='If True, not visible to farmer'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'farmer_notes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['farmer', '-created_at']),
            models.Index(fields=['note_type']),
        ]
    
    def __str__(self):
        return f"Note for {self.farmer.full_name} by {self.created_by}"