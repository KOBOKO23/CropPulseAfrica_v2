# apps/accounts/permissions.py

from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to only allow owners of an object or admins to access it
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin users can access everything
        if request.user and request.user.is_staff:
            return True
        
        # Check if object has 'user' attribute (for related objects)
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Otherwise, check if object is the user itself
        return obj == request.user


class IsFarmer(permissions.BasePermission):
    """
    Permission to only allow farmers to access
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type == 'farmer'
        )


class IsBank(permissions.BasePermission):
    """
    Permission to only allow banks to access
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type == 'bank'
        )


class IsExporter(permissions.BasePermission):
    """
    Permission to only allow exporters to access
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type == 'exporter'
        )


class IsAdminUser(permissions.BasePermission):
    """
    Permission to only allow admin users to access
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type == 'admin'
        )


class IsBankOrAdmin(permissions.BasePermission):
    """
    Permission to allow banks and admins to access
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type in ['bank', 'admin']
        )


class IsVerifiedUser(permissions.BasePermission):
    """
    Permission to only allow verified users to access
    """
    
    message = 'You must verify your phone number to access this resource.'
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_verified
        )


class IsActiveUser(permissions.BasePermission):
    """
    Permission to only allow active users to access
    """
    
    message = 'Your account has been deactivated.'
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_active
        )


class CanAccessBank(permissions.BasePermission):
    """
    Permission to check if user can access bank-specific data
    Multi-tenant isolation for banks
    """
    
    def has_permission(self, request, view):
        # Admins can access all banks
        if request.user.user_type == 'admin':
            return True
        
        # Banks can only access their own data
        return request.user.user_type == 'bank'
    
    def has_object_permission(self, request, view, obj):
        # Admins can access everything
        if request.user.user_type == 'admin':
            return True
        
        # Banks can only access their own records
        if request.user.user_type == 'bank':
            # Check if object has bank relationship
            if hasattr(obj, 'bank'):
                return obj.bank.user == request.user
            # Check if object is bank profile itself
            if hasattr(obj, 'user'):
                return obj.user == request.user
        
        return False


class CanAccessFarmer(permissions.BasePermission):
    """
    Permission to check if user can access farmer data
    """
    
    def has_permission(self, request, view):
        # Farmers can access their own data
        if request.user.user_type == 'farmer':
            return True
        
        # Banks and admins can access farmer data
        if request.user.user_type in ['bank', 'admin', 'exporter']:
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        # Farmers can only access their own data
        if request.user.user_type == 'farmer':
            if hasattr(obj, 'user'):
                return obj.user == request.user
            return obj == request.user
        
        # Banks and admins can access any farmer
        if request.user.user_type in ['bank', 'admin', 'exporter']:
            return True
        
        return False


class HasAPIKey(permissions.BasePermission):
    """
    Permission to check if request has valid API key (for banks)
    """
    
    message = 'Valid API key required'
    
    def has_permission(self, request, view):
        # Check for API key in headers
        api_key = request.META.get('HTTP_X_API_KEY')
        
        if not api_key:
            return False
        
        # Import here to avoid circular imports
        from apps.banks.models import BankAPIKey
        
        # Validate API key
        try:
            api_key_obj = BankAPIKey.objects.select_related('bank').get(
                key=api_key,
                is_active=True
            )
            
            # Attach bank to request for later use
            request.bank = api_key_obj.bank
            
            # Update last used timestamp
            from django.utils import timezone
            api_key_obj.last_used = timezone.now()
            api_key_obj.save(update_fields=['last_used'])
            
            return True
        
        except BankAPIKey.DoesNotExist:
            return False


class ReadOnly(permissions.BasePermission):
    """
    Permission to only allow read-only access
    """
    
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS