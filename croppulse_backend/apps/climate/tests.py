# apps/climate/tests.py
from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timedelta
from apps.climate.models import ClimateData, ClimateRiskAssessment
from apps.climate.services.risk_calculator import RiskCalculator
from apps.climate.services.historical_analysis import HistoricalAnalysisService
from apps.climate.services.alert_generator import AlertGenerator
from apps.climate.services.insurance_trigger import InsuranceTriggerService
from apps.farms.models import Farm
from apps.farmers.models import Farmer


class ClimateDataModelTest(TestCase):
    """Test ClimateData model"""
    
    def setUp(self):
        """Set up test data"""
        self.farmer = Farmer.objects.create(
            first_name='John',
            last_name='Doe',
            phone_number='+254700000000',
            pulse_id='TEST001'
        )
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            name='Test Farm',
            latitude=-1.2921,
            longitude=36.8219,
            area_hectares=2.5
        )
    
    def test_create_climate_data(self):
        """Test creating climate data"""
        climate_data = ClimateData.objects.create(
            farm=self.farm,
            date=datetime.now().date(),
            temperature_max=30.0,
            temperature_min=20.0,
            temperature_avg=25.0,
            rainfall=5.0,
            rainfall_probability=30.0,
            humidity=65.0,
            wind_speed=10.0,
            data_source='NASA_POWER',
            is_forecast=False
        )
        
        self.assertEqual(climate_data.farm, self.farm)
        self.assertEqual(climate_data.temperature_avg, 25.0)
        self.assertFalse(climate_data.is_forecast)
    
    def test_unique_farm_date_constraint(self):
        """Test that farm-date combination is unique"""
        date = datetime.now().date()
        
        ClimateData.objects.create(
            farm=self.farm,
            date=date,
            temperature_max=30.0,
            temperature_min=20.0,
            temperature_avg=25.0,
            rainfall=5.0,
            rainfall_probability=30.0,
            humidity=65.0,
            wind_speed=10.0
        )
        
        # Attempting to create another record with same farm and date should fail
        with self.assertRaises(Exception):
            ClimateData.objects.create(
                farm=self.farm,
                date=date,
                temperature_max=32.0,
                temperature_min=22.0,
                temperature_avg=27.0,
                rainfall=10.0,
                rainfall_probability=50.0,
                humidity=70.0,
                wind_speed=15.0
            )


class RiskCalculatorTest(TestCase):
    """Test RiskCalculator service"""
    
    def setUp(self):
        """Set up test data"""
        self.farmer = Farmer.objects.create(
            first_name='Jane',
            last_name='Smith',
            phone_number='+254700000001',
            pulse_id='TEST002'
        )
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            name='Risk Test Farm',
            latitude=-1.2921,
            longitude=36.8219,
            area_hectares=3.0
        )
        
        # Create climate data for the last 90 days
        base_date = datetime.now().date()
        for i in range(90):
            date = base_date - timedelta(days=i)
            # Simulate drought conditions (low rainfall)
            ClimateData.objects.create(
                farm=self.farm,
                date=date,
                temperature_max=32.0,
                temperature_min=22.0,
                temperature_avg=27.0,
                rainfall=0.5,  # Very low rainfall
                rainfall_probability=10.0,
                humidity=50.0,
                wind_speed=12.0,
                is_forecast=False
            )
        
        self.risk_calculator = RiskCalculator(self.farm)
    
    def test_calculate_drought_risk(self):
        """Test drought risk calculation"""
        drought_risk = self.risk_calculator.calculate_drought_risk(days=90)
        
        # With very low rainfall, drought risk should be high
        self.assertGreater(drought_risk, 40.0)
        self.assertLessEqual(drought_risk, 100.0)
    
    def test_calculate_flood_risk(self):
        """Test flood risk calculation"""
        # Create some heavy rainfall days
        base_date = datetime.now().date()
        for i in range(5):
            date = base_date - timedelta(days=i)
            ClimateData.objects.update_or_create(
                farm=self.farm,
                date=date,
                defaults={
                    'temperature_max': 28.0,
                    'temperature_min': 20.0,
                    'temperature_avg': 24.0,
                    'rainfall': 60.0,  # Heavy rainfall
                    'rainfall_probability': 90.0,
                    'humidity': 85.0,
                    'wind_speed': 15.0,
                    'is_forecast': False
                }
            )
        
        flood_risk = self.risk_calculator.calculate_flood_risk(days=30)
        
        # With heavy rainfall, flood risk should be elevated
        self.assertGreater(flood_risk, 0.0)
    
    def test_create_risk_assessment(self):
        """Test creating a complete risk assessment"""
        assessment = self.risk_calculator.create_risk_assessment(analysis_period_days=90)
        
        self.assertIsInstance(assessment, ClimateRiskAssessment)
        self.assertEqual(assessment.farm, self.farm)
        self.assertIsNotNone(assessment.drought_risk)
        self.assertIsNotNone(assessment.flood_risk)
        self.assertIsNotNone(assessment.heat_stress_risk)
        self.assertIsNotNone(assessment.overall_climate_risk)
        self.assertIsInstance(assessment.recommendations, list)
    
    def test_risk_level_labels(self):
        """Test risk level label generation"""
        labels = [
            (10, 'LOW'),
            (25, 'MODERATE'),
            (50, 'HIGH'),
            (80, 'CRITICAL')
        ]
        
        for score, expected_label in labels:
            label = self.risk_calculator.get_risk_level_label(score)
            self.assertEqual(label, expected_label)


