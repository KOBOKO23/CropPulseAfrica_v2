# apps/farmers/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from django.urls import reverse
from .models import Farmer, VoiceRegistration, FarmerNote


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
        'fraud_badge',
        'onboarding_badge',
        'farms_count',
        'created_at'
    ]
    
    list_filter = [
        'county',
        'sub_county',
        'primary_crop',
        'fraud_status',
        'onboarding_completed',
        'is_active',
        'farming_method',
        'irrigation_access',
        'preferred_language',
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
        'last_fraud_check',
        'onboarding_completed_at',
        'photo_preview',
        'location_map'
    ]
    
    fieldsets = (
        ('Pulse ID & User', {
            'fields': ('pulse_id', 'user')
        }),
        ('Personal Information', {
            'fields': (
                'full_name',
                'date_of_birth',
                'id_number',
                'photo',
                'photo_preview'
            )
        }),
        ('Location', {
            'fields': (
                'county',
                'sub_county',
                'nearest_town',
                'latitude',
                'longitude',
                'location_map'
            )
        }),
        ('Farming Details', {
            'fields': (
                'years_farming',
                'primary_crop',
                'secondary_crops',
                'farming_method',
                'irrigation_access'
            )
        }),
        ('Fraud Detection', {
            'fields': (
                'fraud_status',
                'fraud_notes',
                'last_fraud_check'
            ),
            'classes': ('collapse',)
        }),
        ('Biometric Data', {
            'fields': ('voice_signature',),
            'classes': ('collapse',)
        }),
        ('Preferences', {
            'fields': (
                'preferred_language',
                'referral_source'
            ),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': (
                'onboarding_completed',
                'onboarding_completed_at',
                'is_active',
                'created_at',
                'updated_at'
            )
        }),
    )
    
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    actions = [
        'mark_onboarding_complete',
        'flag_for_fraud',
        'clear_fraud_flag',
        'deactivate_farmers',
        'export_to_csv'
    ]
    
    def user_link(self, obj):
        """Link to user admin page"""
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
    verification_badge.short_description = 'Verification'
    
    def fraud_badge(self, obj):
        """Display fraud status"""
        colors = {
            'clean': '#10b981',
            'verified': '#3b82f6',
            'flagged': '#ef4444',
            'under_review': '#f59e0b',
            'suspended': '#dc2626'
        }
        color = colors.get(obj.fraud_status, '#64748b')
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_fraud_status_display().upper()
        )
    fraud_badge.short_description = 'Fraud Status'
    
    def onboarding_badge(self, obj):
        """Display onboarding status"""
        if obj.onboarding_completed:
            return format_html('<span style="color: #10b981; font-weight: bold;">✓ Complete</span>')
        return format_html('<span style="color: #ef4444;">Incomplete</span>')
    onboarding_badge.short_description = 'Onboarding'
    
    def farms_count(self, obj):
        """Display number of farms"""
        count = obj.farms.filter(is_active=True).count()
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
                '<img src="{}" style="max-width: 200px; max-height: 200px; border-radius: 8px;" />',
                obj.photo.url
            )
        return 'No photo'
    photo_preview.short_description = 'Photo'
    
    def location_map(self, obj):
        """Display location on map"""
        if obj.latitude and obj.longitude:
            map_url = f"https://www.google.com/maps?q={obj.latitude},{obj.longitude}"
            return format_html(
                '<a href="{}" target="_blank" style="color: #3b82f6; font-weight: bold;">'
                'View on Map ({}, {})</a>',
                map_url, obj.latitude, obj.longitude
            )
        return 'No coordinates'
    location_map.short_description = 'Location'
    
    # Actions
    def mark_onboarding_complete(self, request, queryset):
        """Mark selected farmers as onboarded"""
        updated = 0
        for farmer in queryset:
            if not farmer.onboarding_completed:
                try:
                    from .services import FarmerProfileService
                    FarmerProfileService.complete_onboarding(farmer)
                    updated += 1
                except ValueError as e:
                    self.message_user(
                        request,
                        f"Cannot complete onboarding for {farmer.full_name}: {str(e)}",
                        level='error'
                    )
        
        if updated > 0:
            self.message_user(request, f'{updated} farmer(s) marked as onboarded.')
    mark_onboarding_complete.short_description = 'Mark onboarding complete'
    
    def flag_for_fraud(self, request, queryset):
        """Flag selected farmers for fraud"""
        from .services import FarmerProfileService
        
        updated = 0
        for farmer in queryset:
            if farmer.fraud_status not in ['flagged', 'suspended']:
                FarmerProfileService.flag_for_fraud(
                    farmer,
                    reason="Flagged via admin action",
                    flagged_by=request.user
                )
                updated += 1
        
        self.message_user(request, f'{updated} farmer(s) flagged for fraud review.')
    flag_for_fraud.short_description = 'Flag for fraud review'
    
    def clear_fraud_flag(self, request, queryset):
        """Clear fraud flags"""
        from .services import FarmerProfileService
        
        updated = 0
        for farmer in queryset:
            if farmer.fraud_status in ['flagged', 'under_review']:
                FarmerProfileService.clear_fraud_flag(
                    farmer,
                    reason="Cleared via admin action",
                    cleared_by=request.user
                )
                updated += 1
        
        self.message_user(request, f'{updated} fraud flag(s) cleared.')
    clear_fraud_flag.short_description = 'Clear fraud flags'
    
    def deactivate_farmers(self, request, queryset):
        """Deactivate selected farmers"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} farmer(s) deactivated.')
    deactivate_farmers.short_description = 'Deactivate farmers'
    
    def export_to_csv(self, request, queryset):
        """Export to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="farmers.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Pulse ID', 'Full Name', 'Phone', 'County', 'Sub-County',
            'Primary Crop', 'Years Farming', 'Farm Size', 'Verified',
            'Fraud Status', 'Onboarded', 'Created'
        ])
        
        for farmer in queryset.select_related('user').prefetch_related('farms'):
            total_size = farmer.get_total_farm_size()
            
            writer.writerow([
                farmer.pulse_id,
                farmer.full_name,
                farmer.user.phone_number,
                farmer.county,
                farmer.sub_county,
                farmer.primary_crop,
                farmer.years_farming,
                f"{total_size} acres",
                'Yes' if farmer.user.is_verified else 'No',
                farmer.get_fraud_status_display(),
                'Yes' if farmer.onboarding_completed else 'No',
                farmer.created_at.strftime('%Y-%m-%d %H:%M')
            ])
        
        return response
    export_to_csv.short_description = 'Export to CSV'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs.select_related('user').prefetch_related('farms')


