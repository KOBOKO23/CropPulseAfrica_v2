# apps/admin_portal/views.py

from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta

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
from .serializers import (
    FeatureFlagSerializer,
    TenantFeatureFlagSerializer,
    GlobalSettingsSerializer,
    SystemMetricsSerializer,
    BankConfigurationSerializer,
    SystemAlertSerializer,
    SystemAlertCreateSerializer,
    APIUsageLogSerializer,
    APIUsageStatsSerializer,
    DataExportRequestSerializer,
    DataExportRequestCreateSerializer,
    SystemDashboardSerializer
)
from .services import (
    FeatureFlagService,
    GlobalSettingsService,
    SystemMonitor,
    BankManager
)
from core.permissions import IsAdminOnly


# ===========================
# FEATURE FLAGS
# ===========================

class FeatureFlagListCreateView(generics.ListCreateAPIView):
    """
    GET/POST /api/v1/admin/feature-flags/
    List and create feature flags
    """
    queryset = FeatureFlag.objects.all()
    serializer_class = FeatureFlagSerializer
    permission_classes = [IsAdminOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by enabled status
        is_enabled = self.request.query_params.get('is_enabled')
        if is_enabled is not None:
            queryset = queryset.filter(is_enabled=is_enabled.lower() == 'true')
        
        # Filter by beta status
        is_beta = self.request.query_params.get('is_beta')
        if is_beta is not None:
            queryset = queryset.filter(is_beta=is_beta.lower() == 'true')
        
        return queryset.order_by('category', 'display_name')


class FeatureFlagDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/v1/admin/feature-flags/{id}/
    Retrieve, update, or delete a feature flag
    """
    queryset = FeatureFlag.objects.all()
    serializer_class = FeatureFlagSerializer
    permission_classes = [IsAdminOnly]
    lookup_field = 'id'


@api_view(['POST'])
@permission_classes([IsAdminOnly])
def toggle_feature_flag(request, id):
    """
    POST /api/v1/admin/feature-flags/{id}/toggle/
    Toggle feature flag enabled status
    """
    try:
        feature_flag = FeatureFlag.objects.get(id=id)
        feature_flag.is_enabled = not feature_flag.is_enabled
        feature_flag.save()
        
        # Clear cache
        FeatureFlagService.clear_cache(feature_flag.name)
        
        return Response({
            'message': f'Feature flag {"enabled" if feature_flag.is_enabled else "disabled"}',
            'feature': FeatureFlagSerializer(feature_flag).data
        }, status=status.HTTP_200_OK)
    
    except FeatureFlag.DoesNotExist:
        return Response({'error': 'Feature flag not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAdminOnly])
def feature_flag_usage_stats(request, id):
    """
    GET /api/v1/admin/feature-flags/{id}/stats/
    Get usage statistics for a feature flag
    """
    try:
        feature_flag = FeatureFlag.objects.get(id=id)
        stats = FeatureFlagService.get_feature_usage_stats(feature_flag.name)
        
        return Response(stats, status=status.HTTP_200_OK)
    
    except FeatureFlag.DoesNotExist:
        return Response({'error': 'Feature flag not found'}, status=status.HTTP_404_NOT_FOUND)


# ===========================
# TENANT FEATURE FLAGS
# ===========================

class TenantFeatureFlagListCreateView(generics.ListCreateAPIView):
    """
    GET/POST /api/v1/admin/tenant-feature-flags/
    List and create tenant-specific feature flag overrides
    """
    queryset = TenantFeatureFlag.objects.all()
    serializer_class = TenantFeatureFlagSerializer
    permission_classes = [IsAdminOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by tenant
        tenant_id = self.request.query_params.get('tenant_id')
        if tenant_id:
            queryset = queryset.filter(tenant_user_id=tenant_id)
        
        # Filter by feature flag
        feature_flag_id = self.request.query_params.get('feature_flag_id')
        if feature_flag_id:
            queryset = queryset.filter(feature_flag_id=feature_flag_id)
        
        return queryset.select_related('feature_flag', 'tenant_user')


class TenantFeatureFlagDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/v1/admin/tenant-feature-flags/{id}/
    Manage tenant feature flag override
    """
    queryset = TenantFeatureFlag.objects.all()
    serializer_class = TenantFeatureFlagSerializer
    permission_classes = [IsAdminOnly]
    lookup_field = 'id'


# ===========================
# GLOBAL SETTINGS
# ===========================

class GlobalSettingsListCreateView(generics.ListCreateAPIView):
    """
    GET/POST /api/v1/admin/settings/
    List and create global settings
    """
    queryset = GlobalSettings.objects.all()
    serializer_class = GlobalSettingsSerializer
    permission_classes = [IsAdminOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter out sensitive settings for non-superusers
        if not self.request.user.is_superuser:
            queryset = queryset.filter(is_sensitive=False)
        
        return queryset.order_by('category', 'key')
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['show_sensitive'] = self.request.user.is_superuser
        return context


class GlobalSettingsDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/v1/admin/settings/{id}/
    Manage global setting
    """
    queryset = GlobalSettings.objects.all()
    serializer_class = GlobalSettingsSerializer
    permission_classes = [IsAdminOnly]
    lookup_field = 'id'
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['show_sensitive'] = self.request.user.is_superuser
        return context


@api_view(['POST'])
@permission_classes([IsAdminOnly])
def bulk_update_settings(request):
    """
    POST /api/v1/admin/settings/bulk-update/
    Update multiple settings at once
    """
    settings_data = request.data.get('settings', {})
    
    if not isinstance(settings_data, dict):
        return Response({'error': 'Settings must be a dictionary'}, status=status.HTTP_400_BAD_REQUEST)
    
    updated_count = GlobalSettingsService.bulk_update_settings(settings_data)
    
    return Response({
        'message': f'Updated {updated_count} settings',
        'count': updated_count
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminOnly])
def export_settings(request):
    """
    GET /api/v1/admin/settings/export/
    Export all settings as JSON
    """
    json_data = GlobalSettingsService.export_settings()
    
    return Response({
        'settings': json_data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminOnly])
def import_settings(request):
    """
    POST /api/v1/admin/settings/import/
    Import settings from JSON
    """
    json_data = request.data.get('settings')
    
    if not json_data:
        return Response({'error': 'Settings data required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        imported_count = GlobalSettingsService.import_settings(json_data)
        
        return Response({
            'message': f'Imported {imported_count} settings',
            'count': imported_count
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ===========================
# SYSTEM METRICS
# ===========================

class SystemMetricsListView(generics.ListAPIView):
    """
    GET /api/v1/admin/metrics/
    List system metrics history
    """
    queryset = SystemMetrics.objects.all()
    serializer_class = SystemMetricsSerializer
    permission_classes = [IsAdminOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by date range
        from_date = self.request.query_params.get('from_date')
        to_date = self.request.query_params.get('to_date')
        
        if from_date:
            queryset = queryset.filter(timestamp__gte=from_date)
        if to_date:
            queryset = queryset.filter(timestamp__lte=to_date)
        
        # Limit to recent metrics by default
        hours = self.request.query_params.get('hours', 24)
        try:
            hours = int(hours)
            since = timezone.now() - timedelta(hours=hours)
            queryset = queryset.filter(timestamp__gte=since)
        except ValueError:
            pass
        
        return queryset.order_by('-timestamp')


@api_view(['POST'])
@permission_classes([IsAdminOnly])
def collect_system_metrics(request):
    """
    POST /api/v1/admin/metrics/collect/
    Manually trigger system metrics collection
    """
    try:
        metrics = SystemMonitor.collect_metrics()
        
        # Create alerts if needed
        SystemMonitor.create_alert_if_needed(metrics)
        
        return Response({
            'message': 'Metrics collected successfully',
            'metrics': SystemMetricsSerializer(metrics).data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminOnly])
def system_health_summary(request):
    """
    GET /api/v1/admin/health/
    Get overall system health summary
    """
    summary = SystemMonitor.get_system_health_summary()
    return Response(summary, status=status.HTTP_200_OK)
# apps/admin_portal/views.py (Part 2)

# ===========================
# BANK CONFIGURATION
# ===========================

class BankConfigurationListView(generics.ListAPIView):
    """
    GET /api/v1/admin/bank-configs/
    List all bank configurations
    """
    queryset = BankConfiguration.objects.all()
    serializer_class = BankConfigurationSerializer
    permission_classes = [IsAdminOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by billing plan
        billing_plan = self.request.query_params.get('billing_plan')
        if billing_plan:
            queryset = queryset.filter(billing_plan=billing_plan)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.select_related('bank', 'bank__user')


class BankConfigurationDetailView(generics.RetrieveUpdateAPIView):
    """
    GET/PUT/PATCH /api/v1/admin/bank-configs/{id}/
    Manage bank configuration
    """
    queryset = BankConfiguration.objects.all()
    serializer_class = BankConfigurationSerializer
    permission_classes = [IsAdminOnly]
    lookup_field = 'id'


@api_view(['GET'])
@permission_classes([IsAdminOnly])
def bank_statistics(request, bank_id):
    """
    GET /api/v1/admin/banks/{bank_id}/stats/
    Get comprehensive statistics for a bank
    """
    from apps.banks.models import Bank
    
    try:
        bank = Bank.objects.get(id=bank_id)
        stats = BankManager.get_bank_stats(bank)
        
        return Response(stats, status=status.HTTP_200_OK)
    
    except Bank.DoesNotExist:
        return Response({'error': 'Bank not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAdminOnly])
def all_banks_overview(request):
    """
    GET /api/v1/admin/banks/overview/
    Get overview of all banks
    """
    overview = BankManager.get_all_banks_overview()
    return Response(overview, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminOnly])
def update_bank_quota(request, bank_id):
    """
    POST /api/v1/admin/banks/{bank_id}/quota/
    Update API quota for a bank
    """
    from apps.banks.models import Bank
    
    try:
        bank = Bank.objects.get(id=bank_id)
        new_quota = request.data.get('quota')
        
        if not new_quota or not isinstance(new_quota, int):
            return Response({'error': 'Valid quota required'}, status=status.HTTP_400_BAD_REQUEST)
        
        BankManager.update_api_quota(bank, new_quota)
        
        return Response({
            'message': 'Quota updated successfully',
            'bank': bank.name,
            'new_quota': new_quota
        }, status=status.HTTP_200_OK)
    
    except Bank.DoesNotExist:
        return Response({'error': 'Bank not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAdminOnly])
def update_bank_billing_plan(request, bank_id):
    """
    POST /api/v1/admin/banks/{bank_id}/billing-plan/
    Update billing plan for a bank
    """
    from apps.banks.models import Bank
    
    try:
        bank = Bank.objects.get(id=bank_id)
        plan = request.data.get('plan')
        
        if not plan:
            return Response({'error': 'Billing plan required'}, status=status.HTTP_400_BAD_REQUEST)
        
        BankManager.update_billing_plan(bank, plan)
        
        return Response({
            'message': 'Billing plan updated successfully',
            'bank': bank.name,
            'plan': plan
        }, status=status.HTTP_200_OK)
    
    except Bank.DoesNotExist:
        return Response({'error': 'Bank not found'}, status=status.HTTP_404_NOT_FOUND)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ===========================
# SYSTEM ALERTS
# ===========================

class SystemAlertListCreateView(generics.ListCreateAPIView):
    """
    GET/POST /api/v1/admin/alerts/
    List and create system alerts
    """
    queryset = SystemAlert.objects.all()
    permission_classes = [IsAdminOnly]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SystemAlertCreateSerializer
        return SystemAlertSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by severity
        severity = self.request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by resolved status
        is_resolved = self.request.query_params.get('is_resolved')
        if is_resolved is not None:
            queryset = queryset.filter(is_resolved=is_resolved.lower() == 'true')
        
        return queryset.order_by('-created_at')


class SystemAlertDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/v1/admin/alerts/{id}/
    Manage system alert
    """
    queryset = SystemAlert.objects.all()
    serializer_class = SystemAlertSerializer
    permission_classes = [IsAdminOnly]
    lookup_field = 'id'


@api_view(['POST'])
@permission_classes([IsAdminOnly])
def resolve_alert(request, id):
    """
    POST /api/v1/admin/alerts/{id}/resolve/
    Mark alert as resolved
    """
    try:
        alert = SystemAlert.objects.get(id=id)
        alert.resolve(request.user)
        
        return Response({
            'message': 'Alert resolved successfully',
            'alert': SystemAlertSerializer(alert).data
        }, status=status.HTTP_200_OK)
    
    except SystemAlert.DoesNotExist:
        return Response({'error': 'Alert not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAdminOnly])
def bulk_resolve_alerts(request):
    """
    POST /api/v1/admin/alerts/bulk-resolve/
    Resolve multiple alerts
    """
    alert_ids = request.data.get('alert_ids', [])
    
    if not isinstance(alert_ids, list):
        return Response({'error': 'alert_ids must be a list'}, status=status.HTTP_400_BAD_REQUEST)
    
    alerts = SystemAlert.objects.filter(id__in=alert_ids, is_resolved=False)
    
    for alert in alerts:
        alert.resolve(request.user)
    
    return Response({
        'message': f'Resolved {alerts.count()} alerts',
        'count': alerts.count()
    }, status=status.HTTP_200_OK)


# ===========================
# API USAGE LOGS
# ===========================

class APIUsageLogListView(generics.ListAPIView):
    """
    GET /api/v1/admin/api-logs/
    List API usage logs
    """
    queryset = APIUsageLog.objects.all()
    serializer_class = APIUsageLogSerializer
    permission_classes = [IsAdminOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by bank
        bank_id = self.request.query_params.get('bank_id')
        if bank_id:
            queryset = queryset.filter(bank_id=bank_id)
        
        # Filter by endpoint
        endpoint = self.request.query_params.get('endpoint')
        if endpoint:
            queryset = queryset.filter(endpoint__icontains=endpoint)
        
        # Filter by status code
        status_code = self.request.query_params.get('status_code')
        if status_code:
            queryset = queryset.filter(status_code=status_code)
        
        # Filter by errors only
        errors_only = self.request.query_params.get('errors_only')
        if errors_only and errors_only.lower() == 'true':
            queryset = queryset.filter(status_code__gte=400)
        
        # Date range
        from_date = self.request.query_params.get('from_date')
        to_date = self.request.query_params.get('to_date')
        
        if from_date:
            queryset = queryset.filter(timestamp__gte=from_date)
        if to_date:
            queryset = queryset.filter(timestamp__lte=to_date)
        
        # Default to last 24 hours
        if not from_date and not to_date:
            since = timezone.now() - timedelta(hours=24)
            queryset = queryset.filter(timestamp__gte=since)
        
        return queryset.select_related('bank').order_by('-timestamp')


@api_view(['GET'])
@permission_classes([IsAdminOnly])
def api_usage_stats(request):
    """
    GET /api/v1/admin/api-logs/stats/
    Get API usage statistics
    """
    # Get time range
    days = int(request.query_params.get('days', 7))
    since = timezone.now() - timedelta(days=days)
    
    # Get bank if specified
    bank_id = request.query_params.get('bank_id')
    
    logs = APIUsageLog.objects.filter(timestamp__gte=since)
    
    if bank_id:
        logs = logs.filter(bank_id=bank_id)
    
    # Calculate stats
    total_requests = logs.count()
    successful_requests = logs.filter(status_code__lt=400).count()
    failed_requests = logs.filter(status_code__gte=400).count()
    
    success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
    
    avg_response_time = logs.aggregate(
        avg=Avg('response_time')
    )['avg'] or 0.0
    
    total_data = logs.aggregate(
        total=Sum('request_size') + Sum('response_size')
    )['total'] or 0
    
    # Top endpoints
    top_endpoints = logs.values('endpoint', 'method').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Requests by status
    requests_by_status = logs.values('status_code').annotate(
        count=Count('id')
    ).order_by('status_code')
    
    # Requests over time
    requests_over_time = []
    for i in range(days):
        day = timezone.now() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        count = logs.filter(timestamp__gte=day_start, timestamp__lt=day_end).count()
        
        requests_over_time.append({
            'date': day_start.date().isoformat(),
            'count': count
        })
    
    stats = {
        'total_requests': total_requests,
        'successful_requests': successful_requests,
        'failed_requests': failed_requests,
        'success_rate': round(success_rate, 2),
        'avg_response_time': round(avg_response_time, 2),
        'total_data_transferred': total_data,
        'top_endpoints': list(top_endpoints),
        'requests_by_status': list(requests_by_status),
        'requests_over_time': requests_over_time[::-1]
    }
    
    serializer = APIUsageStatsSerializer(stats)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ===========================
# DATA EXPORT
# ===========================

class DataExportRequestListCreateView(generics.ListCreateAPIView):
    """
    GET/POST /api/v1/admin/exports/
    List and create data export requests
    """
    queryset = DataExportRequest.objects.all()
    permission_classes = [IsAdminOnly]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DataExportRequestCreateSerializer
        return DataExportRequestSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by export type
        export_type = self.request.query_params.get('export_type')
        if export_type:
            queryset = queryset.filter(export_type=export_type)
        
        # Filter by requester
        requested_by = self.request.query_params.get('requested_by')
        if requested_by:
            queryset = queryset.filter(requested_by_id=requested_by)
        
        return queryset.select_related('requested_by').order_by('-created_at')


class DataExportRequestDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/admin/exports/{id}/
    Get export request details
    """
    queryset = DataExportRequest.objects.all()
    serializer_class = DataExportRequestSerializer
    permission_classes = [IsAdminOnly]
    lookup_field = 'id'


# ===========================
# DASHBOARD
# ===========================

@api_view(['GET'])
@permission_classes([IsAdminOnly])
def admin_dashboard(request):
    """
    GET /api/v1/admin/dashboard/
    Get comprehensive admin dashboard data
    """
    from django.contrib.auth import get_user_model
    from apps.farmers.models import Farmer
    from apps.loans.models import Loan
    from apps.banks.models import Bank
    from apps.compliance.models import ExportPassport
    
    User = get_user_model()
    
    # Current metrics
    current_metrics = SystemMonitor.get_current_metrics()
    
    # Active alerts
    active_alerts = SystemAlert.objects.filter(is_resolved=False).order_by('-severity', '-created_at')[:10]
    
    # Recent API usage
    api_stats_data = {
        'days': 7,
        'bank_id': None
    }
    # This would call api_usage_stats logic
    
    # System health
    system_health = SystemMonitor.get_system_health_summary()
    
    # User statistics
    thirty_days_ago = timezone.now() - timedelta(days=30)
    user_stats = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(last_activity__gte=thirty_days_ago).count(),
        'new_users_this_month': User.objects.filter(date_joined__gte=thirty_days_ago).count(),
        'by_type': dict(User.objects.values('user_type').annotate(count=Count('id')).values_list('user_type', 'count'))
    }
    
    # Resource usage
    resource_usage = {
        'farmers': Farmer.objects.count(),
        'banks': Bank.objects.count(),
        'active_loans': Loan.objects.filter(status='active').count(),
        'total_loans': Loan.objects.count()
    }
    
    # EUDR Compliance statistics
    eudr_stats = {
        'total_passports': ExportPassport.objects.count(),
        'active_passports': ExportPassport.objects.filter(is_active=True).count(),
        'expiring_soon': ExportPassport.objects.filter(
            valid_until__lte=timezone.now().date() + timedelta(days=30),
            is_active=True
        ).count(),
        'by_status': dict(ExportPassport.objects.values('deforestation_status').annotate(count=Count('id')).values_list('deforestation_status', 'count')),
        'recent_passports': ExportPassport.objects.order_by('-issued_date')[:5].values(
            'passport_id', 'farm__farm_id', 'farmer__user__first_name', 'farmer__user__last_name', 
            'issued_date', 'deforestation_status'
        )
    }
    
    dashboard_data = {
        'current_metrics': SystemMetricsSerializer(current_metrics).data if current_metrics else None,
        'active_alerts': SystemAlertSerializer(active_alerts, many=True).data,
        'system_health': system_health,
        'user_statistics': user_stats,
        'resource_usage': resource_usage,
        'eudr_compliance': eudr_stats
    }
    
    return Response(dashboard_data, status=status.HTTP_200_OK)