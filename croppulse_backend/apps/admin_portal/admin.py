# apps/admin_portal/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    FeatureFlag,
    TenantFeatureFlag,
    GlobalSettings,
    SystemMetrics,
    BankConfiguration,
    SystemAlert,
    APIUsageLog,
    DataExportRequest
)


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    """Admin interface for Feature Flags"""
    
    list_display = [
        'display_name',
        'name',
        'category',
        'status_badge',
        'beta_badge',
        'rollout_percentage',
        'created_at'
    ]
    
    list_filter = [
        'is_enabled',
        'is_beta',
        'category',
        'created_at'
    ]
    
    search_fields = [
        'name',
        'display_name',
        'description'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description', 'category')
        }),
        ('Status', {
            'fields': ('is_enabled', 'is_beta', 'rollout_percentage')
        }),
        ('Configuration', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        """Display status badge"""
        if obj.is_enabled:
            return format_html(
                '<span style="background-color: #10b981; color: white; padding: 3px 10px; '
                'border-radius: 12px; font-size: 11px; font-weight: bold;">ENABLED</span>'
            )
        return format_html(
            '<span style="background-color: #ef4444; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">DISABLED</span>'
        )
    status_badge.short_description = 'Status'
    
    def beta_badge(self, obj):
        """Display beta badge"""
        if obj.is_beta:
            return format_html(
                '<span style="background-color: #f59e0b; color: white; padding: 3px 10px; '
                'border-radius: 12px; font-size: 11px; font-weight: bold;">BETA</span>'
            )
        return '-'
    beta_badge.short_description = 'Beta'
    
    actions = ['enable_features', 'disable_features']
    
    def enable_features(self, request, queryset):
        """Bulk action to enable features"""
        updated = queryset.update(is_enabled=True)
        self.message_user(request, f'{updated} feature(s) enabled.')
    enable_features.short_description = 'Enable selected features'
    
    def disable_features(self, request, queryset):
        """Bulk action to disable features"""
        updated = queryset.update(is_enabled=False)
        self.message_user(request, f'{updated} feature(s) disabled.')
    disable_features.short_description = 'Disable selected features'


@admin.register(TenantFeatureFlag)
class TenantFeatureFlagAdmin(admin.ModelAdmin):
    """Admin interface for Tenant Feature Flags"""
    
    list_display = [
        'feature_flag',
        'tenant_user',
        'tenant_type',
        'is_enabled',
        'created_at'
    ]
    
    list_filter = [
        'is_enabled',
        'tenant_user__user_type',
        'created_at'
    ]
    
    search_fields = [
        'feature_flag__name',
        'tenant_user__username',
        'tenant_user__email'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    def tenant_type(self, obj):
        """Display tenant type"""
        return obj.tenant_user.get_user_type_display()
    tenant_type.short_description = 'Tenant Type'


@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    """Admin interface for Global Settings"""
    
    list_display = [
        'key',
        'value_preview',
        'value_type',
        'category',
        'sensitive_badge',
        'editable_badge'
    ]
    
    list_filter = [
        'category',
        'value_type',
        'is_sensitive',
        'is_editable'
    ]
    
    search_fields = [
        'key',
        'description'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Setting Information', {
            'fields': ('key', 'value', 'value_type', 'category', 'description')
        }),
        ('Properties', {
            'fields': ('is_sensitive', 'is_editable')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def value_preview(self, obj):
        """Display value preview"""
        if obj.is_sensitive:
            return '***HIDDEN***'
        value = str(obj.value)
        return value[:50] + '...' if len(value) > 50 else value
    value_preview.short_description = 'Value'
    
    def sensitive_badge(self, obj):
        """Display sensitive badge"""
        if obj.is_sensitive:
            return format_html(
                '<span style="background-color: #ef4444; color: white; padding: 3px 10px; '
                'border-radius: 12px; font-size: 11px;">SENSITIVE</span>'
            )
        return '-'
    sensitive_badge.short_description = 'Sensitive'
    
    def editable_badge(self, obj):
        """Display editable badge"""
        if obj.is_editable:
            return '✓'
        return '✗'
    editable_badge.short_description = 'Editable'


@admin.register(SystemMetrics)
class SystemMetricsAdmin(admin.ModelAdmin):
    """Admin interface for System Metrics"""
    
    list_display = [
        'timestamp',
        'total_api_calls',
        'failed_api_calls',
        'active_users',
        'cpu_usage_display',
        'memory_usage_display',
        'overall_status'
    ]
    
    list_filter = [
        'database_status',
        'redis_status',
        'celery_status',
        'timestamp'
    ]
    
    readonly_fields = [
        'timestamp',
        'total_api_calls',
        'failed_api_calls',
        'avg_response_time',
        'active_users',
        'new_users_today',
        'total_farmers',
        'total_farms',
        'total_loans',
        'cpu_usage',
        'memory_usage',
        'disk_usage',
        'database_status',
        'redis_status',
        'celery_status',
        'gee_status',
        'nasa_power_status',
        'metadata'
    ]
    
    def cpu_usage_display(self, obj):
        """Display CPU usage with color"""
        color = self._get_usage_color(obj.cpu_usage)
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, obj.cpu_usage
        )
    cpu_usage_display.short_description = 'CPU'
    
    def memory_usage_display(self, obj):
        """Display memory usage with color"""
        color = self._get_usage_color(obj.memory_usage)
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, obj.memory_usage
        )
    memory_usage_display.short_description = 'Memory'
    
    def overall_status(self, obj):
        """Display overall status"""
        statuses = [
            obj.database_status,
            obj.redis_status,
            obj.celery_status
        ]
        
        if 'down' in statuses:
            color = '#ef4444'
            status = 'CRITICAL'
        elif 'degraded' in statuses:
            color = '#f59e0b'
            status = 'DEGRADED'
        else:
            color = '#10b981'
            status = 'HEALTHY'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color, status
        )
    overall_status.short_description = 'Status'
    
    def _get_usage_color(self, usage):
        """Get color based on usage percentage"""
        if usage >= 90:
            return '#ef4444'  # red
        elif usage >= 75:
            return '#f59e0b'  # orange
        else:
            return '#10b981'  # green
    
    def has_add_permission(self, request):
        """Disable manual creation"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Make metrics read-only"""
        return False


