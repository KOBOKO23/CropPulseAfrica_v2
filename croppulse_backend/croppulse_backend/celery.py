import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'croppulse_backend.settings.base')

app = Celery('croppulse_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
