# apps/farmers/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from .models import Farmer, VoiceRegistration


@admin.register(Farmer)
class FarmerAdmin(admin.ModelAdmin):
    """Admin interface for Farmer model"""
    
    list_display = [
        'pulse_id',
        'full_name',
        'user_link',
        'county',
        'primary_crop',
        'verification_badge',
        'onboarding_badge',
        'farms_count',
        'created_at'
    ]
    
    list_filter = [
        'county',
        'sub_county',
        'primary_crop',
        'onboarding_completed',
        'is_active',
        'created_at'
    ]
    
    search_fields = [
        'pulse_id',
        'full_name',
        'id_number',
        'user__username',
        'user__email',
        'user__phone_number'
    ]
    
    readonly_fields = [
        'pulse_id',
        'created_at',
        'updated_at',
        'photo_preview'
    ]
    
    fieldsets = (
        ('Pulse ID & User', {
            'fields': ('pulse_id', 'user')
        }),
        ('Personal Information', {
            'fields': ('full_name', 'date_of_birth', 'id_number', 'photo', 'photo_preview')
        }),
        ('Location', {
            'fields': ('county', 'sub_county', 'nearest_town')
        }),
        ('Farming Details', {
            'fields': ('years_farming', 'primary_crop', 'secondary_crops')
        }),
        ('Biometric Data', {
            'fields': ('voice_signature',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('onboarding_completed', 'is_active', 'created_at', 'updated_at')
        }),
    )
    
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def user_link(self, obj):
        """Link to user admin page"""
        from django.urls import reverse
        url = reverse('admin:accounts_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def verification_badge(self, obj):
        """Display verification status"""
        if obj.user.is_verified:
            return format_html(
                '<span style="background-color: #10b981; color: white; padding: 3px 10px; '
                'border-radius: 12px; font-size: 11px; font-weight: bold;">✓ VERIFIED</span>'
            )
        return format_html(
            '<span style="background-color: #f59e0b; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">PENDING</span>'
        )
    verification_badge.short_description = 'Status'
    
    def onboarding_badge(self, obj):
        """Display onboarding status"""
        if obj.onboarding_completed:
            return format_html('<span style="color: #10b981;">✓ Complete</span>')
        return format_html('<span style="color: #ef4444;">Incomplete</span>')
    onboarding_badge.short_description = 'Onboarding'
    
    def farms_count(self, obj):
        """Display number of farms"""
        count = obj.farms.count()
        if count > 0:
            return format_html(
                '<span style="background-color: #3b82f6; color: white; padding: 2px 8px; '
                'border-radius: 10px; font-size: 11px;">{}</span>', count
            )
        return '0'
    farms_count.short_description = 'Farms'
    
    def photo_preview(self, obj):
        """Display photo preview"""
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-width: 200px; border-radius: 8px;" />',
                obj.photo.url
            )
        return 'No photo'
    photo_preview.short_description = 'Photo'
    
    actions = ['mark_onboarding_complete', 'export_to_csv']
    
    def mark_onboarding_complete(self, request, queryset):
        """Mark selected farmers as onboarded"""
        updated = queryset.update(onboarding_completed=True)
        self.message_user(request, f'{updated} farmer(s) marked as onboarded.')
    mark_onboarding_complete.short_description = 'Mark onboarding complete'
    
    def export_to_csv(self, request, queryset):
        """Export to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="farmers.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Pulse ID', 'Full Name', 'Phone', 'County', 'Primary Crop',
            'Years Farming', 'Verified', 'Onboarded', 'Created'
        ])
        
        for farmer in queryset.select_related('user'):
            writer.writerow([
                farmer.pulse_id,
                farmer.full_name,
                farmer.user.phone_number,
                farmer.county,
                farmer.primary_crop,
                farmer.years_farming,
                'Yes' if farmer.user.is_verified else 'No',
                'Yes' if farmer.onboarding_completed else 'No',
                farmer.created_at.strftime('%Y-%m-%d')
            ])
        
        return response
    export_to_csv.short_description = 'Export to CSV'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs.select_related('user').annotate(
            farms_count_annotation=Count('farms')
        )


@admin.register(VoiceRegistration)
class VoiceRegistrationAdmin(admin.ModelAdmin):
    """Admin interface for VoiceRegistration"""
    
    list_display = [
        'farmer_link',
        'detected_language',
        'confidence_display',
        'transcript_preview',
        'created_at'
    ]
    
    list_filter = ['detected_language', 'created_at']
    
    search_fields = [
        'farmer__pulse_id',
        'farmer__full_name',
        'transcript'
    ]
    
    readonly_fields = ['created_at', 'audio_player']
    
    fieldsets = (
        ('Farmer', {
            'fields': ('farmer',)
        }),
        ('Recording', {
            'fields': ('audio_file', 'audio_player', 'detected_language', 'confidence_score')
        }),
        ('Transcript', {
            'fields': ('transcript',)
        }),
        ('Processed Data', {
            'fields': ('processed_data',),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    
    def farmer_link(self, obj):
        """Link to farmer"""
        from django.urls import reverse
        url = reverse('admin:farmers_farmer_change', args=[obj.farmer.id])
        return format_html('<a href="{}">{}</a>', url, obj.farmer.full_name)
    farmer_link.short_description = 'Farmer'
    
    def confidence_display(self, obj):
        """Display confidence"""
        confidence = obj.confidence_score * 100
        color = '#10b981' if confidence >= 90 else '#f59e0b' if confidence >= 70 else '#ef4444'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, confidence
        )
    confidence_display.short_description = 'Confidence'
    
    def transcript_preview(self, obj):
        """Transcript preview"""
        return obj.transcript[:50] + '...' if len(obj.transcript) > 50 else obj.transcript
    transcript_preview.short_description = 'Transcript'
    
    def audio_player(self, obj):
        """Audio player"""
        if obj.audio_file:
            return format_html(
                '<audio controls><source src="{}" type="audio/mpeg"></audio>',
                obj.audio_file.url
            )
        return 'No audio'
    audio_player.short_description = 'Audio'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs.select_related('farmer', 'farmer__user')