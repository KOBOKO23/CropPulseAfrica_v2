# apps/accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin interface for User model"""
    
    list_display = [
        'username',
        'email',
        'phone_number',
        'user_type',
        'is_verified',
        'is_active',
        'date_joined',
        'verification_badge'
    ]
    
    list_filter = [
        'user_type',
        'is_verified',
        'is_active',
        'is_staff',
        'date_joined'
    ]
    
    search_fields = [
        'username',
        'email',
        'phone_number',
        'first_name',
        'last_name'
    ]
    
    readonly_fields = [
        'date_joined',
        'last_login',
        'created_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('Authentication', {
            'fields': ('username', 'password')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone_number')
        }),
        ('User Type & Verification', {
            'fields': ('user_type', 'is_verified'),
            'classes': ('wide',)
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Important Dates', {
            'fields': ('date_joined', 'last_login', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        ('Create New User', {
            'classes': ('wide',),
            'fields': (
                'username',
                'email',
                'phone_number',
                'user_type',
                'password1',
                'password2',
                'is_verified'
            ),
        }),
    )
    
    ordering = ['-date_joined']
    
    def verification_badge(self, obj):
        """Display verification status with colored badge"""
        if obj.is_verified:
            return format_html(
                '<span style="background-color: #10b981; color: white; padding: 3px 10px; '
                'border-radius: 12px; font-size: 11px; font-weight: bold;">✓ VERIFIED</span>'
            )
        return format_html(
            '<span style="background-color: #ef4444; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">✗ UNVERIFIED</span>'
        )
    verification_badge.short_description = 'Status'
    
    actions = ['mark_as_verified', 'mark_as_unverified', 'deactivate_users']
    
    def mark_as_verified(self, request, queryset):
        """Bulk action to verify users"""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} user(s) marked as verified.')
    mark_as_verified.short_description = 'Mark selected users as verified'
    
    def mark_as_unverified(self, request, queryset):
        """Bulk action to unverify users"""
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} user(s) marked as unverified.')
    mark_as_unverified.short_description = 'Mark selected users as unverified'
    
    def deactivate_users(self, request, queryset):
        """Bulk action to deactivate users"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} user(s) deactivated.')
    deactivate_users.short_description = 'Deactivate selected users'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related()
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }