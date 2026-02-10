# apps/farms/urls.py

from django.urls import path
from .views import (
    FarmCreateView,
    FarmListView,
    FarmDetailView,
    FarmUpdateView,
    FarmBoundaryPointsView,
    FarmerFarmsView,
    NearbyFarmsView,
    FarmsInAreaView,
    farm_geojson,
    trigger_farm_scan,
    farm_statistics,
    delete_farm,
    set_primary_farm,
    validate_boundary,  # NEW
    check_overlap,  # NEW
    simplify_boundary,  # NEW
    get_boundary_analysis,  # NEW
    upload_gps_boundary,  # MOBILE
    get_verification_status,  # MOBILE
)

app_name = 'farms'

urlpatterns = [
    # Farm CRUD
    path('create/', FarmCreateView.as_view(), name='farm_create'),
    path('', FarmListView.as_view(), name='farm_list'),
    path('<str:farm_id>/', FarmDetailView.as_view(), name='farm_detail'),
    path('<str:farm_id>/update/', FarmUpdateView.as_view(), name='farm_update'),
    path('<str:farm_id>/delete/', delete_farm, name='farm_delete'),
    
    # Farm Actions
    path('<str:farm_id>/scan/', trigger_farm_scan, name='trigger_scan'),
    path('<str:farm_id>/set-primary/', set_primary_farm, name='set_primary'),
    path('<str:farm_id>/geojson/', farm_geojson, name='farm_geojson'),
    
    # Boundary Operations (NEW)
    path('validate-boundary/', validate_boundary, name='validate_boundary'),
    path('<str:farm_id>/check-overlap/', check_overlap, name='check_overlap'),
    path('<str:farm_id>/simplify/', simplify_boundary, name='simplify_boundary'),
    path('<str:farm_id>/boundary-analysis/', get_boundary_analysis, name='boundary_analysis'),
    
    # Boundary Points
    path('<str:farm_id>/boundary-points/', FarmBoundaryPointsView.as_view(), name='boundary_points'),
    
    # Farmer Farms
    path('farmer/<str:pulse_id>/', FarmerFarmsView.as_view(), name='farmer_farms'),
    
    # Spatial Queries
    path('<str:farm_id>/nearby/', NearbyFarmsView.as_view(), name='nearby_farms'),
    path('in-area/', FarmsInAreaView.as_view(), name='farms_in_area'),
    
    # Statistics
    path('statistics/', farm_statistics, name='farm_statistics'),
    
    # Mobile GPS Integration
    path('gps-boundary/upload/', upload_gps_boundary, name='upload_gps_boundary'),
    path('<str:farm_id>/verification-status/', get_verification_status, name='verification_status'),
]

# Logistics and Insurance (NEW)
from .views_logistics import (
    verify_insurance_claim,
    analyze_harvest_timing,
    estimate_harvest_loss,
)

urlpatterns += [
    path('insurance/verify-claim/', verify_insurance_claim, name='verify-insurance-claim'),
    path('<int:farm_id>/harvest-timing/', analyze_harvest_timing, name='harvest-timing'),
    path('<int:farm_id>/harvest-loss/', estimate_harvest_loss, name='harvest-loss'),
]
