# banks/models.py

from django.db import models
from apps.accounts.models import User

class Bank(models.Model):
    """Bank/Lender institution"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='bank_profile')
    bank_id = models.CharField(max_length=50, unique=True)
    
    # Institution Details
    name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=100)
    
    # API Access
    api_key = models.CharField(max_length=200, unique=True)
    api_calls_made = models.IntegerField(default=0)
    api_rate_limit = models.IntegerField(default=1000)  # per day
    
    # Subscription
    is_active = models.BooleanField(default=True)
    subscription_tier = models.CharField(max_length=50, default='basic')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'banks'

# UPDATE: Add API keys, webhooks, billing