@admin.register(BankConfiguration)
class BankConfigurationAdmin(admin.ModelAdmin):
    """Admin interface for Bank Configuration"""
    
    list_display = [
        'bank',
        'billing_plan',
        'api_rate_limit',
        'monthly_api_quota',
        'is_active',
        'created_at'
    ]
    
    list_filter = [
        'billing_plan',
        'is_active',
        'use_satellite_verification',
        'use_climate_risk_assessment',
        'use_fraud_detection',
        'created_at'
    ]
    
    search_fields = [
        'bank__name',
        'bank__user__email'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Bank Information', {
            'fields': ('bank',)
        }),
        ('API Configuration', {
            'fields': ('api_rate_limit', 'webhook_url', 'webhook_secret')
        }),
        ('Limits', {
            'fields': ('max_farmers', 'max_loans_per_farmer', 'min_credit_score')
        }),
        ('Features', {
            'fields': (
                'use_satellite_verification',
                'use_climate_risk_assessment',
                'use_fraud_detection'
            )
        }),
        ('Notifications', {
            'fields': ('notification_channels',)
        }),
        ('Billing', {
            'fields': ('billing_plan', 'monthly_api_quota')
        }),
        ('Custom Configuration', {
            'fields': ('custom_config',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SystemAlert)
class SystemAlertAdmin(admin.ModelAdmin):
    """Admin interface for System Alerts"""
    
    list_display = [
        'title',
        'severity_badge',
        'category',
        'resolved_badge',
        'created_at'
    ]
    
    list_filter = [
        'severity',
        'category',
        'is_resolved',
        'created_at'
    ]
    
    search_fields = [
        'title',
        'message',
        'source'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'resolved_at',
        'resolved_by'
    ]
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('title', 'message', 'severity', 'category', 'source')
        }),
        ('Resolution', {
            'fields': ('is_resolved', 'resolved_at', 'resolved_by')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def severity_badge(self, obj):
        """Display severity badge"""
        colors = {
            'info': '#3b82f6',
            'warning': '#f59e0b',
            'error': '#ef4444',
            'critical': '#dc2626'
        }
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            colors.get(obj.severity, '#6b7280'), obj.severity.upper()
        )
    severity_badge.short_description = 'Severity'
    
    def resolved_badge(self, obj):
        """Display resolved status"""
        if obj.is_resolved:
            return format_html(
                '<span style="color: #10b981; font-weight: bold;">✓ RESOLVED</span>'
            )
        return format_html(
            '<span style="color: #ef4444; font-weight: bold;">✗ ACTIVE</span>'
        )
    resolved_badge.short_description = 'Status'
    
    actions = ['mark_resolved']
    
    def mark_resolved(self, request, queryset):
        """Bulk action to mark alerts as resolved"""
        for alert in queryset:
            alert.resolve(request.user)
        self.message_user(request, f'{queryset.count()} alert(s) marked as resolved.')
    mark_resolved.short_description = 'Mark selected alerts as resolved'


@admin.register(APIUsageLog)
class APIUsageLogAdmin(admin.ModelAdmin):
    """Admin interface for API Usage Logs"""
    
    list_display = [
        'timestamp',
        'bank',
        'method',
        'endpoint_preview',
        'status_code_display',
        'response_time_display'
    ]
    
    list_filter = [
        'method',
        'status_code',
        'timestamp'
    ]
    
    search_fields = [
        'endpoint',
        'bank__name',
        'ip_address'
    ]
    
    readonly_fields = [
        'timestamp',
        'bank',
        'endpoint',
        'method',
        'status_code',
        'response_time',
        'ip_address',
        'user_agent',
        'request_size',
        'response_size',
        'error_message',
        'metadata'
    ]
    
    def endpoint_preview(self, obj):
        """Display endpoint preview"""
        endpoint = str(obj.endpoint)
        return endpoint[:50] + '...' if len(endpoint) > 50 else endpoint
    endpoint_preview.short_description = 'Endpoint'
    
    def status_code_display(self, obj):
        """Display status code with color"""
        if obj.status_code < 300:
            color = '#10b981'
        elif obj.status_code < 400:
            color = '#3b82f6'
        elif obj.status_code < 500:
            color = '#f59e0b'
        else:
            color = '#ef4444'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status_code
        )
    status_code_display.short_description = 'Status'
    
    def response_time_display(self, obj):
        """Display response time"""
        return f'{obj.response_time:.2f}ms'
    response_time_display.short_description = 'Response Time'
    
    def has_add_permission(self, request):
        """Disable manual creation"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Make logs read-only"""
        return False


