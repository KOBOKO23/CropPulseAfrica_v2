# compliance/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    ExportPassport,
    DeforestationCheck,
    ComplianceDocument,
    AuditLog,
    TranslationCache
)


@admin.register(ExportPassport)
class ExportPassportAdmin(admin.ModelAdmin):
    """Admin interface for Export Passports"""
    
    list_display = [
        'passport_id',
        'farmer_link',
        'farm_link',
        'commodity_type',
        'status_badge',
        'risk_badge',
        'issued_date',
        'valid_until',
        'is_active',
        'qr_preview',
        'pdf_link'
    ]
    
    list_filter = [
        'deforestation_status',
        'risk_level',
        'commodity_type',
        'is_active',
        'is_verified',
        'blockchain_network',
        'issued_date',
        'language'
    ]
    
    search_fields = [
        'passport_id',
        'dds_reference_number',
        'farmer__full_name',
        'farm__farm_name',
        'operator_name'
    ]
    
    readonly_fields = [
        'passport_id',
        'issued_date',
        'blockchain_hash',
        'blockchain_tx_hash',
        'blockchain_timestamp',
        'qr_code_preview',
        'pdf_preview',
        'audit_trail_display',
        'created_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'passport_id',
                'farmer',
                'farm',
                'issued_date',
                'valid_until'
            )
        }),
        ('Operator Information', {
            'fields': (
                'operator_name',
                'operator_eori',
                'dds_reference_number'
            )
        }),
        ('Commodity Information', {
            'fields': (
                'commodity_type',
                'commodity_code',
                'harvest_season',
                'estimated_production_kg'
            )
        }),
        ('Geolocation Data', {
            'fields': (
                'gps_coordinates',
                'centroid_latitude',
                'centroid_longitude',
                'farm_size_hectares',
                'plot_area_sqm'
            )
        }),
        ('Land Tenure', {
            'fields': (
                'land_ownership_verified',
                'land_tenure_type',
                'land_document_type',
                'land_document_url'
            )
        }),
        ('Deforestation Verification', {
            'fields': (
                'deforestation_status',
                'risk_level',
                'baseline_date',
                'satellite_analysis_date',
                'satellite_proof_url'
            )
        }),
        ('Blockchain', {
            'fields': (
                'blockchain_hash',
                'blockchain_network',
                'blockchain_tx_hash',
                'blockchain_timestamp'
            ),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': (
                'is_active',
                'is_verified',
                'verified_by',
                'verified_date'
            )
        }),
        ('Documents', {
            'fields': (
                'qr_code',
                'qr_code_preview',
                'pdf_document',
                'pdf_preview'
            )
        }),
        ('Settings', {
            'fields': (
                'language',
                'notes',
                'internal_reference'
            )
        }),
        ('Audit Trail', {
            'fields': ('audit_trail_display',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def farmer_link(self, obj):
        url = reverse('admin:farmers_farmer_change', args=[obj.farmer.id])
        return format_html('<a href="{}">{}</a>', url, obj.farmer.full_name)
    farmer_link.short_description = 'Farmer'
    
    def farm_link(self, obj):
        url = reverse('admin:farms_farm_change', args=[obj.farm.id])
        return format_html('<a href="{}">{}</a>', url, obj.farm.farm_name)
    farm_link.short_description = 'Farm'
    
    def status_badge(self, obj):
        colors = {
            'CLEAR': 'green',
            'UNDER_REVIEW': 'orange',
            'FLAGGED': 'red',
            'REMEDIATED': 'blue'
        }
        color = colors.get(obj.deforestation_status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_deforestation_status_display()
        )
    status_badge.short_description = 'Status'
    
    def risk_badge(self, obj):
        colors = {
            'LOW': 'green',
            'STANDARD': 'orange',
            'HIGH': 'red'
        }
        color = colors.get(obj.risk_level, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_risk_level_display()
        )
    risk_badge.short_description = 'Risk'
    
    def qr_preview(self, obj):
        if obj.qr_code:
            return format_html('<img src="{}" width="50" height="50" />', obj.qr_code.url)
        return '-'
    qr_preview.short_description = 'QR'
    
    def qr_code_preview(self, obj):
        if obj.qr_code:
            return format_html('<img src="{}" width="200" height="200" />', obj.qr_code.url)
        return 'No QR code'
    qr_code_preview.short_description = 'QR Code Preview'
    
    def pdf_link(self, obj):
        if obj.pdf_document:
            return format_html(
                '<a href="{}" target="_blank">Download PDF</a>',
                obj.pdf_document.url
            )
        return '-'
    pdf_link.short_description = 'PDF'
    
    def pdf_preview(self, obj):
        if obj.pdf_document:
            return format_html(
                '<a href="{}" target="_blank">View PDF</a>',
                obj.pdf_document.url
            )
        return 'No PDF'
    pdf_preview.short_description = 'PDF Document'
    
    def audit_trail_display(self, obj):
        if obj.audit_trail:
            html = '<table style="width: 100%; border-collapse: collapse;">'
            html += '<tr style="background-color: #f0f0f0;"><th>Timestamp</th><th>Action</th><th>User</th><th>Details</th></tr>'
            
            for entry in obj.audit_trail[-10:]:  # Show last 10 entries
                html += '<tr>'
                html += f'<td>{entry.get("timestamp", "")}</td>'
                html += f'<td>{entry.get("action", "")}</td>'
                html += f'<td>{entry.get("user", "")}</td>'
                html += f'<td>{entry.get("details", "")}</td>'
                html += '</tr>'
            
            html += '</table>'
            return mark_safe(html)
        return 'No audit trail'
    audit_trail_display.short_description = 'Audit Trail (Last 10 entries)'


@admin.register(DeforestationCheck)
class DeforestationCheckAdmin(admin.ModelAdmin):
    """Admin interface for Deforestation Checks"""
    
    list_display = [
        'check_date',
        'farm_link',
        'check_type',
        'result_badge',
        'risk_score',
        'deforestation_detected',
        'forest_change',
        'status'
    ]
    
    list_filter = [
        'check_type',
        'result',
        'status',
        'deforestation_detected',
        'satellite_provider',
        'check_date'
    ]
    
    search_fields = [
        'farm__farm_name',
        'farm__farmer__full_name'
    ]
    
    readonly_fields = [
        'check_date',
        'risk_score',
        'created_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'farm',
                'export_passport',
                'check_date',
                'check_type'
            )
        }),
        ('Analysis Period', {
            'fields': (
                'analysis_start_date',
                'analysis_end_date',
                'baseline_date'
            )
        }),
        ('Results', {
            'fields': (
                'status',
                'result',
                'deforestation_detected',
                'forest_cover_percentage',
                'baseline_forest_cover',
                'change_in_forest_cover',
                'forest_loss_hectares'
            )
        }),
        ('Risk Assessment', {
            'fields': (
                'risk_score',
                'risk_factors',
                'confidence_score'
            )
        }),
        ('Satellite Data', {
            'fields': (
                'satellite_provider',
                'satellite_imagery_urls',
                'cloud_cover_percentage',
                'ndvi_baseline',
                'ndvi_current',
                'ndvi_change'
            )
        }),
        ('Review', {
            'fields': (
                'reviewed_by',
                'reviewed_date',
                'reviewer_notes'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'analysis_method',
                'analysis_metadata',
                'evidence_urls',
                'report_url',
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        })
    )
    
    def farm_link(self, obj):
        url = reverse('admin:farms_farm_change', args=[obj.farm.id])
        return format_html('<a href="{}">{}</a>', url, obj.farm.farm_name)
    farm_link.short_description = 'Farm'
    
    def result_badge(self, obj):
        colors = {
            'CLEAR': 'green',
            'WARNING': 'orange',
            'VIOLATION': 'red',
            'INCONCLUSIVE': 'gray'
        }
        color = colors.get(obj.result, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_result_display() if obj.result else 'N/A'
        )
    result_badge.short_description = 'Result'
    
    def forest_change(self, obj):
        change = obj.change_in_forest_cover
        color = 'red' if change < 0 else 'green'
        return format_html(
            '<span style="color: {};">{:+.2f}%</span>',
            color,
            change
        )
    forest_change.short_description = 'Forest Change'


@admin.register(ComplianceDocument)
class ComplianceDocumentAdmin(admin.ModelAdmin):
    """Admin interface for Compliance Documents"""
    
    list_display = [
        'document_name',
        'document_type',
        'passport_link',
        'upload_date',
        'uploaded_by',
        'is_verified',
        'file_preview'
    ]
    
    list_filter = [
        'document_type',
        'is_verified',
        'upload_date'
    ]
    
    search_fields = [
        'document_name',
        'export_passport__passport_id',
        'uploaded_by'
    ]
    
    readonly_fields = [
        'upload_date',
        'file_size_bytes',
        'file_hash',
        'created_at',
        'updated_at'
    ]
    
    def passport_link(self, obj):
        url = reverse('admin:compliance_exportpassport_change', args=[obj.export_passport.id])
        return format_html('<a href="{}">{}</a>', url, obj.export_passport.passport_id)
    passport_link.short_description = 'Passport'
    
    def file_preview(self, obj):
        if obj.document_file:
            return format_html(
                '<a href="{}" target="_blank">View File</a>',
                obj.document_file.url
            )
        return '-'
    file_preview.short_description = 'File'


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for Audit Logs"""
    
    list_display = [
        'timestamp',
        'entity_type',
        'action',
        'user_name',
        'user_role',
        'ip_address'
    ]
    
    list_filter = [
        'entity_type',
        'action',
        'timestamp'
    ]
    
    search_fields = [
        'user_name',
        'user_id',
        'entity_id'
    ]
    
    readonly_fields = [
        'timestamp',
        'entity_type',
        'entity_id',
        'user_id',
        'user_name',
        'user_role',
        'action',
        'changes',
        'reason',
        'ip_address',
        'user_agent',
        'created_at'
    ]
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TranslationCache)
class TranslationCacheAdmin(admin.ModelAdmin):
    """Admin interface for Translation Cache"""
    
    list_display = [
        'source_language',
        'target_language',
        'hit_count',
        'created_at',
        'expires_at'
    ]
    
    list_filter = [
        'source_language',
        'target_language',
        'created_at'
    ]
    
    search_fields = [
        'source_text',
        'translated_text',
        'cache_key'
    ]
    
    readonly_fields = [
        'cache_key',
        'hit_count',
        'created_at'
    ]