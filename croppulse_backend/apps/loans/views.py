"""
Loans App Views

API endpoints for:
- Loan applications (CRUD)
- Loan approval/rejection
- Loan disbursement
- Repayment tracking
- M-Pesa callbacks
- Interest rate policies
- Climate adjustments
- Loan restructuring
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend

from apps.loans.models import (
    LoanApplication,
    LoanRepayment,
    RepaymentSchedule,
    InterestRatePolicy,
    ClimateRateAdjustment,
    LoanRestructure,
    LoanAuditLog
)
from apps.loans.serializers import (
    LoanApplicationSerializer,
    LoanApplicationWriteSerializer,
    LoanRepaymentSerializer,
    RepaymentScheduleSerializer,
    InterestRatePolicySerializer,
    InterestRatePolicyWriteSerializer,
    ClimateRateAdjustmentSerializer,
    LoanRestructureSerializer,
    LoanRestructureWriteSerializer,
    LoanAuditLogSerializer
)
from apps.loans.services import (
    ApprovalEngine,
    MpesaIntegration,
    RepaymentScheduler,
    RestructureService,
    LoanCalculator
)
from core.mixins.tenant_mixin import BankContextMixin
from decimal import Decimal


class LoanApplicationListView(BankContextMixin, APIView):
    """
    GET: List loans for current bank
    POST: Create new loan application
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        bank = self.get_bank()
        
        loans = LoanApplication.objects.filter(bank=bank).order_by('-created_at')
        
        # Filters
        status_filter = request.query_params.get('status')
        farmer_id = request.query_params.get('farmer_id')
        
        if status_filter:
            loans = loans.filter(status=status_filter)
        if farmer_id:
            loans = loans.filter(farmer_id=farmer_id)
        
        serializer = LoanApplicationSerializer(loans, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        bank = self.get_bank()
        
        serializer = LoanApplicationWriteSerializer(data=request.data)
        if serializer.is_valid():
            loan = serializer.save(bank=bank)
            return Response(
                LoanApplicationSerializer(loan).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoanApplicationDetailView(BankContextMixin, APIView):
    """
    GET: Retrieve loan details
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, loan_id):
        bank = self.get_bank()
        loan = get_object_or_404(LoanApplication, id=loan_id, bank=bank)
        
        serializer = LoanApplicationSerializer(loan)
        return Response(serializer.data)


class LoanApproveView(BankContextMixin, APIView):
    """
    POST: Approve a loan application
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, loan_id):
        bank = self.get_bank()
        loan = get_object_or_404(LoanApplication, id=loan_id, bank=bank)
        
        try:
            # Optional override rate
            override_rate = request.data.get('override_rate')
            if override_rate:
                override_rate = float(override_rate)
            
            # Approve loan
            approved_loan = ApprovalEngine.approve(
                loan=loan,
                reviewed_by=request.user,
                override_rate=override_rate
            )
            
            serializer = LoanApplicationSerializer(approved_loan)
            return Response(serializer.data)
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class LoanDisbursementView(BankContextMixin, APIView):
    """
    POST: Disburse approved loan via M-Pesa
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, loan_id):
        bank = self.get_bank()
        loan = get_object_or_404(LoanApplication, id=loan_id, bank=bank)
        
        try:
            # Disburse via M-Pesa
            result = MpesaIntegration.disburse(loan)
            
            if result['success']:
                serializer = LoanApplicationSerializer(loan)
                return Response({
                    'loan': serializer.data,
                    'disbursement': result
                })
            else:
                return Response(
                    {'error': result['message']},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class LoanMpesaCallbackView(APIView):
    """
    POST: M-Pesa callback for loan repayments (no auth required)
    """
    permission_classes = []  # M-Pesa will call this
    
    def post(self, request):
        payload = request.data
        
        result = MpesaIntegration.on_repayment_callback(payload)
        
        return Response({
            'ResultCode': 0 if result['success'] else 1,
            'ResultDesc': result['message']
        })


class LoanRepaymentListView(BankContextMixin, APIView):
    """
    GET: List repayments for a loan
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, loan_id):
        bank = self.get_bank()
        loan = get_object_or_404(LoanApplication, id=loan_id, bank=bank)
        
        repayments = LoanRepayment.objects.filter(loan=loan).order_by('payment_number')
        
        serializer = LoanRepaymentSerializer(repayments, many=True)
        return Response(serializer.data)


class RepaymentScheduleView(BankContextMixin, APIView):
    """
    GET: Get repayment schedule for a loan
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, loan_id):
        bank = self.get_bank()
        loan = get_object_or_404(LoanApplication, id=loan_id, bank=bank)
        
        schedule = RepaymentScheduler.get_current_schedule(loan)
        
        if not schedule:
            return Response(
                {'error': 'No repayment schedule found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = RepaymentScheduleSerializer(schedule)
        return Response(serializer.data)


class LoanAuditLogListView(BankContextMixin, APIView):
    """
    GET: List audit logs for a loan
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, loan_id):
        bank = self.get_bank()
        loan = get_object_or_404(LoanApplication, id=loan_id, bank=bank)
        
        logs = LoanAuditLog.objects.filter(loan=loan).order_by('-created_at')
        
        serializer = LoanAuditLogSerializer(logs, many=True)
        return Response(serializer.data)


