# loans/models.py

from django.db import models
from apps.farmers.models import Farmer
from apps.banks.models import Bank

class LoanApplication(models.Model):
    """Loan application from farmer"""
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('disbursed', 'Disbursed'),
        ('repaid', 'Fully Repaid'),
        ('defaulted', 'Defaulted'),
    )
    
    application_id = models.CharField(max_length=50, unique=True)
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name='loan_applications')
    bank = models.ForeignKey('banks.Bank', on_delete=models.CASCADE, related_name='loan_applications')
    
    # Loan Details
    requested_amount = models.DecimalField(max_digits=12, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    interest_rate = models.FloatField()
    repayment_period_months = models.IntegerField()
    loan_purpose = models.CharField(max_length=100)
    
    # Pulse Score at Application
    pulse_score_at_application = models.IntegerField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)
    
    # Verification
    satellite_verification_id = models.CharField(max_length=100, null=True, blank=True)
    api_response_time_ms = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'loan_applications'
        indexes = [
            models.Index(fields=['farmer', '-created_at']),
            models.Index(fields=['bank', 'status']),
        ]


class LoanRepayment(models.Model):
    """Loan repayment tracking"""
    loan = models.ForeignKey(LoanApplication, on_delete=models.CASCADE, related_name='repayments')
    
    payment_number = models.IntegerField()
    due_date = models.DateField()
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_date = models.DateField(null=True, blank=True)
    
    is_paid = models.BooleanField(default=False)
    is_late = models.BooleanField(default=False)
    days_late = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'loan_repayments'
        unique_together = ['loan', 'payment_number']