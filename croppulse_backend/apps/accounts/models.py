# apps/accounts/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """Extended user model"""
    USER_TYPES = (
        ('farmer', 'Farmer'),
        ('bank', 'Bank/Lender'),
        ('admin', 'Administrator'),
    )
    
    user_type = models.CharField(max_length=10, choices=USER_TYPES)
    phone_number = models.CharField(max_length=20, unique=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
    
    def __str__(self):
        return self.username