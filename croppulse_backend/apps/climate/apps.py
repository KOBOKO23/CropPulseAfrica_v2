from django.apps import AppConfig


class ClimateConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.climate'
    label = 'climate'

    def ready(self):
        '''
        import signals or perform initialization tasks here
        '''
        pass