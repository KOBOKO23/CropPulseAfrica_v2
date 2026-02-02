# core/permissions.py

from rest_framework import permissions


class IsFarmerOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to only allow farmers to access their own data
    or admins to access any data
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin users can access anything
        if request.user.is_staff or request.user.user_type == 'admin':
            return True
        
        # Bank users can access (read-only)
        if request.user.user_type == 'bank' and request.method in permissions.SAFE_METHODS:
            return True
        
        # Farmers can only access their own data
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        if hasattr(obj, 'farmer'):
            return obj.farmer.user == request.user
        
        return False


class IsFarmerOrAdmin(permissions.BasePermission):
    """
    Permission for farmer or admin users only
    """
    
    def has_permission(self, request, view):
        return request.user.user_type in ['farmer', 'admin'] or request.user.is_staff


class IsBankOrAdmin(permissions.BasePermission):
    """
    Permission for bank or admin users only
    """
    
    def has_permission(self, request, view):
        return request.user.user_type in ['bank', 'admin'] or request.user.is_staff


class IsAdminOnly(permissions.BasePermission):
    """
    Permission for admin users only
    """
    
    def has_permission(self, request, view):
        return request.user.user_type == 'admin' or request.user.is_staff