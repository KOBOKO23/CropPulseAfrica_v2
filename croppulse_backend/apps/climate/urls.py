# apps/climate/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('data/', views.get_climate_data, name='climate-data'),
    path('schedule-updates/', views.schedule_climate_updates, name='schedule-climate-updates'),
]