@admin.register(DataExportRequest)
class DataExportRequestAdmin(admin.ModelAdmin):
    """Admin interface for Data Export Requests"""
    
    list_display = [
        'export_type',
        'requested_by',
        'status_badge',
        'format',
        'records_count',
        'created_at'
    ]
    
    list_filter = [
        'export_type',
        'status',
        'format',
        'created_at'
    ]
    
    search_fields = [
        'requested_by__username',
        'requested_by__email'
    ]
    
    readonly_fields = [
        'requested_by',
        'status',
        'file_url',
        'file_size',
        'records_count',
        'error_message',
        'started_at',
        'completed_at',
        'created_at',
        'updated_at'
    ]
    
    fieldsets = (
        ('Request Information', {
            'fields': ('requested_by', 'export_type', 'format')
        }),
        ('Date Range', {
            'fields': ('date_from', 'date_to')
        }),
        ('Status', {
            'fields': ('status', 'error_message')
        }),
        ('Result', {
            'fields': ('file_url', 'file_size', 'records_count')
        }),
        ('Filters', {
            'fields': ('filters',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'started_at', 'completed_at', 'expires_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        """Display status badge"""
        colors = {
            'pending': '#6b7280',
            'processing': '#3b82f6',
            'completed': '#10b981',
            'failed': '#ef4444'
        }
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#6b7280'), obj.status.upper()
        )
    status_badge.short_description = 'Status'