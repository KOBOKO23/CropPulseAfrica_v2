# apps/satellite/tests.py

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from django.contrib.gis.geos import Polygon, Point
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from apps.accounts.models import User
from apps.farmers.models import Farmer
from apps.farms.models import Farm
from .models import SatelliteScan, NDVIHistory
from .services.ndvi_calculator import NDVICalculator


class SatelliteScanModelTestCase(TestCase):
    """Test cases for SatelliteScan model"""
    
    def setUp(self):
        """Set up test data"""
        # Create user and farmer
        self.user = User.objects.create_user(
            username='testfarmer',
            email='farmer@test.com',
            phone_number='+254712345678',
            password='TestPass123!',
            user_type='farmer'
        )
        
        self.farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-TEST-001',
            full_name='Test Farmer',
            id_number='12345678',
            county='Nakuru',
            sub_county='Nakuru West',
            nearest_town='Nakuru',
            years_farming=5,
            primary_crop='Maize'
        )
        
        # Create farm with polygon
        coords = [
            (36.0800, -0.3031),
            (36.0820, -0.3031),
            (36.0820, -0.3051),
            (36.0800, -0.3051),
            (36.0800, -0.3031)
        ]
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_id='FARM-TEST-001',
            boundary=Polygon(coords),
            center_point=Point(36.0810, -0.3041),
            size_acres=2.4,
            size_hectares=0.97,
            county='Nakuru',
            sub_county='Nakuru West',
            ward='Test Ward'
        )
    
    def test_create_satellite_scan(self):
        """Test creating a satellite scan"""
        scan = SatelliteScan.objects.create(
            scan_id='SCAN-TEST-001',
            farm=self.farm,
            satellite_type='sentinel1',
            acquisition_date=datetime.now(),
            image_url='https://example.com/image.jpg',
            cloud_cover_percentage=25.5,
            sar_penetrated_clouds=False,
            ndvi=0.75,
            evi=0.68,
            savi=0.72,
            soil_moisture=65.0,
            crop_stage='Vegetative',
            crop_health_status='Healthy',
            verified_farm_size=2.35,
            matches_declared_size=True,
            raw_satellite_data={}
        )
        
        self.assertEqual(scan.scan_id, 'SCAN-TEST-001')
        self.assertEqual(scan.farm, self.farm)
        self.assertEqual(scan.ndvi, 0.75)
        self.assertTrue(scan.matches_declared_size)
    
    def test_scan_string_representation(self):
        """Test scan string representation"""
        scan = SatelliteScan.objects.create(
            scan_id='SCAN-TEST-002',
            farm=self.farm,
            satellite_type='sentinel2',
            acquisition_date=datetime.now(),
            image_url='',
            cloud_cover_percentage=10.0,
            crop_health_status='Healthy',
            verified_farm_size=2.4,
            raw_satellite_data={}
        )
        
        self.assertIn('SCAN-TEST-002', str(scan.scan_id))


class NDVIHistoryModelTestCase(TestCase):
    """Test cases for NDVIHistory model"""
    
    def setUp(self):
        """Set up test data"""
        # Reuse setup from SatelliteScanModelTestCase
        self.user = User.objects.create_user(
            username='testfarmer',
            email='farmer@test.com',
            phone_number='+254712345678',
            password='TestPass123!',
            user_type='farmer'
        )
        
        self.farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-TEST-001',
            full_name='Test Farmer',
            id_number='12345678',
            county='Nakuru',
            sub_county='Nakuru West',
            nearest_town='Nakuru',
            years_farming=5,
            primary_crop='Maize'
        )
        
        coords = [(36.08, -0.303), (36.082, -0.303), (36.082, -0.305), (36.08, -0.305), (36.08, -0.303)]
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_id='FARM-TEST-001',
            boundary=Polygon(coords),
            center_point=Point(36.081, -0.304),
            size_acres=2.4,
            size_hectares=0.97,
            county='Nakuru',
            sub_county='Nakuru West',
            ward='Test Ward'
        )
    
    def test_create_ndvi_history(self):
        """Test creating NDVI history entry"""
        history = NDVIHistory.objects.create(
            farm=self.farm,
            date=datetime.now().date(),
            ndvi_value=0.72
        )
        
        self.assertEqual(history.farm, self.farm)
        self.assertEqual(history.ndvi_value, 0.72)
    
    def test_ndvi_unique_constraint(self):
        """Test NDVI history unique constraint (farm + date)"""
        date = datetime.now().date()
        
        NDVIHistory.objects.create(
            farm=self.farm,
            date=date,
            ndvi_value=0.70
        )
        
        # Try to create duplicate
        with self.assertRaises(Exception):
            NDVIHistory.objects.create(
                farm=self.farm,
                date=date,
                ndvi_value=0.75
            )


