"""
Loans Services Package

Export all loan services for easy importing.
"""

from apps.loans.services.loan_calculator import LoanCalculator
from apps.loans.services.approval_engine import ApprovalEngine
from apps.loans.services.repayment_scheduler import RepaymentScheduler
from apps.loans.services.restructure_service import RestructureService
from apps.loans.services.mpesa_integration import MpesaIntegration

# Also export climate_rate_adjuster if it exists in project
try:
    from apps.loans.services.climate_rate_adjuster import ClimateRateAdjuster
except ImportError:
    ClimateRateAdjuster = None

__all__ = [
    'LoanCalculator',
    'ApprovalEngine',
    'RepaymentScheduler',
    'RestructureService',
    'MpesaIntegration',
    'ClimateRateAdjuster',
]