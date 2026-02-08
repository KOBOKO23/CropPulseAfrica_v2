# apps/admin_portal/urls.py

from django.urls import path
from .views import (
    # Feature Flags
    FeatureFlagListCreateView,
    FeatureFlagDetailView,
    toggle_feature_flag,
    feature_flag_usage_stats,
    
    # Tenant Feature Flags
    TenantFeatureFlagListCreateView,
    TenantFeatureFlagDetailView,
    
    # Global Settings
    GlobalSettingsListCreateView,
    GlobalSettingsDetailView,
    bulk_update_settings,
    export_settings,
    import_settings,
    
    # System Metrics
    SystemMetricsListView,
    collect_system_metrics,
    system_health_summary,
    
    # Bank Configuration
    BankConfigurationListView,
    BankConfigurationDetailView,
    bank_statistics,
    all_banks_overview,
    update_bank_quota,
    update_bank_billing_plan,
    
    # System Alerts
    SystemAlertListCreateView,
    SystemAlertDetailView,
    resolve_alert,
    bulk_resolve_alerts,
    
    # API Usage Logs
    APIUsageLogListView,
    api_usage_stats,
    
    # Data Export
    DataExportRequestListCreateView,
    DataExportRequestDetailView,
    
    # Dashboard
    admin_dashboard
)

app_name = 'admin_portal'

urlpatterns = [
    # ===========================
    # DASHBOARD
    # ===========================
    path('dashboard/', admin_dashboard, name='dashboard'),
    
    # ===========================
    # FEATURE FLAGS
    # ===========================
    path('feature-flags/', FeatureFlagListCreateView.as_view(), name='feature_flag_list'),
    path('feature-flags/<int:id>/', FeatureFlagDetailView.as_view(), name='feature_flag_detail'),
    path('feature-flags/<int:id>/toggle/', toggle_feature_flag, name='toggle_feature_flag'),
    path('feature-flags/<int:id>/stats/', feature_flag_usage_stats, name='feature_flag_stats'),
    
    # ===========================
    # TENANT FEATURE FLAGS
    # ===========================
    path('tenant-feature-flags/', TenantFeatureFlagListCreateView.as_view(), name='tenant_feature_flag_list'),
    path('tenant-feature-flags/<int:id>/', TenantFeatureFlagDetailView.as_view(), name='tenant_feature_flag_detail'),
    
    # ===========================
    # GLOBAL SETTINGS
    # ===========================
    path('settings/', GlobalSettingsListCreateView.as_view(), name='settings_list'),
    path('settings/<int:id>/', GlobalSettingsDetailView.as_view(), name='settings_detail'),
    path('settings/bulk-update/', bulk_update_settings, name='bulk_update_settings'),
    path('settings/export/', export_settings, name='export_settings'),
    path('settings/import/', import_settings, name='import_settings'),
    
    # ===========================
    # SYSTEM METRICS
    # ===========================
    path('metrics/', SystemMetricsListView.as_view(), name='metrics_list'),
    path('metrics/collect/', collect_system_metrics, name='collect_metrics'),
    path('health/', system_health_summary, name='system_health'),
    
    # ===========================
    # BANK CONFIGURATION
    # ===========================
    path('bank-configs/', BankConfigurationListView.as_view(), name='bank_config_list'),
    path('bank-configs/<int:id>/', BankConfigurationDetailView.as_view(), name='bank_config_detail'),
    path('banks/<int:bank_id>/stats/', bank_statistics, name='bank_stats'),
    path('banks/overview/', all_banks_overview, name='banks_overview'),
    path('banks/<int:bank_id>/quota/', update_bank_quota, name='update_bank_quota'),
    path('banks/<int:bank_id>/billing-plan/', update_bank_billing_plan, name='update_billing_plan'),
    
    # ===========================
    # SYSTEM ALERTS
    # ===========================
    path('alerts/', SystemAlertListCreateView.as_view(), name='alert_list'),
    path('alerts/<int:id>/', SystemAlertDetailView.as_view(), name='alert_detail'),
    path('alerts/<int:id>/resolve/', resolve_alert, name='resolve_alert'),
    path('alerts/bulk-resolve/', bulk_resolve_alerts, name='bulk_resolve_alerts'),
    
    # ===========================
    # API USAGE LOGS
    # ===========================
    path('api-logs/', APIUsageLogListView.as_view(), name='api_logs_list'),
    path('api-logs/stats/', api_usage_stats, name='api_usage_stats'),
    
    # ===========================
    # DATA EXPORT
    # ===========================
    path('exports/', DataExportRequestListCreateView.as_view(), name='export_list'),
    path('exports/<int:id>/', DataExportRequestDetailView.as_view(), name='export_detail'),
]