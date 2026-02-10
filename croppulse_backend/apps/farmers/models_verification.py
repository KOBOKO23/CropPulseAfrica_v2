# Ground-truth weather reporting models

from django.db import models
from apps.farmers.models import Farmer
from apps.farms.models import Farm

class GroundTruthReport(models.Model):
    """Farmer-reported actual weather conditions"""
    
    WEATHER_CHOICES = [
        ('clear', 'Clear/Sunny'),
        ('cloudy', 'Cloudy'),
        ('light_rain', 'Light Rain'),
        ('heavy_rain', 'Heavy Rain'),
        ('drizzle', 'Drizzle'),
        ('storm', 'Storm/Thunder'),
        ('fog', 'Fog'),
        ('windy', 'Very Windy'),
    ]
    
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name='weather_reports')
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, null=True, blank=True)
    
    # Report details
    weather_condition = models.CharField(max_length=20, choices=WEATHER_CHOICES)
    temperature_feel = models.CharField(max_length=20, choices=[
        ('very_cold', 'Very Cold'),
        ('cold', 'Cold'),
        ('normal', 'Normal'),
        ('hot', 'Hot'),
        ('very_hot', 'Very Hot'),
    ])
    rainfall_amount = models.CharField(max_length=20, choices=[
        ('none', 'No Rain'),
        ('light', 'Light (<5mm)'),
        ('moderate', 'Moderate (5-20mm)'),
        ('heavy', 'Heavy (>20mm)'),
    ], default='none')
    
    # Timing
    report_time = models.DateTimeField(auto_now_add=True)
    weather_time = models.DateTimeField(help_text="When the weather occurred")
    
    # Additional info
    notes = models.TextField(blank=True)
    photo = models.ImageField(upload_to='weather_reports/', null=True, blank=True)
    
    # Verification
    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-report_time']
        indexes = [
            models.Index(fields=['farmer', '-report_time']),
            models.Index(fields=['weather_time']),
        ]
    
    def __str__(self):
        return f"{self.farmer.user.username} - {self.weather_condition} at {self.weather_time}"


class ProofOfAction(models.Model):
    """Farmer proof of following agricultural advice"""
    
    ACTION_TYPES = [
        ('fertilizer', 'Applied Fertilizer'),
        ('pesticide', 'Applied Pesticide'),
        ('irrigation', 'Irrigated Farm'),
        ('planting', 'Planted Crops'),
        ('weeding', 'Weeded Farm'),
        ('harvesting', 'Harvested Crops'),
        ('soil_prep', 'Prepared Soil'),
        ('other', 'Other Action'),
    ]
    
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name='actions')
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE)
    
    # Action details
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    description = models.TextField()
    action_date = models.DateTimeField()
    
    # Proof
    photo = models.ImageField(upload_to='proof_of_action/')
    voice_note = models.FileField(upload_to='voice_notes/', null=True, blank=True)
    
    # Verification
    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Scoring
    points_earned = models.IntegerField(default=0)
    
    # Blockchain (future)
    blockchain_hash = models.CharField(max_length=66, blank=True, help_text="Celo transaction hash")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-action_date']
        indexes = [
            models.Index(fields=['farmer', '-action_date']),
            models.Index(fields=['verified']),
        ]
    
    def __str__(self):
        return f"{self.farmer.user.username} - {self.action_type} on {self.action_date.date()}"
