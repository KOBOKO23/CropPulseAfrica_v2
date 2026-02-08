# apps/accounts/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from .managers import UserManager


class User(AbstractUser):
    """
    Extended user model with multi-tenant support
    """

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'phone_number', 'user_type']

    objects = UserManager()
    
    USER_TYPES = (
        ('farmer', 'Farmer'),
        ('bank', 'Bank/Lender'),
        ('exporter', 'Exporter'),  # NEW: Added exporter type
        ('admin', 'Administrator'),
    )
    
    # Custom fields
    user_type = models.CharField(
        max_length=10,
        choices=USER_TYPES,
        db_index=True
    )
    
    # NEW: Phone validator
    phone_validator = RegexValidator(
        regex=r'^\+254\d{9}$',
        message="Phone number must be in format: '+254XXXXXXXXX'"
    )
    
    phone_number = models.CharField(
        max_length=20,
        unique=True,
        validators=[phone_validator],  # NEW: Added validator
        db_index=True
    )
    
    is_verified = models.BooleanField(
        default=False,
        help_text='Phone number verified'
    )
    
    # NEW: Additional profile fields
    profile_image = models.URLField(
        max_length=500,
        null=True,
        blank=True
    )
    
    country_code = models.CharField(
        max_length=3,
        default='KE',
        help_text='ISO country code'
    )
    
    language_preference = models.CharField(
        max_length=10,
        default='en',
        choices=[
            ('en', 'English'),
            ('sw', 'Swahili'),
            ('ki', 'Kikuyu'),
        ]
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(null=True, blank=True)  # NEW
    
    # NEW: Use custom manager
    objects = UserManager()
    
    class Meta:
        db_table = 'users'
        ordering = ['-date_joined']
        # NEW: Added indexes for performance
        indexes = [
            models.Index(fields=['user_type', 'is_verified']),
            models.Index(fields=['email']),
            models.Index(fields=['phone_number']),
        ]
    
    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"  # UPDATED
    
    # NEW: Get full name method
    def get_full_name(self):
        """Return user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    # NEW: Update last activity
    def update_last_activity(self):
        """Update last activity timestamp"""
        from django.utils import timezone
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])


# NEW MODEL: AuditLog
class AuditLog(models.Model):
    """
    Audit log for tracking user actions
    """
    
    ACTION_CHOICES = (
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('password_change', 'Password Change'),
        ('profile_update', 'Profile Update'),
        ('api_call', 'API Call'),
        ('data_access', 'Data Access'),
        ('data_export', 'Data Export'),
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs'
    )
    
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'audit_logs_accounts'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.timestamp}"