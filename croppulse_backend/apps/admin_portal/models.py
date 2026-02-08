# apps/admin_portal/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.mixins import TimestampMixin


class FeatureFlag(TimestampMixin):
    """
    Feature flags for enabling/disabling features per tenant or globally
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text='Unique feature identifier (e.g., "satellite_verification")'
    )
    
    display_name = models.CharField(
        max_length=200,
        help_text='Human-readable feature name'
    )
    
    description = models.TextField(
        blank=True,
        help_text='Detailed description of the feature'
    )
    
    is_enabled = models.BooleanField(
        default=False,
        help_text='Global feature status'
    )
    
    is_beta = models.BooleanField(
        default=False,
        help_text='Mark as beta feature'
    )
    
    category = models.CharField(
        max_length=50,
        choices=[
            ('verification', 'Verification'),
            ('analytics', 'Analytics'),
            ('compliance', 'Compliance'),
            ('notifications', 'Notifications'),
            ('loans', 'Loans'),
            ('climate', 'Climate'),
            ('fraud', 'Fraud Detection'),
            ('general', 'General'),
        ],
        default='general'
    )
    
    # Rollout configuration
    rollout_percentage = models.IntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Percentage of users who can access this feature (0-100)'
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional configuration parameters'
    )
    
    class Meta:
        db_table = 'admin_feature_flags'
        ordering = ['category', 'display_name']
        indexes = [
            models.Index(fields=['name', 'is_enabled']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        status = "Enabled" if self.is_enabled else "Disabled"
        return f"{self.display_name} ({status})"


class TenantFeatureFlag(TimestampMixin):
    """
    Feature flags per tenant (bank/exporter)
    """
    feature_flag = models.ForeignKey(
        FeatureFlag,
        on_delete=models.CASCADE,
        related_name='tenant_overrides'
    )
    
    tenant_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        limit_choices_to={'user_type__in': ['bank', 'exporter']},
        related_name='feature_overrides'
    )
    
    is_enabled = models.BooleanField(
        default=False,
        help_text='Override global feature status for this tenant'
    )
    
    custom_config = models.JSONField(
        default=dict,
        blank=True,
        help_text='Tenant-specific configuration'
    )
    
    class Meta:
        db_table = 'admin_tenant_feature_flags'
        unique_together = ['feature_flag', 'tenant_user']
        ordering = ['tenant_user', 'feature_flag']
    
    def __str__(self):
        return f"{self.tenant_user.username} - {self.feature_flag.name}"


class GlobalSettings(TimestampMixin):
    """
    System-wide configuration settings
    """
    CATEGORY_CHOICES = [
        ('system', 'System'),
        ('api', 'API'),
        ('notifications', 'Notifications'),
        ('security', 'Security'),
        ('integrations', 'Integrations'),
        ('scoring', 'Scoring'),
        ('limits', 'Limits'),
    ]
    
    key = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text='Setting key (e.g., "max_api_calls_per_hour")'
    )
    
    value = models.TextField(
        help_text='Setting value (can be JSON string for complex values)'
    )
    
    value_type = models.CharField(
        max_length=20,
        choices=[
            ('string', 'String'),
            ('integer', 'Integer'),
            ('float', 'Float'),
            ('boolean', 'Boolean'),
            ('json', 'JSON'),
        ],
        default='string'
    )
    
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='system'
    )
    
    description = models.TextField(
        blank=True,
        help_text='Description of what this setting controls'
    )
    
    is_sensitive = models.BooleanField(
        default=False,
        help_text='Mark as sensitive (e.g., API keys, passwords)'
    )
    
    is_editable = models.BooleanField(
        default=True,
        help_text='Can be edited via admin interface'
    )
    
    class Meta:
        db_table = 'admin_global_settings'
        ordering = ['category', 'key']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['key']),
        ]
    
    def __str__(self):
        return f"{self.key} = {self.value[:50]}"
    
    def get_value(self):
        """Parse and return the typed value"""
        if self.value_type == 'integer':
            return int(self.value)
        elif self.value_type == 'float':
            return float(self.value)
        elif self.value_type == 'boolean':
            return self.value.lower() in ['true', '1', 'yes']
        elif self.value_type == 'json':
            import json
            return json.loads(self.value)
        return self.value


class SystemMetrics(models.Model):
    """
    System performance and health metrics
    """
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # API Metrics
    total_api_calls = models.IntegerField(default=0)
    failed_api_calls = models.IntegerField(default=0)
    avg_response_time = models.FloatField(default=0.0, help_text='in milliseconds')
    
    # User Metrics
    active_users = models.IntegerField(default=0)
    new_users_today = models.IntegerField(default=0)
    
    # Database Metrics
    total_farmers = models.IntegerField(default=0)
    total_farms = models.IntegerField(default=0)
    total_loans = models.IntegerField(default=0)
    
    # System Health
    cpu_usage = models.FloatField(default=0.0, help_text='CPU usage percentage')
    memory_usage = models.FloatField(default=0.0, help_text='Memory usage percentage')
    disk_usage = models.FloatField(default=0.0, help_text='Disk usage percentage')
    
    # Service Status
    database_status = models.CharField(
        max_length=20,
        choices=[
            ('healthy', 'Healthy'),
            ('degraded', 'Degraded'),
            ('down', 'Down'),
        ],
        default='healthy'
    )
    
    redis_status = models.CharField(
        max_length=20,
        choices=[
            ('healthy', 'Healthy'),
            ('degraded', 'Degraded'),
            ('down', 'Down'),
        ],
        default='healthy'
    )
    
    celery_status = models.CharField(
        max_length=20,
        choices=[
            ('healthy', 'Healthy'),
            ('degraded', 'Degraded'),
            ('down', 'Down'),
        ],
        default='healthy'
    )
    
    # External Services
    gee_status = models.CharField(
        max_length=20,
        choices=[
            ('healthy', 'Healthy'),
            ('degraded', 'Degraded'),
            ('down', 'Down'),
        ],
        default='healthy',
        help_text='Google Earth Engine status'
    )
    
    nasa_power_status = models.CharField(
        max_length=20,
        choices=[
            ('healthy', 'Healthy'),
            ('degraded', 'Degraded'),
            ('down', 'Down'),
        ],
        default='healthy',
        help_text='NASA POWER API status'
    )
    
    # Additional metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'admin_system_metrics'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
        ]
        verbose_name = 'System Metric'
        verbose_name_plural = 'System Metrics'
    
    def __str__(self):
        return f"Metrics at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class BankConfiguration(TimestampMixin):
    """
    Configuration settings per bank
    """
    bank = models.OneToOneField(
        'banks.Bank',
        on_delete=models.CASCADE,
        related_name='configuration'
    )
    
    # API Configuration
    api_rate_limit = models.IntegerField(
        default=1000,
        help_text='Max API calls per hour'
    )
    
    webhook_url = models.URLField(
        max_length=500,
        blank=True,
        help_text='Webhook URL for notifications'
    )
    
    webhook_secret = models.CharField(
        max_length=100,
        blank=True,
        help_text='Secret key for webhook signature verification'
    )
    
    # Feature limits
    max_farmers = models.IntegerField(
        default=10000,
        help_text='Maximum number of farmers this bank can manage'
    )
    
    max_loans_per_farmer = models.IntegerField(
        default=5,
        help_text='Maximum active loans per farmer'
    )
    
    # Scoring configuration
    min_credit_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Minimum acceptable credit score (0-100)'
    )
    
    use_satellite_verification = models.BooleanField(
        default=True,
        help_text='Enable satellite verification for this bank'
    )
    
    use_climate_risk_assessment = models.BooleanField(
        default=True,
        help_text='Enable climate risk assessment'
    )
    
    use_fraud_detection = models.BooleanField(
        default=True,
        help_text='Enable fraud detection'
    )
    
    # Notification preferences
    notification_channels = models.JSONField(
        default=list,
        blank=True,
        help_text='Enabled notification channels: ["email", "sms", "webhook"]'
    )
    
    # Billing
    billing_plan = models.CharField(
        max_length=50,
        choices=[
            ('free', 'Free'),
            ('basic', 'Basic'),
            ('professional', 'Professional'),
            ('enterprise', 'Enterprise'),
        ],
        default='basic'
    )
    
    monthly_api_quota = models.IntegerField(
        default=50000,
        help_text='Monthly API call quota'
    )
    
    # Custom configuration
    custom_config = models.JSONField(
        default=dict,
        blank=True,
        help_text='Bank-specific custom configuration'
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text='Is this bank configuration active'
    )
    
    class Meta:
        db_table = 'admin_bank_configurations'
        ordering = ['bank']
    
    def __str__(self):
        return f"Config for {self.bank.name}"


class SystemAlert(TimestampMixin):
    """
    System-wide alerts and notifications for admins
    """
    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]
    
    CATEGORY_CHOICES = [
        ('system', 'System'),
        ('security', 'Security'),
        ('performance', 'Performance'),
        ('data', 'Data'),
        ('integration', 'Integration'),
    ]
    
    title = models.CharField(max_length=200)
    
    message = models.TextField()
    
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='info'
    )
    
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='system'
    )
    
    is_resolved = models.BooleanField(
        default=False,
        help_text='Has this alert been resolved?'
    )
    
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    resolved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_alerts'
    )
    
    # Alert metadata
    source = models.CharField(
        max_length=100,
        blank=True,
        help_text='Source of the alert (e.g., "celery_worker", "api_monitor")'
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional alert data'
    )
    
    # Notification tracking
    notification_sent = models.BooleanField(
        default=False,
        help_text='Has notification been sent to admins?'
    )
    
    notification_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'admin_system_alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['severity', '-created_at']),
            models.Index(fields=['category', 'is_resolved']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"[{self.severity.upper()}] {self.title}"
    
    def resolve(self, user):
        """Mark alert as resolved"""
        from django.utils import timezone
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.save()


class APIUsageLog(models.Model):
    """
    Detailed API usage logging for analytics and billing
    """
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Request details
    bank = models.ForeignKey(
        'banks.Bank',
        on_delete=models.CASCADE,
        related_name='api_usage_logs',
        null=True,
        blank=True
    )
    
    endpoint = models.CharField(max_length=200, db_index=True)
    
    method = models.CharField(
        max_length=10,
        choices=[
            ('GET', 'GET'),
            ('POST', 'POST'),
            ('PUT', 'PUT'),
            ('PATCH', 'PATCH'),
            ('DELETE', 'DELETE'),
        ]
    )
    
    # Response details
    status_code = models.IntegerField()
    
    response_time = models.FloatField(
        help_text='Response time in milliseconds'
    )
    
    # Request metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    user_agent = models.TextField(blank=True)
    
    request_size = models.IntegerField(
        default=0,
        help_text='Request size in bytes'
    )
    
    response_size = models.IntegerField(
        default=0,
        help_text='Response size in bytes'
    )
    
    # Additional data
    error_message = models.TextField(
        blank=True,
        help_text='Error message if request failed'
    )
    
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'admin_api_usage_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['bank', '-timestamp']),
            models.Index(fields=['endpoint', '-timestamp']),
            models.Index(fields=['-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.method} {self.endpoint} - {self.status_code}"


class DataExportRequest(TimestampMixin):
    """
    Track data export requests for compliance and auditing
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    requested_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='export_requests'
    )
    
    export_type = models.CharField(
        max_length=50,
        choices=[
            ('farmers', 'Farmers Data'),
            ('loans', 'Loans Data'),
            ('scores', 'Credit Scores'),
            ('satellite', 'Satellite Data'),
            ('compliance', 'Compliance Certificates'),
            ('audit_logs', 'Audit Logs'),
            ('full_backup', 'Full Database Backup'),
        ]
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Date range for export
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    
    # Export configuration
    format = models.CharField(
        max_length=10,
        choices=[
            ('csv', 'CSV'),
            ('json', 'JSON'),
            ('xlsx', 'Excel'),
            ('pdf', 'PDF'),
        ],
        default='csv'
    )
    
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional filters for the export'
    )
    
    # Result
    file_url = models.URLField(
        max_length=500,
        blank=True,
        help_text='URL to download the exported file'
    )
    
    file_size = models.IntegerField(
        default=0,
        help_text='File size in bytes'
    )
    
    records_count = models.IntegerField(
        default=0,
        help_text='Number of records exported'
    )
    
    error_message = models.TextField(blank=True)
    
    # Completion tracking
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Expiry (for temporary downloads)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the download link expires'
    )
    
    class Meta:
        db_table = 'admin_data_export_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['requested_by', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.export_type} export by {self.requested_by.username} - {self.status}"