"""
Loans App Serializers
"""

from rest_framework import serializers
from apps.loans.models import (
    LoanApplication,
    LoanRepayment,
    RepaymentSchedule,
    InterestRatePolicy,
    ClimateRateAdjustment,
    LoanRestructure,
    LoanAuditLog
)
from apps.farmers.serializers import FarmerSerializer
from apps.banks.serializers import BankSerializer


class LoanApplicationSerializer(serializers.ModelSerializer):
    """Read serializer with nested relations"""
    farmer_details = FarmerSerializer(source='farmer', read_only=True)
    bank_details = BankSerializer(source='bank', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    total_repaid = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    outstanding_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    
    class Meta:
        model = LoanApplication
        fields = '__all__'
        read_only_fields = [
            'application_id', 'status', 'reviewed_at', 'disbursed_at',
            'approved_amount', 'interest_rate', 'interest_rate_cap',
            'climate_protected', 'climate_risk_at_application'
        ]


class LoanApplicationWriteSerializer(serializers.ModelSerializer):
    """Write serializer for creating loans"""
    
    class Meta:
        model = LoanApplication
        fields = [
            'farmer', 'bank', 'requested_amount', 'repayment_period_months',
            'loan_purpose', 'pulse_score_at_application', 'satellite_verification_id'
        ]
    
    def create(self, validated_data):
        # Generate application_id
        import uuid
        from datetime import datetime
        
        year = datetime.now().year
        unique_part = str(uuid.uuid4())[:8].upper()
        application_id = f"LN-{year}-{unique_part}"
        
        validated_data['application_id'] = application_id
        
        # Set default interest rate (will be overridden on approval)
        validated_data['interest_rate'] = 12.0
        
        return super().create(validated_data)


class LoanRepaymentSerializer(serializers.ModelSerializer):
    """Loan repayment instalment"""
    status_badge = serializers.SerializerMethodField()
    
    class Meta:
        model = LoanRepayment
        fields = '__all__'
        read_only_fields = [
            'loan', 'payment_number', 'due_date', 'amount_due',
            'amount_paid', 'paid_date', 'is_paid', 'is_late',
            'days_late', 'mpesa_transaction_id'
        ]
    
    def get_status_badge(self, obj):
        if obj.is_paid:
            return 'paid'
        elif obj.is_late:
            return 'overdue'
        else:
            return 'pending'


class RepaymentScheduleSerializer(serializers.ModelSerializer):
    """Repayment schedule summary"""
    
    class Meta:
        model = RepaymentSchedule
        fields = '__all__'
        read_only_fields = '__all__'


class InterestRatePolicySerializer(serializers.ModelSerializer):
    """Bank interest rate policy"""
    bank_name = serializers.CharField(source='bank.name', read_only=True)
    climate_reset_threshold_display = serializers.CharField(
        source='get_climate_reset_threshold_display', read_only=True
    )
    
    class Meta:
        model = InterestRatePolicy
        fields = '__all__'
        read_only_fields = ['bank', 'created_at', 'updated_at']


class InterestRatePolicyWriteSerializer(serializers.ModelSerializer):
    """Write serializer for creating/updating rate policy"""
    
    class Meta:
        model = InterestRatePolicy
        fields = [
            'max_rate', 'min_rate', 'climate_reset_threshold',
            'climate_floor_rate', 'auto_reset_enabled'
        ]
    
    def validate(self, attrs):
        """Validate min_rate <= climate_floor_rate <= max_rate"""
        min_rate = attrs.get('min_rate')
        max_rate = attrs.get('max_rate')
        floor_rate = attrs.get('climate_floor_rate')
        
        if min_rate and floor_rate and min_rate > floor_rate:
            raise serializers.ValidationError({
                'climate_floor_rate': f'Must be >= min_rate ({min_rate}%)'
            })
        
        if max_rate and floor_rate and floor_rate > max_rate:
            raise serializers.ValidationError({
                'climate_floor_rate': f'Must be <= max_rate ({max_rate}%)'
            })
        
        return attrs


class ClimateRateAdjustmentSerializer(serializers.ModelSerializer):
    """Climate-triggered rate adjustment"""
    loan_application_id = serializers.CharField(source='loan.application_id', read_only=True)
    bank_name = serializers.CharField(source='bank.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviewed_by_name = serializers.CharField(
        source='reviewed_by.get_full_name', read_only=True
    )
    
    class Meta:
        model = ClimateRateAdjustment
        fields = '__all__'
        read_only_fields = [
            'loan', 'bank', 'climate_event_id', 'climate_severity',
            'climate_region', 'old_rate', 'new_rate', 'reason',
            'status', 'reviewed_by', 'reviewed_at', 'applied_at'
        ]


class LoanRestructureSerializer(serializers.ModelSerializer):
    """Loan restructure record"""
    loan_application_id = serializers.CharField(source='loan.application_id', read_only=True)
    bank_name = serializers.CharField(source='bank.name', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviewed_by_name = serializers.CharField(
        source='reviewed_by.get_full_name', read_only=True
    )
    
    class Meta:
        model = LoanRestructure
        fields = '__all__'
        read_only_fields = [
            'loan', 'bank', 'status', 'reviewed_by', 'reviewed_at',
            'completed_at', 'new_monthly_payment'
        ]


class LoanRestructureWriteSerializer(serializers.ModelSerializer):
    """Write serializer for initiating restructure"""
    
    class Meta:
        model = LoanRestructure
        fields = [
            'loan', 'reason', 'notes', 'new_interest_rate',
            'new_repayment_period_months'
        ]


class LoanAuditLogSerializer(serializers.ModelSerializer):
    """Audit log entry"""
    loan_application_id = serializers.CharField(source='loan.application_id', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    performed_by_name = serializers.CharField(
        source='performed_by.get_full_name', read_only=True
    )
    
    class Meta:
        model = LoanAuditLog
        fields = '__all__'
        read_only_fields = '__all__'