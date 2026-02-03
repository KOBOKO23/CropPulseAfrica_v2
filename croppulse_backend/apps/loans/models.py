"""
Loans App Models - Climate-Protected Agricultural Lending

Key Features:
- Interest rate capping per bank and platform-wide
- Climate-triggered automatic interest rate resets
- Loan restructuring for climate events
- Comprehensive audit trail
- M-Pesa integration for disbursement and repayments
"""

from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from apps.farmers.models import Farmer
from apps.banks.models import Bank

User = get_user_model()

# Platform-wide constants
PLATFORM_MAX_INTEREST_RATE = 36.0  # 36% per annum maximum
PLATFORM_MIN_INTEREST_RATE = 2.0   # 2% per annum minimum
MINIMUM_PULSE_SCORE = 300          # Auto-reject below this score


class LoanApplication(models.Model):
    """
    Core loan application entity.
    
    Workflow:
    1. Farmer applies (status=pending)
    2. Bank reviews and approves/rejects (status=approved/rejected)
    3. Upon approval, interest_rate is set based on pulse_score
    4. Bank disburses via M-Pesa (status=disbursed)
    5. Repayments tracked via LoanRepayment model
    6. Climate events can trigger rate resets and restructuring
    """
    
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('disbursed', 'Disbursed'),
        ('repaid', 'Fully Repaid'),
        ('defaulted', 'Defaulted'),
    )
    
    # Identifiers
    application_id = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Unique loan identifier (e.g., LN-2026-001234)"
    )
    farmer = models.ForeignKey(
        Farmer, 
        on_delete=models.CASCADE, 
        related_name='loan_applications'
    )
    bank = models.ForeignKey(
        Bank, 
        on_delete=models.CASCADE, 
        related_name='loan_applications'
    )
    
    # Loan Details
    requested_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1000.00'))]
    )
    approved_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="May differ from requested amount based on assessment"
    )
    interest_rate = models.FloatField(
        validators=[
            MinValueValidator(PLATFORM_MIN_INTEREST_RATE),
            MaxValueValidator(PLATFORM_MAX_INTEREST_RATE)
        ],
        help_text="Annual interest rate (%)"
    )
    interest_rate_cap = models.FloatField(
        null=True,
        blank=True,
        help_text="Maximum rate this loan can be charged (from bank policy at approval)"
    )
    repayment_period_months = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text="Loan tenor in months (max 5 years)"
    )
    loan_purpose = models.CharField(
        max_length=100,
        help_text="e.g., 'Seed purchase', 'Fertilizer', 'Equipment'"
    )
    
    # Pulse Score at Application
    pulse_score_at_application = models.IntegerField(
        help_text="Farmer's credit score when they applied"
    )
    
    # Climate Protection
    climate_protected = models.BooleanField(
        default=False,
        help_text="True if this loan has received climate-triggered rate reduction"
    )
    climate_risk_at_application = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=(
            ('low', 'Low Risk'),
            ('moderate', 'Moderate Risk'),
            ('high', 'High Risk'),
            ('critical', 'Critical Risk'),
        ),
        help_text="Climate risk level when loan was approved"
    )
    
    # Status Tracking
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    reviewed_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When bank made approval/rejection decision"
    )
    disbursed_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When funds were sent to farmer via M-Pesa"
    )
    
    # Verification & Performance
    satellite_verification_id = models.CharField(
        max_length=100, 
        null=True, 
        blank=True,
        help_text="Link to satellite scan that verified the farm"
    )
    api_response_time_ms = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Time taken for loan assessment"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'loan_applications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['farmer', '-created_at']),
            models.Index(fields=['bank', 'status']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['bank', 'climate_protected']),
        ]
    
    def __str__(self):
        return f"{self.application_id} - {self.farmer.full_name} - {self.get_status_display()}"
    
    @property
    def is_active(self):
        """Check if loan is currently active (disbursed but not closed)"""
        return self.status == 'disbursed'
    
    @property
    def total_repaid(self):
        """Calculate total amount repaid so far"""
        return self.repayments.aggregate(
            total=models.Sum('amount_paid')
        )['total'] or Decimal('0.00')
    
    @property
    def outstanding_balance(self):
        """Calculate remaining balance"""
        if not self.approved_amount:
            return Decimal('0.00')
        
        # Get the current repayment schedule
        current_schedule = self.repayment_schedules.filter(is_current=True).first()
        if not current_schedule:
            return Decimal('0.00')
        
        total_due = current_schedule.total_repayment
        return total_due - self.total_repaid


