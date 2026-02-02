# farmers/models.py

from django.db import models
from apps.accounts.models import User

class Farmer(models.Model):
    """Farmer profile with Pulse ID"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='farmer_profile')
    pulse_id = models.CharField(max_length=20, unique=True, db_index=True)  # e.g., CP-882-NK
    
    # Personal Information
    full_name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    id_number = models.CharField(max_length=50, unique=True)
    county = models.CharField(max_length=100)
    sub_county = models.CharField(max_length=100)
    nearest_town = models.CharField(max_length=100)
    
    # Farming Details
    years_farming = models.IntegerField()
    primary_crop = models.CharField(max_length=100)
    secondary_crops = models.JSONField(default=list)  # ["beans", "vegetables"]
    
    # Biometric Data
    voice_signature = models.TextField(null=True, blank=True)  # Voice biometric hash
    photo = models.ImageField(upload_to='farmer_photos/', null=True, blank=True)
    
    # Status
    onboarding_completed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'farmers'
        indexes = [
            models.Index(fields=['pulse_id']),
            models.Index(fields=['county', 'sub_county']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.pulse_id})"


class VoiceRegistration(models.Model):
    """Voice recording data from farmer registration"""
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name='voice_recordings')
    audio_file = models.FileField(upload_to='voice_recordings/')
    transcript = models.TextField()
    detected_language = models.CharField(max_length=20)  # Swahili, Kikuyu, English
    confidence_score = models.FloatField()
    processed_data = models.JSONField()  # Extracted structured data
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'voice_registrations'


# update farmers/models.py to add fraud_status field to Farmer model