class NDVICalculatorTestCase(TestCase):
    """Test cases for NDVI Calculator service"""
    
    def setUp(self):
        """Set up calculator"""
        self.calculator = NDVICalculator()
    
    def test_interpret_excellent_ndvi(self):
        """Test interpretation of excellent NDVI"""
        result = self.calculator.interpret_ndvi(0.80)
        
        self.assertEqual(result['status'], 'Healthy')
        self.assertEqual(result['category'], 'excellent')
        self.assertIn('Excellent', result['description'])
    
    def test_interpret_good_ndvi(self):
        """Test interpretation of good NDVI"""
        result = self.calculator.interpret_ndvi(0.65)
        
        self.assertEqual(result['status'], 'Healthy')
        self.assertEqual(result['category'], 'good')
    
    def test_interpret_poor_ndvi(self):
        """Test interpretation of poor NDVI"""
        result = self.calculator.interpret_ndvi(0.25)
        
        self.assertEqual(result['status'], 'Stressed')
        self.assertEqual(result['category'], 'poor')
    
    def test_compare_with_maize_baseline(self):
        """Test crop baseline comparison"""
        result = self.calculator.compare_with_crop_baseline(0.70, 'maize')
        
        self.assertEqual(result['crop_type'], 'maize')
        self.assertEqual(result['performance'], 'optimal')
        self.assertIn('healthy_range', result)
    
    def test_generate_health_score(self):
        """Test health score generation"""
        score = self.calculator.generate_health_score(
            ndvi_value=0.75,
            soil_moisture=60,
            rainfall_data=120
        )
        
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        self.assertGreater(score, 80)  # Should be high with good values


