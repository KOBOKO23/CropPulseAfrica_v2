from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from apps.compliance.models import ExportPassport, DeforestationCheck
from .services import (
    EUDRPassportGenerator,
    QRCodeGenerator,
    DeforestationAnalyzer,
    BlockchainAnchor
)
from apps.farmers.models import Farmer
from apps.farms.models import Farm
from apps.accounts.models import User


class ExportPassportModelTest(TestCase):
    """Test ExportPassport model"""
    
    def setUp(self):
        """Set up test data"""
        user = User.objects.create(username="testuser1", email="test1@example.com")
        self.farmer = Farmer.objects.create(
            user=user,
            pulse_id="CP-TEST-001",
            full_name="Test Farmer",
            id_number="ID123456",
            county="Nairobi",
            sub_county="Westlands",
            nearest_town="Nairobi",
            years_farming=5,
            primary_crop="Coffee"
        )
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_name="Test Farm",
            area_hectares=10.5
        )
    
    def test_passport_id_generation(self):
        """Test automatic passport ID generation"""
        passport = ExportPassport.objects.create(
            farmer=self.farmer,
            farm=self.farm,
            dds_reference_number="DDS-2026-TEST001",
            operator_name="Test Operator",
            commodity_type="COFFEE",
            commodity_code="0901",
            gps_coordinates=[
                {'lat': -1.2921, 'lng': 36.8219},
                {'lat': -1.2922, 'lng': 36.8220},
                {'lat': -1.2923, 'lng': 36.8221}
            ],
            centroid_latitude=-1.2922,
            centroid_longitude=36.8220,
            farm_size_hectares=10.5
        )
        
        self.assertIsNotNone(passport.passport_id)
        self.assertTrue(passport.passport_id.startswith('EU-'))
    
    def test_passport_expiry(self):
        """Test passport expiry logic"""
        passport = ExportPassport.objects.create(
            farmer=self.farmer,
            farm=self.farm,
            dds_reference_number="DDS-2026-TEST002",
            operator_name="Test Operator",
            commodity_type="COFFEE",
            commodity_code="0901",
            gps_coordinates=[{'lat': -1.2921, 'lng': 36.8219}],
            centroid_latitude=-1.2922,
            centroid_longitude=36.8220,
            farm_size_hectares=10.5,
            valid_until=timezone.now().date() - timedelta(days=1)
        )
        
        self.assertTrue(passport.is_expired())
        self.assertEqual(passport.days_until_expiry(), 0)
    
    def test_audit_trail(self):
        """Test audit trail functionality"""
        passport = ExportPassport.objects.create(
            farmer=self.farmer,
            farm=self.farm,
            dds_reference_number="DDS-2026-TEST003",
            operator_name="Test Operator",
            commodity_type="COFFEE",
            commodity_code="0901",
            gps_coordinates=[{'lat': -1.2921, 'lng': 36.8219}],
            centroid_latitude=-1.2922,
            centroid_longitude=36.8220,
            farm_size_hectares=10.5
        )
        
        passport.add_audit_entry(
            action='TEST',
            user='test_user',
            details={'test': 'data'}
        )
        
        self.assertEqual(len(passport.audit_trail), 1)
        self.assertEqual(passport.audit_trail[0]['action'], 'TEST')


class QRCodeGeneratorTest(TestCase):
    """Test QR code generation"""
    
    def setUp(self):
        """Set up test data"""
        user = User.objects.create(username="testuser2", email="test2@example.com")
        self.farmer = Farmer.objects.create(
            user=user,
            pulse_id="CP-TEST-002",
            full_name="Test Farmer",
            id_number="ID123457",
            county="Nairobi",
            sub_county="Westlands",
            nearest_town="Nairobi",
            years_farming=5,
            primary_crop="Coffee"
        )
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_name="Test Farm",
            area_hectares=10.5
        )
        
        self.passport = ExportPassport.objects.create(
            farmer=self.farmer,
            farm=self.farm,
            dds_reference_number="DDS-2026-TEST004",
            operator_name="Test Operator",
            commodity_type="COFFEE",
            commodity_code="0901",
            gps_coordinates=[{'lat': -1.2921, 'lng': 36.8219}],
            centroid_latitude=-1.2922,
            centroid_longitude=36.8220,
            farm_size_hectares=10.5
        )
    
    def test_qr_data_generation(self):
        """Test QR data generation"""
        generator = QRCodeGenerator()
        qr_data = generator.generate_qr_data(self.passport)
        
        self.assertIn('passport_id', qr_data)
        self.assertIn('dds_ref', qr_data)
        self.assertIn('coordinates', qr_data)
        self.assertEqual(qr_data['passport_id'], self.passport.passport_id)


