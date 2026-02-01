# apps/satellite/urls.py

from django.urls import path
from .views import (
    TriggerSatelliteScanView,
    SatelliteScanListView,
    SatelliteScanDetailView,
    FarmLatestScanView,
    NDVIHistoryListView,
    NDVITrendView,
    FarmHealthSummaryView,
    BulkScanTriggerView,
    satellite_statistics,
    rescan_farm
)

app_name = 'satellite'

urlpatterns = [
    # Satellite Scans
    path('scan/trigger/', TriggerSatelliteScanView.as_view(), name='trigger_scan'),
    path('scan/bulk-trigger/', BulkScanTriggerView.as_view(), name='bulk_trigger_scan'),
    path('scans/', SatelliteScanListView.as_view(), name='scan_list'),
    path('scans/<str:scan_id>/', SatelliteScanDetailView.as_view(), name='scan_detail'),
    
    # Farm-specific Scans
    path('farms/<str:farm_id>/latest-scan/', FarmLatestScanView.as_view(), name='farm_latest_scan'),
    path('farms/<str:farm_id>/rescan/', rescan_farm, name='rescan_farm'),
    path('farms/<str:farm_id>/health-summary/', FarmHealthSummaryView.as_view(), name='farm_health_summary'),
    
    # NDVI History & Trends
    path('ndvi-history/', NDVIHistoryListView.as_view(), name='ndvi_history'),
    path('ndvi-trend/<str:farm_id>/', NDVITrendView.as_view(), name='ndvi_trend'),
    
    # Statistics
    path('statistics/', satellite_statistics, name='statistics'),
]