class HistoricalAnalysisTest(TestCase):
    """Test HistoricalAnalysisService"""
    
    def setUp(self):
        """Set up test data"""
        self.farmer = Farmer.objects.create(
            first_name='Bob',
            last_name='Johnson',
            phone_number='+254700000002',
            pulse_id='TEST003'
        )
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            name='Analysis Test Farm',
            latitude=-1.2921,
            longitude=36.8219,
            area_hectares=4.0
        )
        
        # Create climate data
        base_date = datetime.now().date()
        for i in range(60):
            date = base_date - timedelta(days=i)
            ClimateData.objects.create(
                farm=self.farm,
                date=date,
                temperature_max=30.0 + (i % 10),
                temperature_min=18.0 + (i % 5),
                temperature_avg=24.0 + (i % 7),
                rainfall=5.0 if i % 3 == 0 else 0.0,
                rainfall_probability=30.0,
                humidity=60.0 + (i % 20),
                wind_speed=8.0 + (i % 5),
                is_forecast=False
            )
        
        self.analysis_service = HistoricalAnalysisService(self.farm)
    
    def test_get_temperature_trends(self):
        """Test temperature trends analysis"""
        trends = self.analysis_service.get_temperature_trends(days=30)
        
        self.assertIsNotNone(trends)
        self.assertIn('average_temperature', trends)
        self.assertIn('maximum_temperature', trends)
        self.assertIn('minimum_temperature', trends)
        self.assertIn('extreme_heat_days', trends)
    
    def test_get_rainfall_distribution(self):
        """Test rainfall distribution analysis"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        
        distribution = self.analysis_service.get_rainfall_distribution(start_date, end_date)
        
        self.assertIsNotNone(distribution)
        self.assertIn('total_rainfall_mm', distribution)
        self.assertIn('rainy_days', distribution)
        self.assertIn('dry_spell_days', distribution)
    
    def test_identify_dry_spells(self):
        """Test dry spell identification"""
        dry_spells = self.analysis_service.identify_dry_spells(days=60)
        
        self.assertIsInstance(dry_spells, list)


class AlertGeneratorTest(TestCase):
    """Test AlertGenerator service"""
    
    def setUp(self):
        """Set up test data"""
        self.farmer = Farmer.objects.create(
            first_name='Alice',
            last_name='Williams',
            phone_number='+254700000003',
            pulse_id='TEST004'
        )
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            name='Alert Test Farm',
            latitude=-1.2921,
            longitude=36.8219,
            area_hectares=2.0
        )
        
        # Create a high-risk assessment
        self.assessment = ClimateRiskAssessment.objects.create(
            farm=self.farm,
            drought_risk=75.0,  # Critical
            flood_risk=30.0,
            heat_stress_risk=45.0,  # Warning
            overall_climate_risk=50.0,
            analysis_start_date=datetime.now().date() - timedelta(days=90),
            analysis_end_date=datetime.now().date(),
            historical_rainfall_avg=100.0,
            current_season_rainfall=40.0,
            rainfall_deviation_percentage=-60.0,
            recommendations=[]
        )
        
        self.alert_generator = AlertGenerator(self.farm)
    
    def test_check_and_generate_alerts(self):
        """Test alert generation"""
        alerts = self.alert_generator.check_and_generate_alerts()
        
        self.assertIsInstance(alerts, list)
        self.assertGreater(len(alerts), 0)
        
        # Check for drought alert (critical level)
        drought_alerts = [a for a in alerts if a['type'] == 'DROUGHT']
        self.assertGreater(len(drought_alerts), 0)
    
    def test_format_alert_for_sms(self):
        """Test SMS formatting"""
        alert = {
            'type': 'DROUGHT',
            'severity': 'CRITICAL',
            'message': 'Critical drought conditions detected. Take immediate action.'
        }
        
        sms = self.alert_generator.format_alert_for_sms(alert)
        
        self.assertLessEqual(len(sms), 160)
        self.assertIn('DROUGHT', sms)


class InsuranceTriggerTest(TestCase):
    """Test InsuranceTriggerService"""
    
    def setUp(self):
        """Set up test data"""
        self.farmer = Farmer.objects.create(
            first_name='Charlie',
            last_name='Brown',
            phone_number='+254700000004',
            pulse_id='TEST005'
        )
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            name='Insurance Test Farm',
            latitude=-1.2921,
            longitude=36.8219,
            area_hectares=5.0
        )
        
        # Create drought conditions (very low rainfall over 90 days)
        base_date = datetime.now().date()
        for i in range(90):
            date = base_date - timedelta(days=i)
            ClimateData.objects.create(
                farm=self.farm,
                date=date,
                temperature_max=32.0,
                temperature_min=22.0,
                temperature_avg=27.0,
                rainfall=0.2,  # Severe drought
                rainfall_probability=5.0,
                humidity=45.0,
                wind_speed=12.0,
                is_forecast=False
            )
        
        self.insurance_service = InsuranceTriggerService(self.farm)
    
    def test_check_drought_trigger(self):
        """Test drought insurance trigger"""
        trigger = self.insurance_service.check_drought_trigger(
            coverage_period_days=90,
            threshold_percentage=30
        )
        
        self.assertIsInstance(trigger, dict)
        self.assertIn('triggered', trigger)
        self.assertIn('payout_percentage', trigger)
        
        # With severe drought, trigger should be activated
        self.assertTrue(trigger['triggered'])
        self.assertGreater(trigger['payout_percentage'], 0)
    
    def test_calculate_total_payout(self):
        """Test total payout calculation"""
        payout = self.insurance_service.calculate_total_payout(
            policy_sum_insured=100000.0
        )
        
        self.assertIsInstance(payout, dict)
        self.assertIn('payout_amount', payout)
        self.assertIn('payout_eligible', payout)
        
        # With drought conditions, should be eligible for payout
        if payout['payout_eligible']:
            self.assertGreater(payout['payout_amount'], 0)