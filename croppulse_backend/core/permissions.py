from rest_framework import permissions


class IsFarmerOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to only allow farmers to access their own data
    or admins to access any data
    """
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or getattr(request.user, 'user_type', None) == 'admin':
            return True
        
        if getattr(request.user, 'user_type', None) == 'bank' and request.method in permissions.SAFE_METHODS:
            return True
        
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        if hasattr(obj, 'farmer'):
            return obj.farmer.user == request.user
        
        return False


class IsFarmerOrAdmin(permissions.BasePermission):
    """Permission for farmer or admin users only"""
    
    def has_permission(self, request, view):
        return getattr(request.user, 'user_type', None) in ['farmer', 'admin'] or request.user.is_staff


class IsBankOrAdmin(permissions.BasePermission):
    """Permission for bank or admin users only"""
    
    def has_permission(self, request, view):
        return getattr(request.user, 'user_type', None) in ['bank', 'admin'] or request.user.is_staff


class IsAdminOnly(permissions.BasePermission):
    """Permission for admin users only"""
    
    def has_permission(self, request, view):
        return getattr(request.user, 'user_type', None) == 'admin' or request.user.is_staff


class IsTenantUser(permissions.BasePermission):
    """
    Permission for users that belong to a tenant
    (organization, cooperative, bank, etc.)
    """
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "tenant")
        )
