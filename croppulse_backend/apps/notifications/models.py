# notifications/models.py

from django.db import models
from apps.accounts.models import User

class Notification(models.Model):
    """User notifications"""
    NOTIFICATION_TYPES = (
        ('score_update', 'Score Update'),
        ('loan_offer', 'Loan Offer'),
        ('farm_alert', 'Farm Alert'),
        ('weather', 'Weather Alert'),
        ('system', 'System Update'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Action Link
    action_url = models.CharField(max_length=500, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

# UPDATE: Add notofication type, priority