# apps/admin_portal/services/system_monitor.py

from django.db import connection
from django.core.cache import cache
from django.utils import timezone
import psutil
import time


class SystemMonitor:
    """
    Service for monitoring system health and performance
    """
    
    @staticmethod
    def collect_metrics():
        """
        Collect current system metrics
        
        Returns:
            dict: System metrics
        """
        from apps.admin_portal.models import SystemMetrics, APIUsageLog
        from django.contrib.auth import get_user_model
        from datetime import timedelta
        
        User = get_user_model()
        now = timezone.now()
        
        # Calculate time windows
        one_hour_ago = now - timedelta(hours=1)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # API Metrics
        api_calls_last_hour = APIUsageLog.objects.filter(
            timestamp__gte=one_hour_ago
        ).count()
        
        failed_api_calls = APIUsageLog.objects.filter(
            timestamp__gte=one_hour_ago,
            status_code__gte=400
        ).count()
        
        avg_response_time = APIUsageLog.objects.filter(
            timestamp__gte=one_hour_ago
        ).aggregate(
            avg_time=models.Avg('response_time')
        )['avg_time'] or 0.0
        
        # User Metrics
        active_users_count = User.objects.filter(
            last_activity__gte=one_hour_ago
        ).count()
        
        new_users_today = User.objects.filter(
            date_joined__gte=today_start
        ).count()
        
        # Database Metrics
        from apps.farmers.models import Farmer
        from apps.farms.models import Farm
        from apps.loans.models import Loan
        
        total_farmers = Farmer.objects.count()
        total_farms = Farm.objects.count()
        total_loans = Loan.objects.count()
        
        # System Resources
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Service Health
        database_status = SystemMonitor._check_database_health()
        redis_status = SystemMonitor._check_redis_health()
        celery_status = SystemMonitor._check_celery_health()
        gee_status = SystemMonitor._check_gee_health()
        nasa_power_status = SystemMonitor._check_nasa_power_health()
        
        # Create metrics record
        metrics = SystemMetrics.objects.create(
            total_api_calls=api_calls_last_hour,
            failed_api_calls=failed_api_calls,
            avg_response_time=round(avg_response_time, 2),
            active_users=active_users_count,
            new_users_today=new_users_today,
            total_farmers=total_farmers,
            total_farms=total_farms,
            total_loans=total_loans,
            cpu_usage=round(cpu_usage, 2),
            memory_usage=round(memory.percent, 2),
            disk_usage=round(disk.percent, 2),
            database_status=database_status,
            redis_status=redis_status,
            celery_status=celery_status,
            gee_status=gee_status,
            nasa_power_status=nasa_power_status
        )
        
        return metrics
    
    @staticmethod
    def _check_database_health():
        """Check database connectivity"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return 'healthy'
        except Exception:
            return 'down'
    
    @staticmethod
    def _check_redis_health():
        """Check Redis connectivity"""
        try:
            cache.set('health_check', 'ok', 10)
            value = cache.get('health_check')
            if value == 'ok':
                return 'healthy'
            return 'degraded'
        except Exception:
            return 'down'
    
    @staticmethod
    def _check_celery_health():
        """Check Celery workers status"""
        try:
            from celery import current_app
            
            inspect = current_app.control.inspect()
            stats = inspect.stats()
            
            if stats:
                return 'healthy'
            return 'down'
        except Exception:
            return 'down'
    
    @staticmethod
    def _check_gee_health():
        """Check Google Earth Engine API health"""
        try:
            import ee
            
            # Try a simple operation
            ee.Initialize()
            test = ee.Number(1).getInfo()
            
            if test == 1:
                return 'healthy'
            return 'degraded'
        except Exception:
            return 'down'
    
    @staticmethod
    def _check_nasa_power_health():
        """Check NASA POWER API health"""
        try:
            import requests
            
            # Simple health check endpoint
            response = requests.get(
                'https://power.larc.nasa.gov/api/system/manager/status',
                timeout=5
            )
            
            if response.status_code == 200:
                return 'healthy'
            return 'degraded'
        except Exception:
            return 'down'
    
    @staticmethod
    def get_current_metrics():
        """
        Get the most recent metrics
        
        Returns:
            SystemMetrics instance or None
        """
        from apps.admin_portal.models import SystemMetrics
        
        return SystemMetrics.objects.first()
    
    @staticmethod
    def get_metrics_history(hours=24):
        """
        Get metrics history for specified hours
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            QuerySet of SystemMetrics
        """
        from apps.admin_portal.models import SystemMetrics
        from datetime import timedelta
        
        since = timezone.now() - timedelta(hours=hours)
        
        return SystemMetrics.objects.filter(
            timestamp__gte=since
        ).order_by('timestamp')
    
    @staticmethod
    def create_alert_if_needed(metrics):
        """
        Create system alerts based on metrics
        
        Args:
            metrics: SystemMetrics instance
        """
        from apps.admin_portal.models import SystemAlert
        
        alerts = []
        
        # CPU usage alert
        if metrics.cpu_usage > 90:
            alerts.append({
                'title': 'High CPU Usage',
                'message': f'CPU usage is at {metrics.cpu_usage}%',
                'severity': 'critical' if metrics.cpu_usage > 95 else 'warning',
                'category': 'performance',
                'source': 'system_monitor'
            })
        
        # Memory usage alert
        if metrics.memory_usage > 90:
            alerts.append({
                'title': 'High Memory Usage',
                'message': f'Memory usage is at {metrics.memory_usage}%',
                'severity': 'critical' if metrics.memory_usage > 95 else 'warning',
                'category': 'performance',
                'source': 'system_monitor'
            })
        
        # Disk usage alert
        if metrics.disk_usage > 85:
            alerts.append({
                'title': 'High Disk Usage',
                'message': f'Disk usage is at {metrics.disk_usage}%',
                'severity': 'critical' if metrics.disk_usage > 95 else 'warning',
                'category': 'performance',
                'source': 'system_monitor'
            })
        
        # Service down alerts
        if metrics.database_status == 'down':
            alerts.append({
                'title': 'Database Down',
                'message': 'Database connection failed',
                'severity': 'critical',
                'category': 'system',
                'source': 'system_monitor'
            })
        
        if metrics.redis_status == 'down':
            alerts.append({
                'title': 'Redis Down',
                'message': 'Redis connection failed',
                'severity': 'error',
                'category': 'system',
                'source': 'system_monitor'
            })
        
        if metrics.celery_status == 'down':
            alerts.append({
                'title': 'Celery Workers Down',
                'message': 'No active Celery workers detected',
                'severity': 'error',
                'category': 'system',
                'source': 'system_monitor'
            })
        
        # API failure rate alert
        if metrics.total_api_calls > 0:
            failure_rate = (metrics.failed_api_calls / metrics.total_api_calls) * 100
            if failure_rate > 10:
                alerts.append({
                    'title': 'High API Failure Rate',
                    'message': f'API failure rate is at {failure_rate:.2f}%',
                    'severity': 'warning',
                    'category': 'performance',
                    'source': 'system_monitor'
                })
        
        # Create alerts
        for alert_data in alerts:
            # Check if similar alert already exists and is not resolved
            existing = SystemAlert.objects.filter(
                title=alert_data['title'],
                is_resolved=False,
                created_at__gte=timezone.now() - timezone.timedelta(hours=1)
            ).exists()
            
            if not existing:
                SystemAlert.objects.create(**alert_data)
    
    @staticmethod
    def get_system_health_summary():
        """
        Get overall system health summary
        
        Returns:
            dict: Health summary
        """
        metrics = SystemMonitor.get_current_metrics()
        
        if not metrics:
            return {
                'status': 'unknown',
                'message': 'No metrics available'
            }
        
        # Check critical services
        critical_services = [
            metrics.database_status,
            metrics.redis_status,
        ]
        
        important_services = [
            metrics.celery_status,
            metrics.gee_status,
            metrics.nasa_power_status
        ]
        
        # Determine overall health
        if 'down' in critical_services:
            status = 'critical'
            message = 'Critical services are down'
        elif 'down' in important_services or 'degraded' in critical_services:
            status = 'degraded'
            message = 'Some services are experiencing issues'
        elif metrics.cpu_usage > 90 or metrics.memory_usage > 90:
            status = 'warning'
            message = 'High resource usage detected'
        else:
            status = 'healthy'
            message = 'All systems operational'
        
        return {
            'status': status,
            'message': message,
            'timestamp': metrics.timestamp,
            'services': {
                'database': metrics.database_status,
                'redis': metrics.redis_status,
                'celery': metrics.celery_status,
                'gee': metrics.gee_status,
                'nasa_power': metrics.nasa_power_status
            },
            'resources': {
                'cpu': metrics.cpu_usage,
                'memory': metrics.memory_usage,
                'disk': metrics.disk_usage
            }
        }
    
    @staticmethod
    def cleanup_old_metrics(days=30):
        """
        Clean up old metrics data
        
        Args:
            days: Keep metrics from last N days
            
        Returns:
            int: Number of metrics deleted
        """
        from apps.admin_portal.models import SystemMetrics
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        deleted_count = SystemMetrics.objects.filter(
            timestamp__lt=cutoff_date
        ).delete()[0]
        
        return deleted_count


from django.db import models  # Import for aggregate functions