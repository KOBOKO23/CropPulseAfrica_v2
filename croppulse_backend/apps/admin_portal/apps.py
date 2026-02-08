# apps/admin_portal/apps.py

from django.apps import AppConfig


class AdminPortalConfig(AppConfig):
    """Configuration for Admin Portal app"""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.admin_portal'
    label = 'admin_portal'
    
    def ready(self):
        """Initialize app when Django starts"""
        # Import signal handlers if any
        pass