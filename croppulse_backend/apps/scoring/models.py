"""
Scoring App Models

Core credit scoring system that calculates Pulse Scores for farmers based on:
- Farm size
- Crop health (NDVI from satellite)
- Climate risk
- Deforestation status
- Payment history
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
from apps.farmers.models import Farmer
from apps.farms.models import Farm


class PulseScore(models.Model):
    """
    The core credit score for a farmer.
    
    Score calculation combines multiple factors with weighted importance:
    - Farm size: 20%
    - Crop health: 25%
    - Climate risk: 20%
    - Deforestation: 17%
    - Payment history: 18%
    
    Score range: 0-1000 (higher is better)
    Confidence: 0.0-1.0 (how reliable the score is)
    """
    
    # Relationships
    farmer = models.ForeignKey(
        Farmer,
        on_delete=models.CASCADE,
        related_name='pulse_scores'
    )
    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        related_name='pulse_scores'
    )
    
    # Core Score
    score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(1000)],
        help_text="Credit score from 0-1000"
    )
    confidence_level = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence in score accuracy (0.0-1.0)"
    )
    
    # Score Breakdown (each component 0-100)
    farm_size_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    crop_health_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    climate_risk_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    deforestation_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    payment_history_score = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="50 = neutral for new farmers"
    )
    
    # Credit Implications
    max_loan_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Maximum recommended loan amount based on score"
    )
    recommended_interest_rate_min = models.FloatField(
        help_text="Minimum recommended interest rate (%)"
    )
    recommended_interest_rate_max = models.FloatField(
        help_text="Maximum recommended interest rate (%)"
    )
    default_probability = models.FloatField(
        help_text="Estimated default probability (0-100%)"
    )
    
    # Metadata
    calculation_method = models.CharField(
        max_length=50,
        default='v1.0',
        help_text="Version of scoring algorithm used"
    )
    factors_used = models.JSONField(
        help_text="List of data points used in calculation"
    )
    
    # Data Freshness
    satellite_data_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of satellite data used"
    )
    climate_data_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of climate data used"
    )
    
    # Validity Period
    valid_from = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField(
        help_text="Score expires after this date"
    )
    is_current = models.BooleanField(
        default=True,
        help_text="True if this is the active score for the farmer"
    )
    
    # Frozen Status
    is_frozen = models.BooleanField(
        default=False,
        help_text="True if score is frozen due to pending loan application"
    )
    frozen_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When score was frozen"
    )
    frozen_by_loan = models.ForeignKey(
        'loans.LoanApplication',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='frozen_scores'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pulse_scores'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['farmer', '-created_at']),
            models.Index(fields=['farm', '-created_at']),
            models.Index(fields=['is_current']),
            models.Index(fields=['is_frozen']),
            models.Index(fields=['score', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.farmer.full_name} - Score: {self.score} (Valid until {self.valid_until.date()})"
    
    @property
    def is_valid(self):
        """Check if score is still valid"""
        return timezone.now() <= self.valid_until and self.is_current
    
    @property
    def days_until_expiry(self):
        """Calculate days remaining until score expires"""
        if not self.is_valid:
            return 0
        return (self.valid_until - timezone.now()).days
    
    @property
    def grade(self):
        """Convert score to letter grade"""
        if self.score >= 850:
            return 'A+'
        elif self.score >= 800:
            return 'A'
        elif self.score >= 750:
            return 'A-'
        elif self.score >= 700:
            return 'B+'
        elif self.score >= 650:
            return 'B'
        elif self.score >= 600:
            return 'B-'
        elif self.score >= 550:
            return 'C+'
        elif self.score >= 500:
            return 'C'
        elif self.score >= 450:
            return 'C-'
        elif self.score >= 400:
            return 'D'
        else:
            return 'F'
    
    @property
    def risk_category(self):
        """Categorize risk level based on score"""
        if self.score >= 750:
            return 'low'
        elif self.score >= 600:
            return 'moderate'
        elif self.score >= 450:
            return 'high'
        else:
            return 'very_high'
    
    def freeze(self, loan_application):
        """
        Freeze score for loan application.
        
        Prevents recalculation while loan is being processed.
        """
        self.is_frozen = True
        self.frozen_at = timezone.now()
        self.frozen_by_loan = loan_application
        self.save()
    
    def unfreeze(self):
        """Unfreeze score after loan is processed"""
        self.is_frozen = False
        self.frozen_at = None
        self.frozen_by_loan = None
        self.save()


class ScoreHistory(models.Model):
    """
    Track score changes over time for trend analysis.
    
    One record per day per farmer showing their score on that date.
    Used for:
    - Score trend graphs
    - Improvement tracking
    - Historical loan assessment
    """
    
    farmer = models.ForeignKey(
        Farmer,
        on_delete=models.CASCADE,
        related_name='score_history'
    )
    date = models.DateField()
    score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(1000)]
    )
    change_from_previous = models.IntegerField(
        help_text="Score delta from previous day (can be negative)"
    )
    
    # Snapshot of key factors
    farm_size_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    crop_health_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    climate_risk_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    payment_history_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'score_history'
        ordering = ['-date']
        unique_together = ['farmer', 'date']
        indexes = [
            models.Index(fields=['farmer', '-date']),
        ]
    
    def __str__(self):
        arrow = '↑' if self.change_from_previous > 0 else '↓' if self.change_from_previous < 0 else '→'
        return f"{self.farmer.full_name} - {self.date}: {self.score} ({arrow}{abs(self.change_from_previous)})"


class ScoreRecalculationLog(models.Model):
    """
    Log every score recalculation for audit and debugging.
    
    Tracks:
    - When score was recalculated
    - Why it was recalculated
    - What changed
    - Any errors encountered
    """
    
    TRIGGER_CHOICES = (
        ('scheduled', 'Scheduled Recalculation'),
        ('new_satellite', 'New Satellite Data'),
        ('new_payment', 'New Payment Received'),
        ('manual', 'Manual Trigger'),
        ('loan_application', 'Loan Application Submitted'),
        ('system', 'System-Initiated'),
    )
    
    farmer = models.ForeignKey(
        Farmer,
        on_delete=models.CASCADE,
        related_name='score_recalculation_logs'
    )
    trigger = models.CharField(max_length=50, choices=TRIGGER_CHOICES)
    
    # Before/After
    old_score = models.IntegerField(null=True, blank=True)
    new_score = models.IntegerField()
    score_change = models.IntegerField(
        help_text="new_score - old_score"
    )
    
    # Calculation Details
    calculation_method = models.CharField(max_length=50)
    factors_changed = models.JSONField(
        help_text="List of factors that changed since last calculation"
    )
    
    # Performance
    calculation_time_ms = models.IntegerField(
        help_text="Time taken to calculate score (milliseconds)"
    )
    
    # Status
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'score_recalculation_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['farmer', '-created_at']),
            models.Index(fields=['trigger', '-created_at']),
            models.Index(fields=['success']),
        ]
    
    def __str__(self):
        status = '✓' if self.success else '✗'
        return f"{status} {self.farmer.full_name} - {self.trigger} - {self.created_at.date()}"


class ScoreOverride(models.Model):
    """
    Manual score overrides for exceptional cases.
    
    Allows administrators to manually adjust scores when:
    - Automated scoring fails
    - Special circumstances apply
    - Temporary adjustments needed
    
    All overrides are logged for compliance.
    """
    
    REASON_CHOICES = (
        ('data_error', 'Data Quality Issue'),
        ('special_case', 'Special Circumstances'),
        ('fraud_detected', 'Fraud Detected'),
        ('manual_review', 'Manual Credit Review'),
        ('system_error', 'System Error'),
        ('appeal_approved', 'Farmer Appeal Approved'),
    )
    
    farmer = models.ForeignKey(
        Farmer,
        on_delete=models.CASCADE,
        related_name='score_overrides'
    )
    original_score = models.IntegerField()
    override_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(1000)]
    )
    
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    notes = models.TextField(
        help_text="Detailed explanation for override"
    )
    
    # Approval
    requested_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='requested_score_overrides'
    )
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_score_overrides'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Validity
    is_active = models.BooleanField(default=True)
    valid_until = models.DateTimeField(
        help_text="Override expires after this date"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'score_overrides'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['farmer', 'is_active']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.farmer.full_name} - Override: {self.original_score} → {self.override_score}"
    
    @property
    def is_valid(self):
        """Check if override is still active and not expired"""
        return self.is_active and timezone.now() <= self.valid_until


class FraudAlert(models.Model):
    """
    Fraud detection alerts that may affect credit scores.
    
    Generated by fraud detection algorithms when suspicious patterns detected.
    """
    
    SEVERITY_CHOICES = (
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical Risk'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('investigating', 'Under Investigation'),
        ('confirmed', 'Confirmed Fraud'),
        ('false_positive', 'False Positive'),
        ('resolved', 'Resolved'),
    )
    
    farmer = models.ForeignKey(
        Farmer,
        on_delete=models.CASCADE,
        related_name='fraud_alerts'
    )
    farm = models.ForeignKey(
        Farm,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='fraud_alerts'
    )
    
    alert_type = models.CharField(
        max_length=50,
        help_text="e.g., 'ghost_farm', 'duplicate_farm', 'ndvi_mismatch'"
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='medium'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    description = models.TextField(
        help_text="Details of the fraud pattern detected"
    )
    evidence = models.JSONField(
        help_text="Supporting data/metrics for the alert"
    )
    
    # Impact
    score_impact = models.IntegerField(
        default=0,
        help_text="How much this alert reduces the credit score"
    )
    blocks_lending = models.BooleanField(
        default=False,
        help_text="If true, farmer cannot get loans until resolved"
    )
    
    # Resolution
    reviewed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_fraud_alerts'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'fraud_alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['farmer', 'status']),
            models.Index(fields=['severity', 'status']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_severity_display()} - {self.farmer.full_name} - {self.alert_type}"