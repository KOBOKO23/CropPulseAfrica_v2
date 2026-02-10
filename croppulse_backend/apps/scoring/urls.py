"""
Scoring App URLs
"""

from django.urls import path
from apps.scoring import views
from .views_reports import download_credit_report

app_name = 'scoring'

urlpatterns = [
    # Score Calculation
    path('calculate/', views.CalculateScoreView.as_view(), name='calculate-score'),
    
    # Score Retrieval
    path('farmer/<int:farmer_id>/', views.FarmerScoreView.as_view(), name='farmer-score'),
    path('farmer/<int:farmer_id>/history/', views.ScoreHistoryView.as_view(), name='score-history'),
    
    # Fraud Alerts
    path('farmer/<int:farmer_id>/fraud-alerts/', views.FraudAlertsView.as_view(), name='fraud-alerts'),
    
    # NEW: Credit Report
    path('farmer/<int:farmer_id>/credit-report/', download_credit_report, name='credit-report'),
]