class LoanRepayment(models.Model):
    """
    Individual loan repayment instalments.
    
    Generated automatically when loan is disbursed based on the
    repayment schedule (amortisation table).
    
    Updated via M-Pesa callbacks when farmer makes payments.
    """
    
    loan = models.ForeignKey(
        LoanApplication, 
        on_delete=models.CASCADE, 
        related_name='repayments'
    )
    payment_number = models.IntegerField(
        help_text="Instalment number (1, 2, 3...)"
    )
    due_date = models.DateField()
    amount_due = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Expected payment amount (EMI)"
    )
    amount_paid = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    paid_date = models.DateField(
        null=True, 
        blank=True,
        help_text="When payment was received"
    )
    is_paid = models.BooleanField(default=False)
    is_late = models.BooleanField(
        default=False,
        help_text="True if payment made after due_date"
    )
    days_late = models.IntegerField(
        default=0,
        help_text="Number of days overdue"
    )
    
    # M-Pesa Integration
    mpesa_transaction_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="M-Pesa confirmation code"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'loan_repayments'
        ordering = ['loan', 'payment_number']
        unique_together = ['loan', 'payment_number']
        indexes = [
            models.Index(fields=['loan', 'is_paid']),
            models.Index(fields=['due_date', 'is_paid']),
        ]
    
    def __str__(self):
        return f"{self.loan.application_id} - Payment {self.payment_number}"


class RepaymentSchedule(models.Model):
    """
    Amortisation schedule summary for a loan.
    
    Contains the high-level repayment plan:
    - Total instalments
    - Monthly EMI
    - Total interest
    - Total repayment amount
    
    One schedule per loan, but can be superseded if loan is restructured
    (in which case is_current=False and a new schedule is created).
    """
    
    loan = models.ForeignKey(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name='repayment_schedules'
    )
    total_instalments = models.IntegerField(
        help_text="Number of monthly payments"
    )
    monthly_payment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Fixed EMI amount (Equated Monthly Instalment)"
    )
    total_interest = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Total interest to be paid over loan life"
    )
    total_repayment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Principal + Interest"
    )
    start_date = models.DateField(
        help_text="Date of first payment"
    )
    end_date = models.DateField(
        help_text="Date of final payment"
    )
    interest_rate_used = models.FloatField(
        help_text="Interest rate (%) used to generate this schedule"
    )
    is_current = models.BooleanField(
        default=True,
        help_text="False if loan has been restructured"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'repayment_schedules'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['loan', 'is_current']),
        ]
    
    def __str__(self):
        status = "Current" if self.is_current else "Superseded"
        return f"{self.loan.application_id} - {status} Schedule"


class InterestRatePolicy(models.Model):
    """
    Per-bank interest rate policy.
    
    Defines:
    - Maximum interest rate the bank can charge
    - Minimum interest rate (typically for best customers)
    - Climate reset threshold (what severity triggers auto-reset)
    - Climate floor rate (rate to reset to during climate events)
    - Whether auto-reset is enabled
    
    Example:
    - Bank A: max_rate=24%, climate_reset_threshold='high', 
              climate_floor_rate=5%, auto_reset_enabled=True
    - When 'high' severity climate event occurs, all Bank A's active loans
      automatically reset to 5%
    """
    
    CLIMATE_SEVERITY_CHOICES = (
        ('low', 'Low'),
        ('moderate', 'Moderate'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )
    
    bank = models.ForeignKey(
        Bank,
        on_delete=models.CASCADE,
        related_name='interest_rate_policies'
    )
    
    # Rate Bounds
    max_rate = models.FloatField(
        validators=[
            MinValueValidator(PLATFORM_MIN_INTEREST_RATE),
            MaxValueValidator(PLATFORM_MAX_INTEREST_RATE)
        ],
        help_text=f"Maximum rate (cannot exceed platform cap of {PLATFORM_MAX_INTEREST_RATE}%)"
    )
    min_rate = models.FloatField(
        validators=[
            MinValueValidator(PLATFORM_MIN_INTEREST_RATE),
            MaxValueValidator(PLATFORM_MAX_INTEREST_RATE)
        ],
        help_text="Minimum rate for best-credit customers"
    )
    
    # Climate Protection Settings
    climate_reset_threshold = models.CharField(
        max_length=20,
        choices=CLIMATE_SEVERITY_CHOICES,
        default='high',
        help_text="Climate severity level that triggers rate reset"
    )
    climate_floor_rate = models.FloatField(
        validators=[
            MinValueValidator(PLATFORM_MIN_INTEREST_RATE),
            MaxValueValidator(PLATFORM_MAX_INTEREST_RATE)
        ],
        help_text="Rate to reset to during climate events"
    )
    auto_reset_enabled = models.BooleanField(
        default=True,
        help_text="If True, rate resets happen automatically. If False, requires bank approval."
    )
    
    # Metadata
    is_active = models.BooleanField(
        default=True,
        help_text="Only one policy per bank should be active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'interest_rate_policies'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['bank', 'is_active']),
        ]
        verbose_name_plural = 'Interest Rate Policies'
    
    def __str__(self):
        return f"{self.bank.name} Policy - {self.min_rate}% to {self.max_rate}%"
    
    def clean(self):
        """Validate that min_rate <= climate_floor_rate <= max_rate"""
        from django.core.exceptions import ValidationError
        
        if self.min_rate > self.climate_floor_rate:
            raise ValidationError({
                'climate_floor_rate': f'Climate floor rate must be >= min_rate ({self.min_rate}%)'
            })
        
        if self.climate_floor_rate > self.max_rate:
            raise ValidationError({
                'climate_floor_rate': f'Climate floor rate must be <= max_rate ({self.max_rate}%)'
            })


class ClimateRateAdjustment(models.Model):
    """
    Log of climate-triggered interest rate adjustments.
    
    Created when:
    1. Climate app detects a severe weather event
    2. Event severity meets or exceeds bank's climate_reset_threshold
    3. System creates ClimateRateAdjustment records for affected loans
    
    Status flow:
    - 'pending': Awaiting bank review (if auto_reset_enabled=False)
    - 'applied': Rate reduction has been applied
    - 'rejected': Bank declined to apply reduction
    - 'cancelled': Event was false alarm or retracted
    """
    
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('applied', 'Applied'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    )
    
    loan = models.ForeignKey(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name='climate_adjustments'
    )
    bank = models.ForeignKey(
        Bank,
        on_delete=models.CASCADE,
        related_name='climate_adjustments'
    )
    
    # Climate Event Details
    climate_event_id = models.CharField(
        max_length=100,
        help_text="Reference to ClimateAlert in climate app"
    )
    climate_severity = models.CharField(
        max_length=20,
        help_text="e.g., 'high', 'critical'"
    )
    climate_region = models.CharField(
        max_length=100,
        help_text="Geographic region affected"
    )
    
    # Rate Change
    old_rate = models.FloatField(
        help_text="Interest rate before adjustment"
    )
    new_rate = models.FloatField(
        help_text="Proposed/applied interest rate"
    )
    reason = models.TextField(
        help_text="Explanation of climate event and impact"
    )
    
    # Status & Review
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_climate_adjustments'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When rate change took effect"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'climate_rate_adjustments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['loan', '-created_at']),
            models.Index(fields=['bank', 'status']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['climate_event_id']),
        ]
    
    def __str__(self):
        return f"{self.loan.application_id} - {self.old_rate}% → {self.new_rate}% ({self.status})"