class DeforestationAnalyzerTest(TestCase):
    """Test deforestation analysis"""
    
    def setUp(self):
        """Set up test data"""
        user = User.objects.create(username="testuser3", email="test3@example.com")
        self.farmer = Farmer.objects.create(
            user=user,
            pulse_id="CP-TEST-003",
            full_name="Test Farmer",
            id_number="ID123458",
            county="Nairobi",
            sub_county="Westlands",
            nearest_town="Nairobi",
            years_farming=5,
            primary_crop="Coffee"
        )
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_name="Test Farm",
            area_hectares=10.5
        )
    
    def test_risk_score_calculation(self):
        """Test risk score calculation"""
        check = DeforestationCheck.objects.create(
            farm=self.farm,
            analysis_start_date=timezone.now().date() - timedelta(days=365),
            analysis_end_date=timezone.now().date(),
            deforestation_detected=True,
            forest_cover_percentage=60.0,
            baseline_forest_cover=80.0,
            change_in_forest_cover=-20.0,
            satellite_provider='SENTINEL2'
        )
        
        risk_score = check.calculate_risk_score()
        self.assertGreater(risk_score, 0)
        self.assertLessEqual(risk_score, 100)


class EUDRPassportGeneratorTest(TestCase):
    """Test EUDR passport generation"""
    
    def setUp(self):
        """Set up test data"""
        user = User.objects.create(username="testuser4", email="test4@example.com")
        self.farmer = Farmer.objects.create(
            user=user,
            pulse_id="CP-TEST-004",
            full_name="Test Farmer",
            id_number="ID123459",
            county="Nairobi",
            sub_county="Westlands",
            nearest_town="Nairobi",
            years_farming=5,
            primary_crop="Coffee"
        )
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_name="Test Farm",
            area_hectares=10.5
        )
        
        # Create boundary points
        from apps.farms.models import FarmBoundaryPoint
        FarmBoundaryPoint.objects.create(
            farm=self.farm,
            latitude=-1.2921,
            longitude=36.8219,
            sequence=1
        )
        FarmBoundaryPoint.objects.create(
            farm=self.farm,
            latitude=-1.2922,
            longitude=36.8220,
            sequence=2
        )
        FarmBoundaryPoint.objects.create(
            farm=self.farm,
            latitude=-1.2923,
            longitude=36.8221,
            sequence=3
        )
    
    def test_dds_reference_generation(self):
        """Test DDS reference number generation"""
        generator = EUDRPassportGenerator()
        dds_ref = generator._generate_dds_reference()
        
        self.assertTrue(dds_ref.startswith('DDS-'))
        self.assertEqual(len(dds_ref.split('-')), 3)


class PassportIntegrationTest(TestCase):
    """Test full passport creation workflow"""
    
    def setUp(self):
        """Set up test data"""
        user = User.objects.create(username="integrationuser", email="integration@example.com")
        self.farmer = Farmer.objects.create(
            user=user,
            pulse_id="CP-TEST-005",
            full_name="Integration Test Farmer",
            id_number="ID123460",
            county="Nairobi",
            sub_county="Westlands",
            nearest_town="Nairobi",
            years_farming=10,
            primary_crop="Coffee"
        )
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_name="Integration Test Farm",
            area_hectares=15.0
        )
        
        # Create boundary points
        from apps.farms.models import FarmBoundaryPoint
        for i in range(4):
            FarmBoundaryPoint.objects.create(
                farm=self.farm,
                latitude=-1.2921 + (i * 0.0001),
                longitude=36.8219 + (i * 0.0001),
                sequence=i + 1
            )
    
    def test_full_passport_creation_workflow(self):
        """Test complete passport creation with all steps"""
        # This would be an integration test that mocks satellite services
        # and tests the full workflow
        pass
