"""
Loans App Test Suite

Tests for:
- Loan calculator
- Approval engine
- Repayment scheduler
- Climate-triggered restructuring
- M-Pesa integration
"""

from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.loans.models import (
    LoanApplication, LoanRepayment, RepaymentSchedule,
    InterestRatePolicy, ClimateRateAdjustment, LoanRestructure,
    LoanAuditLog
)
from apps.loans.services import (
    LoanCalculator, ApprovalEngine, RepaymentScheduler,
    RestructureService, MpesaIntegration
)
from apps.farmers.models import Farmer
from apps.banks.models import Bank

User = get_user_model()


class LoanCalculatorTestCase(TestCase):
    """Test loan EMI and amortisation calculations"""
    
    def test_emi_calculation(self):
        """Test EMI formula correctness"""
        principal = Decimal('100000.00')
        rate = 12.0  # 12% per annum
        months = 12
        
        emi = LoanCalculator.calculate_emi(principal, rate, months)
        
        # EMI should be around 8884.88 for these parameters
        self.assertGreater(emi, Decimal('8880'))
        self.assertLess(emi, Decimal('8890'))
    
    def test_zero_interest_rate(self):
        """Test 0% interest edge case"""
        principal = Decimal('100000.00')
        rate = 0.0
        months = 10
        
        emi = LoanCalculator.calculate_emi(principal, rate, months)
        
        # EMI should be exactly principal / months
        self.assertEqual(emi, Decimal('10000.00'))
    
    def test_amortisation_schedule(self):
        """Test full amortisation schedule generation"""
        principal = Decimal('50000.00')
        rate = 10.0
        months = 6
        start_date = date(2026, 3, 1)
        
        schedule = LoanCalculator.generate_amortisation_schedule(
            principal, rate, months, start_date
        )
        
        # Verify structure
        self.assertIn('monthly_payment', schedule)
        self.assertIn('total_interest', schedule)
        self.assertIn('total_repayment', schedule)
        self.assertIn('rows', schedule)
        
        # Verify row count
        self.assertEqual(len(schedule['rows']), months)
        
        # Verify final balance is 0
        final_row = schedule['rows'][-1]
        self.assertEqual(final_row['closing_balance'], Decimal('0.00'))
        
        # Verify total repayment = principal + interest
        self.assertEqual(
            schedule['total_repayment'],
            principal + schedule['total_interest']
        )


class ApprovalEngineTestCase(TestCase):
    """Test loan approval logic"""
    
    def setUp(self):
        """Create test fixtures"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.bank = Bank.objects.create(
            name='Test Bank',
            email='bank@test.com'
        )
        self.farmer = Farmer.objects.create(
            full_name='John Farmer',
            phone_number='+254712345678',
            pulse_id='PID-001'
        )
        
        # Create rate policy
        InterestRatePolicy.objects.create(
            bank=self.bank,
            min_rate=5.0,
            max_rate=24.0,
            climate_reset_threshold='high',
            climate_floor_rate=3.0,
            auto_reset_enabled=True,
            is_active=True
        )
    
    def _make_loan(self, pulse_score):
        """Helper to create loan application"""
        return LoanApplication.objects.create(
            application_id=f'LN-TEST-{pulse_score}',
            farmer=self.farmer,
            bank=self.bank,
            requested_amount=Decimal('50000.00'),
            interest_rate=12.0,
            repayment_period_months=12,
            loan_purpose='Seeds',
            pulse_score_at_application=pulse_score,
            status='pending'
        )
    
    def test_high_score_gets_low_rate(self):
        """High pulse score should get lower interest rate"""
        loan = self._make_loan(pulse_score=900)
        
        evaluation = ApprovalEngine.evaluate(loan)
        
        self.assertTrue(evaluation['approved'])
        self.assertLess(evaluation['suggested_rate'], 10.0)
    
    def test_low_score_gets_high_rate(self):
        """Low pulse score should get higher interest rate"""
        loan = self._make_loan(pulse_score=400)
        
        evaluation = ApprovalEngine.evaluate(loan)
        
        self.assertTrue(evaluation['approved'])
        self.assertGreater(evaluation['suggested_rate'], 18.0)
    
    def test_below_minimum_rejected(self):
        """Score below 300 should be rejected"""
        loan = self._make_loan(pulse_score=250)
        
        evaluation = ApprovalEngine.evaluate(loan)
        
        self.assertFalse(evaluation['approved'])
        self.assertIn('below minimum threshold', evaluation['reason'])
    
    def test_approve_updates_status(self):
        """Approval should update loan status and rate"""
        loan = self._make_loan(pulse_score=700)
        
        approved_loan = ApprovalEngine.approve(loan, reviewed_by=self.user)
        
        self.assertEqual(approved_loan.status, 'approved')
        self.assertIsNotNone(approved_loan.interest_rate)
        self.assertIsNotNone(approved_loan.interest_rate_cap)
        self.assertIsNotNone(approved_loan.reviewed_at)
        
        # Check audit log
        audit = LoanAuditLog.objects.filter(loan=loan).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.action, 'status_change')


class RepaymentSchedulerTestCase(TestCase):
    """Test repayment schedule generation"""
    
    def setUp(self):
        """Create test fixtures"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.bank = Bank.objects.create(
            name='Test Bank',
            email='bank@test.com'
        )
        self.farmer = Farmer.objects.create(
            full_name='Jane Farmer',
            phone_number='+254723456789',
            pulse_id='PID-002'
        )
        
        # Create approved loan
        self.loan = LoanApplication.objects.create(
            application_id='LN-TEST-SCHED',
            farmer=self.farmer,
            bank=self.bank,
            requested_amount=Decimal('100000.00'),
            approved_amount=Decimal('100000.00'),
            interest_rate=12.0,
            repayment_period_months=10,
            loan_purpose='Fertilizer',
            pulse_score_at_application=750,
            status='approved'
        )
    
    def test_generate_schedule(self):
        """Test initial schedule generation"""
        schedule = RepaymentScheduler.generate(self.loan)
        
        self.assertEqual(schedule.loan, self.loan)
        self.assertEqual(schedule.total_instalments, 10)
        self.assertTrue(schedule.is_current)
        
        # Check repayment records created
        repayments = LoanRepayment.objects.filter(loan=self.loan)
        self.assertEqual(repayments.count(), 10)
        
        # Check first payment
        first_payment = repayments.first()
        self.assertEqual(first_payment.payment_number, 1)
        self.assertFalse(first_payment.is_paid)
    
    def test_cannot_generate_duplicate(self):
        """Should not allow duplicate schedule generation"""
        RepaymentScheduler.generate(self.loan)
        
        with self.assertRaises(ValueError):
            RepaymentScheduler.generate(self.loan)
    
    def test_regenerate_after_restructure(self):
        """Test schedule regeneration after loan restructure"""
        # Generate initial schedule
        old_schedule = RepaymentScheduler.generate(self.loan)
        
        # Mark loan as disbursed
        self.loan.status = 'disbursed'
        self.loan.save()
        
        # Regenerate with new terms
        new_schedule = RepaymentScheduler.regenerate(
            loan=self.loan,
            new_interest_rate=8.0,  # Lower rate
            new_repayment_period_months=15,  # Longer tenor
            outstanding_balance=Decimal('90000.00')
        )
        
        # Old schedule should be marked as superseded
        old_schedule.refresh_from_db()
        self.assertFalse(old_schedule.is_current)
        
        # New schedule should be current
        self.assertTrue(new_schedule.is_current)
        self.assertEqual(new_schedule.total_instalments, 15)
        
        # Check loan updated
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.interest_rate, 8.0)


