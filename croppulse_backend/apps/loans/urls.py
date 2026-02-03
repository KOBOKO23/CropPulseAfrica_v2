"""
Loans App URLs
"""

from django.urls import path
from apps.loans import views

app_name = 'loans'

urlpatterns = [
    # Loan Applications
    path('', views.LoanApplicationListView.as_view(), name='loan-list'),
    path('<int:loan_id>/', views.LoanApplicationDetailView.as_view(), name='loan-detail'),
    path('<int:loan_id>/approve/', views.LoanApproveView.as_view(), name='loan-approve'),
    path('<int:loan_id>/disburse/', views.LoanDisbursementView.as_view(), name='loan-disburse'),
    
    # Repayments
    path('<int:loan_id>/repayments/', views.LoanRepaymentListView.as_view(), name='loan-repayments'),
    path('<int:loan_id>/schedule/', views.RepaymentScheduleView.as_view(), name='repayment-schedule'),
    path('<int:loan_id>/audit/', views.LoanAuditLogListView.as_view(), name='loan-audit-log'),
    
    # M-Pesa Callback
    path('mpesa-callback/', views.LoanMpesaCallbackView.as_view(), name='mpesa-callback'),
    
    # Utilities
    path('emi-calculator/', views.EMICalculatorView.as_view(), name='emi-calculator'),
    
    # Interest Rate Policies
    path('rate-policy/', views.InterestRatePolicyListView.as_view(), name='rate-policy-list'),
    path('rate-policy/<int:policy_id>/', views.InterestRatePolicyDetailView.as_view(), name='rate-policy-detail'),
    
    # Climate Adjustments
    path('climate-adjustments/', views.ClimateRateAdjustmentListView.as_view(), name='climate-adjustments'),
    path('climate-adjustments/<int:adjustment_id>/review/', views.ClimateRateAdjustmentReviewView.as_view(), name='climate-adjustment-review'),
    
    # Restructuring
    path('restructures/', views.LoanRestructureListView.as_view(), name='restructure-list'),
    path('restructures/<int:restructure_id>/review/', views.LoanRestructureReviewView.as_view(), name='restructure-review'),
]