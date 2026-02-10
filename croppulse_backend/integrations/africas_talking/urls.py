# USSD URLs

from django.urls import path
from .ussd import ussd_callback

urlpatterns = [
    path('callback/', ussd_callback, name='ussd-callback'),
]