class LoanRestructure(models.Model):
    """
    Full loan restructuring (beyond simple rate adjustment).
    
    Used when:
    - Climate events require both rate AND tenor changes
    - Farmer requests payment holiday
    - Loan is at risk of default and needs rescheduling
    
    Captures:
    - Old loan terms (rate, tenor, monthly payment)
    - New loan terms
    - Outstanding balance at time of restructure
    - Reason for restructure
    
    Workflow:
    1. System or bank initiates restructure (status=pending)
    2. Bank approves/rejects (status=approved/rejected)
    3. Upon approval, RepaymentScheduler regenerates schedule (status=completed)
    """
    
    REASON_CHOICES = (
        ('climate_event', 'Climate Event'),
        ('default_risk', 'Default Risk Mitigation'),
        ('farmer_request', 'Farmer Hardship Request'),
        ('admin_decision', 'Administrative Decision'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    )
    
    loan = models.ForeignKey(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name='restructures'
    )
    bank = models.ForeignKey(
        Bank,
        on_delete=models.CASCADE,
        related_name='loan_restructures'
    )
    
    # Reason
    reason = models.CharField(
        max_length=50,
        choices=REASON_CHOICES
    )
    climate_adjustment = models.ForeignKey(
        ClimateRateAdjustment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="If restructure was triggered by climate event"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional context"
    )
    
    # Old Terms (snapshot)
    old_interest_rate = models.FloatField()
    old_repayment_period_months = models.IntegerField()
    old_monthly_payment = models.DecimalField(max_digits=12, decimal_places=2)
    old_outstanding_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="How much was owed at restructure time"
    )
    
    # New Terms
    new_interest_rate = models.FloatField()
    new_repayment_period_months = models.IntegerField()
    new_monthly_payment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Calculated once restructure is completed"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_restructures'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When new schedule was generated"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'loan_restructures'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['loan', '-created_at']),
            models.Index(fields=['bank', 'status']),
            models.Index(fields=['reason', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.loan.application_id} Restructure - {self.get_reason_display()}"


class LoanAuditLog(models.Model):
    """
    Comprehensive audit trail for all loan operations.
    
    Records:
    - Status changes
    - Rate adjustments
    - Disbursements
    - Repayments
    - Restructures
    - Manual overrides
    
    This is an append-only table (never updated or deleted).
    """
    
    ACTION_CHOICES = (
        ('status_change', 'Status Change'),
        ('rate_change', 'Interest Rate Change'),
        ('disbursement', 'Loan Disbursed'),
        ('repayment', 'Payment Received'),
        ('restructure', 'Loan Restructured'),
        ('climate_adjustment', 'Climate Rate Adjustment'),
    )
    
    loan = models.ForeignKey(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    old_value = models.JSONField(
        null=True,
        blank=True,
        help_text="Previous state (JSON)"
    )
    new_value = models.JSONField(
        null=True,
        blank=True,
        help_text="New state (JSON)"
    )
    details = models.TextField(
        blank=True,
        help_text="Human-readable description"
    )
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    triggered_by_system = models.BooleanField(
        default=False,
        help_text="True if automated, False if manual"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'loan_audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['loan', '-created_at']),
            models.Index(fields=['action', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.loan.application_id} - {self.get_action_display()}"