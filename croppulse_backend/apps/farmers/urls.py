# apps/farmers/urls.py

from django.urls import path
from .views import (
    FarmerCreateView,
    FarmerListView,
    FarmerDetailView,
    FarmerUpdateView,
    MyFarmerProfileView,
    VoiceRegistrationCreateView,
    VoiceRegistrationListView,
    FarmerOnboardingStatusView,
    FarmerNoteCreateView,
    FarmerNoteListView,
    complete_onboarding,
    farmer_statistics,
    search_farmers,
    deactivate_farmer,
    verify_pulse_id,
    flag_farmer_for_fraud,
    clear_farmer_fraud_flag,
    get_farmer_stats_detailed
)

app_name = 'farmers'

urlpatterns = [
    # Farmer Profile Management
    path('register/', FarmerCreateView.as_view(), name='farmer_register'),
    path('', FarmerListView.as_view(), name='farmer_list'),
    path('me/', MyFarmerProfileView.as_view(), name='my_profile'),
    path('<str:pulse_id>/', FarmerDetailView.as_view(), name='farmer_detail'),
    path('<str:pulse_id>/update/', FarmerUpdateView.as_view(), name='farmer_update'),
    path('<str:pulse_id>/deactivate/', deactivate_farmer, name='farmer_deactivate'),
    path('<str:pulse_id>/stats/', get_farmer_stats_detailed, name='farmer_stats_detailed'),
    
    # Voice Registration
    path('voice-registration/', VoiceRegistrationCreateView.as_view(), name='voice_registration_create'),
    path('<str:pulse_id>/voice-recordings/', VoiceRegistrationListView.as_view(), name='voice_recordings'),
    
    # Onboarding
    path('<str:pulse_id>/onboarding-status/', FarmerOnboardingStatusView.as_view(), name='onboarding_status'),
    path('<str:pulse_id>/complete-onboarding/', complete_onboarding, name='complete_onboarding'),
    
    # Farmer Notes
    path('<str:pulse_id>/notes/', FarmerNoteListView.as_view(), name='farmer_notes'),
    path('<str:pulse_id>/notes/create/', FarmerNoteCreateView.as_view(), name='farmer_note_create'),
    
    # Fraud Management
    path('<str:pulse_id>/flag-fraud/', flag_farmer_for_fraud, name='flag_fraud'),
    path('<str:pulse_id>/clear-fraud/', clear_farmer_fraud_flag, name='clear_fraud'),
    
    # Search & Verification
    path('search/', search_farmers, name='search_farmers'),
    path('verify-pulse-id/<str:pulse_id>/', verify_pulse_id, name='verify_pulse_id'),
    
    # Statistics (Admin)
    path('statistics/', farmer_statistics, name='farmer_statistics'),
]

# Verification Features (NEW)
from .views_verification import (
    GroundTruthReportListCreateView,
    ProofOfActionListCreateView,
    verify_ground_truth,
    verify_proof_of_action,
    send_sms_alert,
)

# Add to urlpatterns
urlpatterns += [
    path('ground-truth/', GroundTruthReportListCreateView.as_view(), name='ground-truth-list'),
    path('ground-truth/<int:pk>/verify/', verify_ground_truth, name='ground-truth-verify'),
    path('proof-of-action/', ProofOfActionListCreateView.as_view(), name='proof-of-action-list'),
    path('proof-of-action/<int:pk>/verify/', verify_proof_of_action, name='proof-of-action-verify'),
    path('sms/send/', send_sms_alert, name='send-sms-alert'),
]