class RestructureServiceTestCase(TestCase):
    """Test climate-triggered restructuring"""
    
    def setUp(self):
        """Create test fixtures"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.bank = Bank.objects.create(
            name='Test Bank',
            email='bank@test.com'
        )
        self.farmer = Farmer.objects.create(
            full_name='Climate Farmer',
            phone_number='+254734567890',
            pulse_id='PID-003'
        )
        
        # Create rate policy with auto-reset enabled
        self.policy = InterestRatePolicy.objects.create(
            bank=self.bank,
            min_rate=5.0,
            max_rate=24.0,
            climate_reset_threshold='high',
            climate_floor_rate=4.0,
            auto_reset_enabled=True,
            is_active=True
        )
        
        # Create disbursed loan
        self.loan = LoanApplication.objects.create(
            application_id='LN-CLIMATE-TEST',
            farmer=self.farmer,
            bank=self.bank,
            requested_amount=Decimal('80000.00'),
            approved_amount=Decimal('80000.00'),
            interest_rate=18.0,  # Will be reset to 4.0
            repayment_period_months=12,
            loan_purpose='Equipment',
            pulse_score_at_application=600,
            status='disbursed'
        )
        
        # Generate schedule
        RepaymentScheduler.generate(self.loan)
    
    def test_climate_event_creates_adjustments(self):
        """Climate event should create rate adjustments"""
        adjustments = RestructureService.on_climate_event(
            event_id='EVT-001',
            severity='high',
            region='Western Kenya',
            description='Severe drought'
        )
        
        self.assertGreater(len(adjustments), 0)
        
        # Check adjustment for our loan
        adjustment = ClimateRateAdjustment.objects.filter(
            loan=self.loan
        ).first()
        
        self.assertIsNotNone(adjustment)
        self.assertEqual(adjustment.old_rate, 18.0)
        self.assertEqual(adjustment.new_rate, 4.0)
        self.assertEqual(adjustment.status, 'applied')  # Auto-applied
    
    def test_severity_threshold(self):
        """Only events >= threshold should trigger adjustment"""
        # 'moderate' is below 'high' threshold
        adjustments = RestructureService.on_climate_event(
            event_id='EVT-002',
            severity='moderate',
            region='Central Kenya',
            description='Moderate flooding'
        )
        
        # Should not create adjustment for this loan
        self.assertEqual(len(adjustments), 0)
    
    def test_manual_approval_flow(self):
        """Test manual approval when auto_reset disabled"""
        # Disable auto-reset
        self.policy.auto_reset_enabled = False
        self.policy.save()
        
        adjustments = RestructureService.on_climate_event(
            event_id='EVT-003',
            severity='critical',
            region='Coast',
            description='Hurricane'
        )
        
        # Adjustment should be pending
        adjustment = adjustments[0]
        self.assertEqual(adjustment.status, 'pending')
        
        # Manually apply
        RestructureService.apply_climate_adjustment(
            adjustment,
            reviewed_by=self.user
        )
        
        adjustment.refresh_from_db()
        self.assertEqual(adjustment.status, 'applied')
        self.assertEqual(adjustment.reviewed_by, self.user)


class MpesaIntegrationTestCase(TestCase):
    """Test M-Pesa disbursement and repayment tracking"""
    
    def setUp(self):
        """Create test fixtures"""
        self.bank = Bank.objects.create(
            name='Test Bank',
            email='bank@test.com'
        )
        self.farmer = Farmer.objects.create(
            full_name='Mpesa Farmer',
            phone_number='+254745678901',
            pulse_id='PID-004'
        )
        
        # Create approved loan
        self.loan = LoanApplication.objects.create(
            application_id='LN-MPESA-TEST',
            farmer=self.farmer,
            bank=self.bank,
            requested_amount=Decimal('60000.00'),
            approved_amount=Decimal('60000.00'),
            interest_rate=15.0,
            repayment_period_months=6,
            loan_purpose='Seeds',
            pulse_score_at_application=650,
            status='approved'
        )
    
    def test_repayment_callback_processing(self):
        """Test M-Pesa repayment callback"""
        # Generate schedule first
        RepaymentScheduler.generate(self.loan)
        
        # Mark as disbursed
        self.loan.status = 'disbursed'
        self.loan.save()
        
        # Simulate M-Pesa callback
        payload = {
            'TransID': 'TEST12345',
            'TransAmount': '10500.00',
            'BillRefNumber': self.loan.application_id,
            'MSISDN': '+254745678901'
        }
        
        result = MpesaIntegration.on_repayment_callback(payload)
        
        self.assertTrue(result['success'])
        
        # Check first instalment updated
        first_payment = LoanRepayment.objects.filter(
            loan=self.loan,
            payment_number=1
        ).first()
        
        self.assertGreater(first_payment.amount_paid, Decimal('0'))
        self.assertEqual(first_payment.mpesa_transaction_id, 'TEST12345')
    
    def test_flag_defaults(self):
        """Test default flagging for overdue loans"""
        # Generate schedule
        RepaymentScheduler.generate(self.loan)
        
        # Mark as disbursed
        self.loan.status = 'disbursed'
        self.loan.save()
        
        # Make first payment overdue by 100 days
        first_payment = LoanRepayment.objects.filter(
            loan=self.loan,
            payment_number=1
        ).first()
        
        first_payment.due_date = date.today() - timedelta(days=100)
        first_payment.save()
        
        # Run default flagging
        count = MpesaIntegration.flag_defaults(days_overdue=90)
        
        self.assertEqual(count, 1)
        
        # Check loan marked as defaulted
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.status, 'defaulted')


class ModelValidationTestCase(TestCase):
    """Test model validations"""
    
    def setUp(self):
        """Create test fixtures"""
        self.bank = Bank.objects.create(
            name='Test Bank',
            email='bank@test.com'
        )
    
    def test_rate_policy_validation(self):
        """Test InterestRatePolicy.clean() validation"""
        from django.core.exceptions import ValidationError
        
        # Invalid: floor_rate > max_rate
        policy = InterestRatePolicy(
            bank=self.bank,
            min_rate=5.0,
            max_rate=20.0,
            climate_floor_rate=25.0,  # Too high!
            auto_reset_enabled=True
        )
        
        with self.assertRaises(ValidationError):
            policy.clean()
        
        # Invalid: floor_rate < min_rate
        policy2 = InterestRatePolicy(
            bank=self.bank,
            min_rate=5.0,
            max_rate=20.0,
            climate_floor_rate=3.0,  # Too low!
            auto_reset_enabled=True
        )
        
        with self.assertRaises(ValidationError):
            policy2.clean()


class APIIntegrationTestCase(TestCase):
    """Test API endpoints"""
    
    def setUp(self):
        """Setup API test fixtures"""
        self.user = User.objects.create_user(
            username='apiuser',
            password='testpass123'
        )
        self.bank = Bank.objects.create(
            name='API Test Bank',
            email='api@test.com'
        )
        self.farmer = Farmer.objects.create(
            full_name='API Farmer',
            phone_number='+254756789012',
            pulse_id='PID-API'
        )
        
        self.client.force_login(self.user)
    
    def test_create_loan_application(self):
        """Test POST /api/v1/loans/"""
        # Note: Actual endpoint testing would require DRF test client
        # This is a placeholder for integration test structure
        pass
    
    def test_list_loans(self):
        """Test GET /api/v1/loans/"""
        pass
    
    def test_emi_calculator(self):
        """Test POST /api/v1/loans/emi-calculator/"""
        pass