"""
Scoring App Test Suite
"""

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from apps.scoring.models import PulseScore, FraudAlert
from apps.scoring.algorithms import PulseScoreEngine, FraudDetector, ScoreFreezer
from apps.farmers.models import Farmer
from apps.farms.models import Farm
from apps.banks.models import Bank


class PulseScoreEngineTestCase(TestCase):
    """Test score calculation"""
    
    def setUp(self):
        self.bank = Bank.objects.create(name='Test Bank', email='test@bank.com')
        self.farmer = Farmer.objects.create(
            full_name='Test Farmer',
            phone_number='+254712345678',
            pulse_id='PID-TEST'
        )
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            name='Test Farm',
            size_acres=Decimal('2.5')
        )
    
    def test_score_calculation(self):
        """Test basic score calculation"""
        engine = PulseScoreEngine()
        result = engine.calculate_score(self.farmer, self.farm)
        
        self.assertIn('score', result)
        self.assertIn('confidence', result)
        self.assertIn('breakdown', result)
        self.assertGreaterEqual(result['score'], 0)
        self.assertLessEqual(result['score'], 1000)


class FraudDetectorTestCase(TestCase):
    """Test fraud detection"""
    
    def setUp(self):
        self.farmer = Farmer.objects.create(
            full_name='Fraud Test',
            phone_number='+254723456789',
            pulse_id='PID-FRAUD'
        )
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            name='Test Farm',
            size_acres=Decimal('1.0')
        )
    
    def test_duplicate_identity_detection(self):
        """Test duplicate phone detection"""
        # Create duplicate
        Farmer.objects.create(
            full_name='Duplicate',
            phone_number='+254723456789',
            pulse_id='PID-DUP'
        )
        
        alerts = FraudDetector.check_duplicate_identity(self.farmer)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].alert_type, 'duplicate_identity')


class ScoreFreezerTestCase(TestCase):
    """Test score freezing"""
    
    def setUp(self):
        self.farmer = Farmer.objects.create(
            full_name='Freeze Test',
            phone_number='+254734567890',
            pulse_id='PID-FREEZE'
        )
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            name='Test Farm',
            size_acres=Decimal('3.0')
        )
        self.score = PulseScore.objects.create(
            farmer=self.farmer,
            farm=self.farm,
            score=750,
            confidence_level=0.85,
            farm_size_score=80,
            crop_health_score=85,
            climate_risk_score=70,
            deforestation_score=100,
            payment_history_score=50,
            max_loan_amount=Decimal('50000'),
            recommended_interest_rate_min=12.0,
            recommended_interest_rate_max=14.0,
            default_probability=8.0,
            calculation_method='v1.0',
            factors_used={},
            valid_until=timezone.now() + timedelta(days=30),
            is_current=True
        )
    
    def test_score_is_frozen(self):
        """Test score freezing check"""
        self.assertFalse(ScoreFreezer.is_score_frozen(self.farmer))