class SatelliteScanAPITestCase(APITestCase):
    """Test cases for Satellite Scan API"""
    
    def setUp(self):
        """Set up test client and data"""
        self.client = APIClient()
        
        # Create user and authenticate
        self.user = User.objects.create_user(
            username='testfarmer',
            email='farmer@test.com',
            phone_number='+254712345678',
            password='TestPass123!',
            user_type='farmer'
        )
        
        self.farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-TEST-001',
            full_name='Test Farmer',
            id_number='12345678',
            county='Nakuru',
            sub_county='Nakuru West',
            nearest_town='Nakuru',
            years_farming=5,
            primary_crop='Maize'
        )
        
        coords = [(36.08, -0.303), (36.082, -0.303), (36.082, -0.305), (36.08, -0.305), (36.08, -0.303)]
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_id='FARM-TEST-001',
            boundary=Polygon(coords),
            center_point=Point(36.081, -0.304),
            size_acres=2.4,
            size_hectares=0.97,
            county='Nakuru',
            sub_county='Nakuru West',
            ward='Test Ward'
        )
        
        # Create sample scan
        self.scan = SatelliteScan.objects.create(
            scan_id='SCAN-TEST-001',
            farm=self.farm,
            satellite_type='sentinel2',
            acquisition_date=datetime.now(),
            image_url='https://example.com/test.jpg',
            cloud_cover_percentage=15.0,
            ndvi=0.75,
            crop_health_status='Healthy',
            verified_farm_size=2.35,
            matches_declared_size=True,
            raw_satellite_data={}
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_list_satellite_scans(self):
        """Test listing satellite scans"""
        url = reverse('satellite:scan_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_scan_detail(self):
        """Test getting scan details"""
        url = reverse('satellite:scan_detail', kwargs={'scan_id': self.scan.scan_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scan_id'], self.scan.scan_id)
        self.assertIn('vegetation_indices', response.data)
    
    def test_get_farm_latest_scan(self):
        """Test getting latest scan for a farm"""
        url = reverse('satellite:farm_latest_scan', kwargs={'farm_id': self.farm.farm_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scan_id'], self.scan.scan_id)
    
    @patch('apps.satellite.tasks.process_satellite_scan.delay')
    def test_trigger_satellite_scan(self, mock_task):
        """Test triggering a satellite scan"""
        mock_task.return_value = MagicMock(id='test-task-id')
        
        url = reverse('satellite:trigger_scan')
        response = self.client.post(url, {'farm_id': self.farm.farm_id})
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('task_id', response.data['data'])
    
    def test_unauthorized_access(self):
        """Test unauthorized access to scans"""
        # Create another user
        other_user = User.objects.create_user(
            username='otherfarmer',
            email='other@test.com',
            phone_number='+254722222222',
            password='TestPass123!',
            user_type='farmer'
        )
        
        self.client.force_authenticate(user=other_user)
        
        url = reverse('satellite:scan_detail', kwargs={'scan_id': self.scan.scan_id})
        response = self.client.get(url)
        
        # Should return 404 (not found) since user doesn't own this farm
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class NDVITrendAPITestCase(APITestCase):
    """Test cases for NDVI Trend API"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            username='testfarmer',
            email='farmer@test.com',
            phone_number='+254712345678',
            password='TestPass123!',
            user_type='farmer'
        )
        
        self.farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-TEST-001',
            full_name='Test Farmer',
            id_number='12345678',
            county='Nakuru',
            sub_county='Nakuru West',
            nearest_town='Nakuru',
            years_farming=5,
            primary_crop='Maize'
        )
        
        coords = [(36.08, -0.303), (36.082, -0.303), (36.082, -0.305), (36.08, -0.305), (36.08, -0.303)]
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_id='FARM-TEST-001',
            boundary=Polygon(coords),
            center_point=Point(36.081, -0.304),
            size_acres=2.4,
            size_hectares=0.97,
            county='Nakuru',
            sub_county='Nakuru West',
            ward='Test Ward'
        )
        
        # Create NDVI history
        for i in range(10):
            NDVIHistory.objects.create(
                farm=self.farm,
                date=(datetime.now() - timedelta(days=i*3)).date(),
                ndvi_value=0.60 + (i * 0.02)  # Increasing trend
            )
        
        self.client.force_authenticate(user=self.user)
    
    def test_get_ndvi_trend(self):
        """Test getting NDVI trend"""
        url = reverse('satellite:ndvi_trend', kwargs={'farm_id': self.farm.farm_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('trend', response.data)
        self.assertIn('data_points', response.data)
        self.assertEqual(len(response.data['data_points']), 10)
    
    def test_ndvi_history_list(self):
        """Test listing NDVI history"""
        url = reverse('satellite:ndvi_history')
        response = self.client.get(url, {'farm_id': self.farm.farm_id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)


class FarmHealthSummaryAPITestCase(APITestCase):
    """Test cases for Farm Health Summary API"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            username='testfarmer',
            email='farmer@test.com',
            phone_number='+254712345678',
            password='TestPass123!',
            user_type='farmer'
        )
        
        self.farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-TEST-001',
            full_name='Test Farmer',
            id_number='12345678',
            county='Nakuru',
            sub_county='Nakuru West',
            nearest_town='Nakuru',
            years_farming=5,
            primary_crop='Maize'
        )
        
        coords = [(36.08, -0.303), (36.082, -0.303), (36.082, -0.305), (36.08, -0.305), (36.08, -0.303)]
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_id='FARM-TEST-001',
            boundary=Polygon(coords),
            center_point=Point(36.081, -0.304),
            size_acres=2.4,
            size_hectares=0.97,
            county='Nakuru',
            sub_county='Nakuru West',
            ward='Test Ward'
        )
        
        # Create scan
        self.scan = SatelliteScan.objects.create(
            scan_id='SCAN-TEST-001',
            farm=self.farm,
            satellite_type='sentinel2',
            acquisition_date=datetime.now(),
            image_url='https://example.com/test.jpg',
            cloud_cover_percentage=10.0,
            ndvi=0.75,
            soil_moisture=65.0,
            crop_health_status='Healthy',
            verified_farm_size=2.35,
            matches_declared_size=True,
            raw_satellite_data={}
        )
        
        # Create NDVI history
        for i in range(5):
            NDVIHistory.objects.create(
                farm=self.farm,
                date=(datetime.now() - timedelta(days=i*7)).date(),
                ndvi_value=0.70 + (i * 0.01)
            )
        
        self.client.force_authenticate(user=self.user)
    
    def test_get_health_summary(self):
        """Test getting farm health summary"""
        url = reverse('satellite:farm_health_summary', kwargs={'farm_id': self.farm.farm_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('latest_scan', response.data)
        self.assertIn('ndvi_trend', response.data)
        self.assertIn('health_score', response.data)
        self.assertIn('recommendations', response.data)
        
        # Health score should be good
        self.assertGreater(response.data['health_score'], 70)