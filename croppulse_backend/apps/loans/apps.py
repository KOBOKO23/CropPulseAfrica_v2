"""
Loans App Configuration
"""

from django.apps import AppConfig


class LoansConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.loans'
    label = 'loans'
    
    def ready(self):
        """Import signals/tasks when app is ready"""
        # Import tasks to register them with Celery
        try:
            import apps.loans.tasks
        except ImportError:
            pass