@admin.register(VoiceRegistration)
class VoiceRegistrationAdmin(admin.ModelAdmin):
    """Admin interface for VoiceRegistration"""
    
    list_display = [
        'farmer_link',
        'detected_language',
        'confidence_display',
        'processing_status_badge',
        'transcript_preview',
        'created_at'
    ]
    
    list_filter = [
        'detected_language',
        'processing_status',
        'created_at'
    ]
    
    search_fields = [
        'farmer__pulse_id',
        'farmer__full_name',
        'transcript'
    ]
    
    readonly_fields = [
        'created_at',
        'processed_at',
        'audio_player',
        'audio_duration',
        'audio_format',
        'audio_size'
    ]
    
    fieldsets = (
        ('Farmer', {
            'fields': ('farmer',)
        }),
        ('Recording', {
            'fields': (
                'audio_file',
                'audio_player',
                'audio_duration',
                'audio_format',
                'audio_size'
            )
        }),
        ('Processing', {
            'fields': (
                'processing_status',
                'processing_error',
                'detected_language',
                'confidence_score',
                'created_at',
                'processed_at'
            )
        }),
        ('Results', {
            'fields': (
                'transcript',
                'processed_data',
                'field_confidence'
            )
        }),
    )
    
    date_hierarchy = 'created_at'
    
    def farmer_link(self, obj):
        """Link to farmer"""
        url = reverse('admin:farmers_farmer_change', args=[obj.farmer.id])
        return format_html('<a href="{}">{}</a>', url, obj.farmer.full_name)
    farmer_link.short_description = 'Farmer'
    
    def confidence_display(self, obj):
        """Display confidence"""
        confidence = obj.get_confidence_percentage()
        color = '#10b981' if confidence >= 90 else '#f59e0b' if confidence >= 70 else '#ef4444'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, confidence
        )
    confidence_display.short_description = 'Confidence'
    
    def processing_status_badge(self, obj):
        """Display processing status"""
        colors = {
            'pending': '#f59e0b',
            'processing': '#3b82f6',
            'completed': '#10b981',
            'failed': '#ef4444'
        }
        color = colors.get(obj.processing_status, '#64748b')
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_processing_status_display().upper()
        )
    processing_status_badge.short_description = 'Status'
    
    def transcript_preview(self, obj):
        """Transcript preview"""
        if len(obj.transcript) > 50:
            return obj.transcript[:50] + '...'
        return obj.transcript
    transcript_preview.short_description = 'Transcript'
    
    def audio_player(self, obj):
        """Audio player"""
        if obj.audio_file:
            return format_html(
                '<audio controls style="width: 300px;">'
                '<source src="{}" type="audio/mpeg">Your browser does not support audio.</audio>',
                obj.audio_file.url
            )
        return 'No audio'
    audio_player.short_description = 'Audio'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs.select_related('farmer', 'farmer__user')


@admin.register(FarmerNote)
class FarmerNoteAdmin(admin.ModelAdmin):
    """Admin interface for Farmer Notes"""
    
    list_display = [
        'farmer_link',
        'note_type',
        'created_by',
        'is_internal',
        'content_preview',
        'created_at'
    ]
    
    list_filter = [
        'note_type',
        'is_internal',
        'created_at'
    ]
    
    search_fields = [
        'farmer__pulse_id',
        'farmer__full_name',
        'content',
        'created_by__username'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Note Details', {
            'fields': ('farmer', 'created_by', 'note_type', 'is_internal')
        }),
        ('Content', {
            'fields': ('content',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    
    def farmer_link(self, obj):
        """Link to farmer"""
        url = reverse('admin:farmers_farmer_change', args=[obj.farmer.id])
        return format_html('<a href="{}">{}</a>', url, obj.farmer.full_name)
    farmer_link.short_description = 'Farmer'
    
    def content_preview(self, obj):
        """Content preview"""
        if len(obj.content) > 50:
            return obj.content[:50] + '...'
        return obj.content
    content_preview.short_description = 'Content'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs.select_related('farmer', 'created_by')