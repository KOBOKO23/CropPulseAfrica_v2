# compliance/apps.py
from django.apps import AppConfig


class ComplianceConfig(AppConfig):
    """Configuration for compliance app"""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.compliance'
    label = 'compliance'
    
    def ready(self):
        """Import signals when app is ready"""
        try:
            import apps.compliance.signals  # noqa
        except ImportError:
            pass