class EMICalculatorView(APIView):
    """
    POST: Calculate EMI for given loan parameters
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        principal = request.data.get('principal')
        annual_rate = request.data.get('annual_rate')
        months = request.data.get('months')
        
        if not all([principal, annual_rate, months]):
            return Response(
                {'error': 'Missing required fields: principal, annual_rate, months'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            principal = Decimal(str(principal))
            annual_rate = float(annual_rate)
            months = int(months)
            
            emi = LoanCalculator.calculate_emi(principal, annual_rate, months)
            
            # Calculate total repayment
            total_repayment = emi * months
            total_interest = total_repayment - principal
            
            return Response({
                'emi': str(emi),
                'total_interest': str(total_interest),
                'total_repayment': str(total_repayment),
                'principal': str(principal),
                'annual_rate': annual_rate,
                'months': months
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class InterestRatePolicyListView(BankContextMixin, APIView):
    """
    GET: List rate policies for bank
    POST: Create new rate policy
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        bank = self.get_bank()
        
        policies = InterestRatePolicy.objects.filter(bank=bank).order_by('-created_at')
        
        serializer = InterestRatePolicySerializer(policies, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        bank = self.get_bank()
        
        serializer = InterestRatePolicyWriteSerializer(data=request.data)
        if serializer.is_valid():
            # Deactivate old policies
            InterestRatePolicy.objects.filter(bank=bank, is_active=True).update(
                is_active=False
            )
            
            # Create new policy
            policy = serializer.save(bank=bank, is_active=True)
            
            return Response(
                InterestRatePolicySerializer(policy).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InterestRatePolicyDetailView(BankContextMixin, APIView):
    """
    GET: Retrieve rate policy details
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, policy_id):
        bank = self.get_bank()
        policy = get_object_or_404(InterestRatePolicy, id=policy_id, bank=bank)
        
        serializer = InterestRatePolicySerializer(policy)
        return Response(serializer.data)


class ClimateRateAdjustmentListView(BankContextMixin, APIView):
    """
    GET: List climate rate adjustments
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        bank = self.get_bank()
        
        adjustments = ClimateRateAdjustment.objects.filter(
            bank=bank
        ).order_by('-created_at')
        
        # Filters
        status_filter = request.query_params.get('status')
        loan_id = request.query_params.get('loan_id')
        
        if status_filter:
            adjustments = adjustments.filter(status=status_filter)
        if loan_id:
            adjustments = adjustments.filter(loan_id=loan_id)
        
        serializer = ClimateRateAdjustmentSerializer(adjustments, many=True)
        return Response(serializer.data)


class ClimateRateAdjustmentReviewView(BankContextMixin, APIView):
    """
    POST: Review a climate rate adjustment (approve/reject)
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, adjustment_id):
        bank = self.get_bank()
        adjustment = get_object_or_404(
            ClimateRateAdjustment,
            id=adjustment_id,
            bank=bank
        )
        
        action = request.data.get('action')  # 'apply' or 'reject'
        notes = request.data.get('notes', '')
        
        if action == 'apply':
            try:
                RestructureService.apply_climate_adjustment(
                    adjustment,
                    reviewed_by=request.user
                )
                
                serializer = ClimateRateAdjustmentSerializer(adjustment)
                return Response(serializer.data)
            
            except ValueError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        elif action == 'reject':
            adjustment.status = 'rejected'
            adjustment.reviewed_by = request.user
            adjustment.reviewed_at = timezone.now()
            adjustment.save()
            
            serializer = ClimateRateAdjustmentSerializer(adjustment)
            return Response(serializer.data)
        
        else:
            return Response(
                {'error': "Action must be 'apply' or 'reject'"},
                status=status.HTTP_400_BAD_REQUEST
            )


class LoanRestructureListView(BankContextMixin, APIView):
    """
    GET: List loan restructures
    POST: Initiate loan restructure
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        bank = self.get_bank()
        
        restructures = LoanRestructure.objects.filter(
            bank=bank
        ).order_by('-created_at')
        
        serializer = LoanRestructureSerializer(restructures, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        bank = self.get_bank()
        
        serializer = LoanRestructureWriteSerializer(data=request.data)
        if serializer.is_valid():
            loan = serializer.validated_data['loan']
            
            if loan.bank != bank:
                return Response(
                    {'error': 'Loan does not belong to this bank'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            try:
                restructure = RestructureService.initiate_restructure(
                    loan=loan,
                    new_interest_rate=serializer.validated_data['new_interest_rate'],
                    new_repayment_period_months=serializer.validated_data['new_repayment_period_months'],
                    reason=serializer.validated_data['reason'],
                    notes=serializer.validated_data.get('notes', ''),
                    auto_approve=False
                )
                
                return Response(
                    LoanRestructureSerializer(restructure).data,
                    status=status.HTTP_201_CREATED
                )
            
            except ValueError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoanRestructureReviewView(BankContextMixin, APIView):
    """
    POST: Review a loan restructure (approve/reject/complete)
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, restructure_id):
        bank = self.get_bank()
        restructure = get_object_or_404(
            LoanRestructure,
            id=restructure_id,
            bank=bank
        )
        
        action = request.data.get('action')  # 'approve', 'reject', 'complete'
        notes = request.data.get('notes', '')
        
        try:
            if action == 'approve':
                RestructureService.approve_restructure(
                    restructure,
                    reviewed_by=request.user
                )
            elif action == 'reject':
                RestructureService.reject_restructure(
                    restructure,
                    reviewed_by=request.user,
                    notes=notes
                )
            elif action == 'complete':
                RestructureService.complete_restructure(restructure)
            else:
                return Response(
                    {'error': "Action must be 'approve', 'reject', or 'complete'"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = LoanRestructureSerializer(restructure)
            return Response(serializer.data)
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


from django.utils import timezone