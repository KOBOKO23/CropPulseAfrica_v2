"""
Loans App Django Admin
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from apps.loans.models import (
    LoanApplication,
    LoanRepayment,
    RepaymentSchedule,
    InterestRatePolicy,
    ClimateRateAdjustment,
    LoanRestructure,
    LoanAuditLog
)


@admin.register(LoanApplication)
class LoanApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'application_id', 'farmer_name', 'bank_name', 'requested_amount',
        'approved_amount', 'interest_rate', 'status_badge', 'climate_protected',
        'pulse_score_at_application', 'created_at'
    ]
    list_filter = [
        'status', 'climate_protected', 'bank', 'created_at'
    ]
    search_fields = [
        'application_id', 'farmer__full_name', 'farmer__pulse_id'
    ]
    readonly_fields = [
        'application_id', 'created_at', 'updated_at', 'reviewed_at',
        'disbursed_at', 'is_active', 'total_repaid', 'outstanding_balance'
    ]
    
    fieldsets = (
        ('Loan Details', {
            'fields': (
                'application_id', 'farmer', 'bank', 'loan_purpose',
                'requested_amount', 'approved_amount'
            )
        }),
        ('Terms', {
            'fields': (
                'interest_rate', 'interest_rate_cap', 'repayment_period_months'
            )
        }),
        ('Assessment', {
            'fields': (
                'pulse_score_at_application', 'satellite_verification_id',
                'climate_risk_at_application', 'climate_protected'
            )
        }),
        ('Status', {
            'fields': (
                'status', 'reviewed_at', 'disbursed_at', 'is_active',
                'total_repaid', 'outstanding_balance'
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'api_response_time_ms'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = []
    
    def farmer_name(self, obj):
        return obj.farmer.full_name
    farmer_name.short_description = 'Farmer'
    
    def bank_name(self, obj):
        return obj.bank.name
    bank_name.short_description = 'Bank'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'approved': 'blue',
            'rejected': 'red',
            'disbursed': 'green',
            'repaid': 'darkgreen',
            'defaulted': 'darkred'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    actions = ['approve_selected_loans', 'default_selected_loans']
    
    def approve_selected_loans(self, request, queryset):
        from apps.loans.services import ApprovalEngine
        
        count = 0
        for loan in queryset.filter(status='pending'):
            try:
                ApprovalEngine.approve(loan, reviewed_by=request.user)
                count += 1
            except ValueError:
                pass
        
        self.message_user(request, f'{count} loans approved')
    approve_selected_loans.short_description = 'Approve selected pending loans'
    
    def default_selected_loans(self, request, queryset):
        count = queryset.filter(status='disbursed').update(status='defaulted')
        self.message_user(request, f'{count} loans marked as defaulted')
    default_selected_loans.short_description = 'Mark selected loans as defaulted'


class LoanRepaymentInline(admin.TabularInline):
    model = LoanRepayment
    extra = 0
    readonly_fields = [
        'payment_number', 'due_date', 'amount_due', 'amount_paid',
        'paid_date', 'is_paid', 'is_late', 'days_late', 'mpesa_transaction_id'
    ]
    can_delete = False


@admin.register(LoanRepayment)
class LoanRepaymentAdmin(admin.ModelAdmin):
    list_display = [
        'loan_id', 'payment_number', 'due_date', 'amount_due',
        'amount_paid', 'paid_badge', 'late_badge', 'days_late'
    ]
    list_filter = ['is_paid', 'is_late', 'due_date']
    search_fields = ['loan__application_id', 'mpesa_transaction_id']
    readonly_fields = ['created_at']
    
    def loan_id(self, obj):
        return obj.loan.application_id
    loan_id.short_description = 'Loan'
    
    def paid_badge(self, obj):
        if obj.is_paid:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Paid</span>'
            )
        return format_html(
            '<span style="color: orange; font-weight: bold;">⏳ Pending</span>'
        )
    paid_badge.short_description = 'Status'
    
    def late_badge(self, obj):
        if obj.is_late:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ Late</span>'
            )
        return ''
    late_badge.short_description = 'Late?'


@admin.register(RepaymentSchedule)
class RepaymentScheduleAdmin(admin.ModelAdmin):
    list_display = [
        'loan_id', 'is_current', 'total_instalments', 'monthly_payment',
        'total_interest', 'interest_rate_used', 'start_date', 'end_date'
    ]
    list_filter = ['is_current', 'created_at']
    search_fields = ['loan__application_id']
    readonly_fields = [
        'loan', 'total_instalments', 'monthly_payment', 'total_interest',
        'total_repayment', 'start_date', 'end_date', 'interest_rate_used',
        'is_current', 'created_at'
    ]
    
    def loan_id(self, obj):
        return obj.loan.application_id
    loan_id.short_description = 'Loan'


@admin.register(InterestRatePolicy)
class InterestRatePolicyAdmin(admin.ModelAdmin):
    list_display = [
        'bank_name', 'active_badge', 'min_rate', 'max_rate',
        'climate_reset_threshold', 'climate_floor_rate',
        'auto_reset_enabled', 'created_at'
    ]
    list_filter = ['is_active', 'auto_reset_enabled', 'climate_reset_threshold']
    search_fields = ['bank__name']
    readonly_fields = ['created_at', 'updated_at']
    
    def bank_name(self, obj):
        return obj.bank.name
    bank_name.short_description = 'Bank'
    
    def active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Active</span>'
            )
        return format_html(
            '<span style="color: gray;">Inactive</span>'
        )
    active_badge.short_description = 'Status'


@admin.register(ClimateRateAdjustment)
class ClimateRateAdjustmentAdmin(admin.ModelAdmin):
    list_display = [
        'loan_id', 'bank_name', 'severity_badge', 'rate_change',
        'status_badge', 'reviewed_by_name', 'created_at'
    ]
    list_filter = ['status', 'climate_severity', 'bank', 'created_at']
    search_fields = [
        'loan__application_id', 'climate_event_id', 'climate_region'
    ]
    readonly_fields = [
        'created_at', 'reviewed_at', 'applied_at'
    ]
    
    def loan_id(self, obj):
        return obj.loan.application_id
    loan_id.short_description = 'Loan'
    
    def bank_name(self, obj):
        return obj.bank.name
    bank_name.short_description = 'Bank'
    
    def severity_badge(self, obj):
        colors = {
            'low': 'yellow',
            'moderate': 'orange',
            'high': 'darkorange',
            'critical': 'red'
        }
        color = colors.get(obj.climate_severity, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.climate_severity.upper()
        )
    severity_badge.short_description = 'Severity'
    
    def rate_change(self, obj):
        return f"{obj.old_rate}% → {obj.new_rate}%"
    rate_change.short_description = 'Rate Change'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'applied': 'green',
            'rejected': 'red',
            'cancelled': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def reviewed_by_name(self, obj):
        return obj.reviewed_by.get_full_name() if obj.reviewed_by else '-'
    reviewed_by_name.short_description = 'Reviewed By'


@admin.register(LoanRestructure)
class LoanRestructureAdmin(admin.ModelAdmin):
    list_display = [
        'loan_id', 'status_badge', 'reason', 'rate_change',
        'reviewed_by_name', 'created_at'
    ]
    list_filter = ['status', 'reason', 'bank', 'created_at']
    search_fields = ['loan__application_id', 'notes']
    readonly_fields = [
        'created_at', 'reviewed_at', 'completed_at'
    ]
    
    def loan_id(self, obj):
        return obj.loan.application_id
    loan_id.short_description = 'Loan'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'approved': 'blue',
            'rejected': 'red',
            'completed': 'green'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def rate_change(self, obj):
        return f"{obj.old_interest_rate}% → {obj.new_interest_rate}%"
    rate_change.short_description = 'Rate Change'
    
    def reviewed_by_name(self, obj):
        return obj.reviewed_by.get_full_name() if obj.reviewed_by else '-'
    reviewed_by_name.short_description = 'Reviewed By'


@admin.register(LoanAuditLog)
class LoanAuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'loan_id', 'action', 'details_short', 'performed_by_name',
        'triggered_by_system', 'created_at'
    ]
    list_filter = ['action', 'triggered_by_system', 'created_at']
    search_fields = ['loan__application_id', 'details']
    readonly_fields = [
        'loan', 'action', 'old_value', 'new_value', 'details',
        'performed_by', 'triggered_by_system', 'created_at'
    ]
    
    # Prevent adding/changing/deleting audit logs
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def loan_id(self, obj):
        return obj.loan.application_id
    loan_id.short_description = 'Loan'
    
    def details_short(self, obj):
        return obj.details[:50] + '...' if len(obj.details) > 50 else obj.details
    details_short.short_description = 'Details'
    
    def performed_by_name(self, obj):
        return obj.performed_by.get_full_name() if obj.performed_by else 'System'
    performed_by_name.short_description = 'Performed By'