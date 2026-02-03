# apps/accounts/managers.py

from django.contrib.auth.models import BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """
    Custom user manager for User model with email as unique identifier
    """
    
    def create_user(self, username, email, phone_number, password=None, **extra_fields):
        """
        Create and save a regular user with the given details
        """
        if not email:
            raise ValueError('Users must have an email address')
        
        if not phone_number:
            raise ValueError('Users must have a phone number')
        
        if not username:
            raise ValueError('Users must have a username')
        
        # Normalize email
        email = self.normalize_email(email)
        
        # Normalize phone number to international format
        phone_number = self._normalize_phone_number(phone_number)
        
        # Set default user_type if not provided
        if 'user_type' not in extra_fields:
            extra_fields['user_type'] = 'farmer'
        
        # Create user instance
        user = self.model(
            username=username,
            email=email,
            phone_number=phone_number,
            **extra_fields
        )
        
        # Set password
        user.set_password(password)
        user.save(using=self._db)
        
        return user
    
    def create_superuser(self, username, email, phone_number, password=None, **extra_fields):
        """
        Create and save a superuser with admin privileges
        """
        # Set required superuser fields
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('user_type', 'admin')
        
        # Validate superuser fields
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')
        
        return self.create_user(username, email, phone_number, password, **extra_fields)
    
    def _normalize_phone_number(self, phone_number):
        """
        Normalize phone number to international format (+254XXXXXXXXX)
        """
        # Remove spaces, dashes, and parentheses
        cleaned = phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Handle different formats
        if cleaned.startswith('+254'):
            return cleaned
        elif cleaned.startswith('254'):
            return '+' + cleaned
        elif cleaned.startswith('0'):
            return '+254' + cleaned[1:]
        else:
            # Assume it's a local number (9 digits)
            if len(cleaned) == 9:
                return '+254' + cleaned
        
        return cleaned
    
    def get_farmers(self):
        """Get all farmer users"""
        return self.filter(user_type='farmer')
    
    def get_banks(self):
        """Get all bank users"""
        return self.filter(user_type='bank')
    
    def get_exporters(self):
        """Get all exporter users"""
        return self.filter(user_type='exporter')
    
    def get_admins(self):
        """Get all admin users"""
        return self.filter(user_type='admin')
    
    def get_verified_users(self):
        """Get all verified users"""
        return self.filter(is_verified=True, is_active=True)
    
    def get_unverified_users(self):
        """Get all unverified users"""
        return self.filter(is_verified=False, is_active=True)
    
    def get_active_users(self):
        """Get all active users"""
        return self.filter(is_active=True)
    
    def search_users(self, query):
        """
        Search users by username, email, phone, or name
        """
        return self.filter(
            models.Q(username__icontains=query) |
            models.Q(email__icontains=query) |
            models.Q(phone_number__icontains=query) |
            models.Q(first_name__icontains=query) |
            models.Q(last_name__icontains=query)
        )