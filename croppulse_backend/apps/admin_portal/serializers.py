# apps/admin_portal/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
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

User = get_user_model()


class FeatureFlagSerializer(serializers.ModelSerializer):
    """Serializer for Feature Flags"""
    
    tenant_overrides_count = serializers.SerializerMethodField()
    
    class Meta:
        model = FeatureFlag
        fields = [
            'id',
            'name',
            'display_name',
            'description',
            'is_enabled',
            'is_beta',
            'category',
            'rollout_percentage',
            'metadata',
            'tenant_overrides_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_tenant_overrides_count(self, obj):
        """Get count of tenant-specific overrides"""
        return obj.tenant_overrides.count()
    
    def validate_name(self, value):
        """Validate feature flag name format"""
        if not value.replace('_', '').isalnum():
            raise serializers.ValidationError(
                "Feature name must contain only letters, numbers, and underscores"
            )
        return value.lower()
    
    def validate_rollout_percentage(self, value):
        """Validate rollout percentage"""
        if not 0 <= value <= 100:
            raise serializers.ValidationError(
                "Rollout percentage must be between 0 and 100"
            )
        return value


class TenantFeatureFlagSerializer(serializers.ModelSerializer):
    """Serializer for Tenant Feature Flags"""
    
    feature_flag_name = serializers.CharField(source='feature_flag.name', read_only=True)
    feature_flag_display_name = serializers.CharField(source='feature_flag.display_name', read_only=True)
    tenant_username = serializers.CharField(source='tenant_user.username', read_only=True)
    tenant_type = serializers.CharField(source='tenant_user.user_type', read_only=True)
    
    class Meta:
        model = TenantFeatureFlag
        fields = [
            'id',
            'feature_flag',
            'feature_flag_name',
            'feature_flag_display_name',
            'tenant_user',
            'tenant_username',
            'tenant_type',
            'is_enabled',
            'custom_config',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_tenant_user(self, value):
        """Ensure user is a bank or exporter"""
        if value.user_type not in ['bank', 'exporter']:
            raise serializers.ValidationError(
                "Tenant must be a bank or exporter user"
            )
        return value


class GlobalSettingsSerializer(serializers.ModelSerializer):
    """Serializer for Global Settings"""
    
    parsed_value = serializers.SerializerMethodField()
    
    class Meta:
        model = GlobalSettings
        fields = [
            'id',
            'key',
            'value',
            'parsed_value',
            'value_type',
            'category',
            'description',
            'is_sensitive',
            'is_editable',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_parsed_value(self, obj):
        """Get the typed value"""
        if obj.is_sensitive and not self.context.get('show_sensitive', False):
            return '***HIDDEN***'
        try:
            return obj.get_value()
        except:
            return obj.value
    
    def validate_key(self, value):
        """Validate setting key format"""
        if not value.replace('_', '').replace('.', '').isalnum():
            raise serializers.ValidationError(
                "Setting key must contain only letters, numbers, underscores, and periods"
            )
        return value.lower()
    
    def validate(self, attrs):
        """Validate value against value_type"""
        value = attrs.get('value')
        value_type = attrs.get('value_type')
        
        if value and value_type:
            try:
                if value_type == 'integer':
                    int(value)
                elif value_type == 'float':
                    float(value)
                elif value_type == 'boolean':
                    if value.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                        raise ValueError()
                elif value_type == 'json':
                    import json
                    json.loads(value)
            except ValueError:
                raise serializers.ValidationError({
                    'value': f'Value is not a valid {value_type}'
                })
        
        return attrs


class SystemMetricsSerializer(serializers.ModelSerializer):
    """Serializer for System Metrics"""
    
    overall_health = serializers.SerializerMethodField()
    api_success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = SystemMetrics
        fields = [
            'id',
            'timestamp',
            'total_api_calls',
            'failed_api_calls',
            'api_success_rate',
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
            'overall_health',
            'metadata'
        ]
        read_only_fields = fields
    
    def get_overall_health(self, obj):
        """Calculate overall system health"""
        statuses = [
            obj.database_status,
            obj.redis_status,
            obj.celery_status,
            obj.gee_status,
            obj.nasa_power_status
        ]
        
        if 'down' in statuses:
            return 'critical'
        elif 'degraded' in statuses:
            return 'degraded'
        return 'healthy'
    
    def get_api_success_rate(self, obj):
        """Calculate API success rate"""
        if obj.total_api_calls == 0:
            return 100.0
        success_rate = ((obj.total_api_calls - obj.failed_api_calls) / obj.total_api_calls) * 100
        return round(success_rate, 2)


class BankConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for Bank Configuration"""
    
    bank_name = serializers.CharField(source='bank.name', read_only=True)
    bank_user_email = serializers.CharField(source='bank.user.email', read_only=True)
    api_usage_this_month = serializers.SerializerMethodField()
    quota_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = BankConfiguration
        fields = [
            'id',
            'bank',
            'bank_name',
            'bank_user_email',
            'api_rate_limit',
            'webhook_url',
            'webhook_secret',
            'max_farmers',
            'max_loans_per_farmer',
            'min_credit_score',
            'use_satellite_verification',
            'use_climate_risk_assessment',
            'use_fraud_detection',
            'notification_channels',
            'billing_plan',
            'monthly_api_quota',
            'api_usage_this_month',
            'quota_remaining',
            'custom_config',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_api_usage_this_month(self, obj):
        """Get API usage for current month"""
        from django.utils import timezone
        from datetime import timedelta
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        usage = APIUsageLog.objects.filter(
            bank=obj.bank,
            timestamp__gte=thirty_days_ago
        ).count()
        
        return usage
    
    def get_quota_remaining(self, obj):
        """Calculate remaining API quota"""
        usage = self.get_api_usage_this_month(obj)
        remaining = obj.monthly_api_quota - usage
        return max(0, remaining)
    
    def validate_min_credit_score(self, value):
        """Validate credit score range"""
        if not 0 <= value <= 100:
            raise serializers.ValidationError(
                "Credit score must be between 0 and 100"
            )
        return value
    
    def validate_notification_channels(self, value):
        """Validate notification channels"""
        valid_channels = ['email', 'sms', 'webhook', 'push']
        if not isinstance(value, list):
            raise serializers.ValidationError("Notification channels must be a list")
        
        for channel in value:
            if channel not in valid_channels:
                raise serializers.ValidationError(
                    f"Invalid channel: {channel}. Must be one of {valid_channels}"
                )
        
        return value


class SystemAlertSerializer(serializers.ModelSerializer):
    """Serializer for System Alerts"""
    
    resolved_by_username = serializers.CharField(source='resolved_by.username', read_only=True)
    time_to_resolve = serializers.SerializerMethodField()
    
    class Meta:
        model = SystemAlert
        fields = [
            'id',
            'title',
            'message',
            'severity',
            'category',
            'is_resolved',
            'resolved_at',
            'resolved_by',
            'resolved_by_username',
            'time_to_resolve',
            'source',
            'metadata',
            'notification_sent',
            'notification_sent_at',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'resolved_at',
            'notification_sent',
            'notification_sent_at',
            'created_at',
            'updated_at'
        ]
    
    def get_time_to_resolve(self, obj):
        """Calculate time to resolve in minutes"""
        if obj.is_resolved and obj.resolved_at:
            delta = obj.resolved_at - obj.created_at
            return round(delta.total_seconds() / 60, 2)
        return None


class SystemAlertCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating system alerts"""
    
    class Meta:
        model = SystemAlert
        fields = [
            'title',
            'message',
            'severity',
            'category',
            'source',
            'metadata'
        ]
    
    def validate_severity(self, value):
        """Validate severity level"""
        valid_severities = ['info', 'warning', 'error', 'critical']
        if value not in valid_severities:
            raise serializers.ValidationError(
                f"Severity must be one of: {valid_severities}"
            )
        return value


class APIUsageLogSerializer(serializers.ModelSerializer):
    """Serializer for API Usage Logs"""
    
    bank_name = serializers.CharField(source='bank.name', read_only=True)
    is_error = serializers.SerializerMethodField()
    
    class Meta:
        model = APIUsageLog
        fields = [
            'id',
            'timestamp',
            'bank',
            'bank_name',
            'endpoint',
            'method',
            'status_code',
            'is_error',
            'response_time',
            'ip_address',
            'user_agent',
            'request_size',
            'response_size',
            'error_message',
            'metadata'
        ]
        read_only_fields = fields
    
    def get_is_error(self, obj):
        """Check if request resulted in error"""
        return obj.status_code >= 400


class APIUsageStatsSerializer(serializers.Serializer):
    """Serializer for API usage statistics"""
    
    total_requests = serializers.IntegerField()
    successful_requests = serializers.IntegerField()
    failed_requests = serializers.IntegerField()
    success_rate = serializers.FloatField()
    avg_response_time = serializers.FloatField()
    total_data_transferred = serializers.IntegerField()
    top_endpoints = serializers.ListField()
    requests_by_status = serializers.DictField()
    requests_over_time = serializers.ListField()


class DataExportRequestSerializer(serializers.ModelSerializer):
    """Serializer for Data Export Requests"""
    
    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True)
    requested_by_email = serializers.CharField(source='requested_by.email', read_only=True)
    processing_time = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = DataExportRequest
        fields = [
            'id',
            'requested_by',
            'requested_by_username',
            'requested_by_email',
            'export_type',
            'status',
            'date_from',
            'date_to',
            'format',
            'filters',
            'file_url',
            'file_size',
            'records_count',
            'error_message',
            'started_at',
            'completed_at',
            'processing_time',
            'expires_at',
            'is_expired',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
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
    
    def get_processing_time(self, obj):
        """Calculate processing time in seconds"""
        if obj.started_at and obj.completed_at:
            delta = obj.completed_at - obj.started_at
            return round(delta.total_seconds(), 2)
        return None
    
    def get_is_expired(self, obj):
        """Check if download link has expired"""
        if not obj.expires_at:
            return False
        
        from django.utils import timezone
        return timezone.now() > obj.expires_at
    
    def validate(self, attrs):
        """Validate date range"""
        date_from = attrs.get('date_from')
        date_to = attrs.get('date_to')
        
        if date_from and date_to:
            if date_from > date_to:
                raise serializers.ValidationError({
                    'date_to': 'End date must be after start date'
                })
        
        return attrs


class DataExportRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating data export requests"""
    
    class Meta:
        model = DataExportRequest
        fields = [
            'export_type',
            'date_from',
            'date_to',
            'format',
            'filters'
        ]
    
    def validate_export_type(self, value):
        """Validate export type"""
        valid_types = [
            'farmers', 'loans', 'scores', 'satellite',
            'compliance', 'audit_logs', 'full_backup'
        ]
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Export type must be one of: {valid_types}"
            )
        return value
    
    def validate_format(self, value):
        """Validate export format"""
        valid_formats = ['csv', 'json', 'xlsx', 'pdf']
        if value not in valid_formats:
            raise serializers.ValidationError(
                f"Format must be one of: {valid_formats}"
            )
        return value
    
    def create(self, validated_data):
        """Create export request with current user"""
        validated_data['requested_by'] = self.context['request'].user
        return super().create(validated_data)


class SystemDashboardSerializer(serializers.Serializer):
    """Serializer for system dashboard overview"""
    
    current_metrics = SystemMetricsSerializer()
    active_alerts = SystemAlertSerializer(many=True)
    recent_api_usage = APIUsageStatsSerializer()
    system_health = serializers.DictField()
    user_statistics = serializers.DictField()
    resource_usage = serializers.DictField()