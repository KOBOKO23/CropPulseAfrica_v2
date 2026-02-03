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
from .services.cloud_classifier import CloudClassifier
from .services.sar_processor import SARProcessor
from .services.image_cache import ImageCacheService


# ---------------------------------------------------------------------------
# Shared helper — avoids copy-pasting the same setUp across every TestCase
# ---------------------------------------------------------------------------
class BaseSatelliteTestCase(TestCase):
    """Mixin that creates a user, farmer and farm used by most test classes."""

    def _create_base_fixtures(self, username='testfarmer', email='farmer@test.com'):
        self.user = User.objects.create_user(
            username=username,
            email=email,
            phone_number='+254712345678',
            password='TestPass123!',
            user_type='farmer',
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
            primary_crop='Maize',
        )

        coords = [
            (36.0800, -0.3031),
            (36.0820, -0.3031),
            (36.0820, -0.3051),
            (36.0800, -0.3051),
            (36.0800, -0.3031),
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
            ward='Test Ward',
        )


# ===========================================================================
# MODEL TESTS
# ===========================================================================

class SatelliteScanModelTestCase(BaseSatelliteTestCase):
    """Test cases for SatelliteScan model"""

    def setUp(self):
        self._create_base_fixtures()

    def test_create_satellite_scan(self):
        """Test creating a satellite scan with all key fields"""
        scan = SatelliteScan.objects.create(
            scan_id='SCAN-TEST-001',
            farm=self.farm,
            satellite_type='sentinel1',
            acquisition_date=datetime.now(),
            processing_status='completed',
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
            raw_satellite_data={},
        )

        self.assertEqual(scan.scan_id, 'SCAN-TEST-001')
        self.assertEqual(scan.farm, self.farm)
        self.assertEqual(scan.ndvi, 0.75)
        self.assertTrue(scan.matches_declared_size)
        self.assertEqual(scan.processing_status, 'completed')

    def test_scan_string_representation(self):
        """Test scan __str__"""
        scan = SatelliteScan.objects.create(
            scan_id='SCAN-TEST-002',
            farm=self.farm,
            satellite_type='sentinel2',
            acquisition_date=datetime.now(),
            image_url='',
            cloud_cover_percentage=10.0,
            crop_health_status='Healthy',
            verified_farm_size=2.4,
            raw_satellite_data={},
        )

        self.assertIn('SCAN-TEST-002', str(scan))
        self.assertIn(self.farm.farm_id, str(scan))

    def test_failed_scan_with_unknown_health_status(self):
        """'Unknown' is now a valid HEALTH_STATUS choice — used on failure path"""
        scan = SatelliteScan.objects.create(
            scan_id='SCAN-FAIL-001',
            farm=self.farm,
            satellite_type='sentinel1',
            acquisition_date=datetime.now(),
            processing_status='failed',
            processing_error='No satellite data available',
            image_url='',
            cloud_cover_percentage=100,
            crop_health_status='Unknown',
            verified_farm_size=float(self.farm.size_acres),
            raw_satellite_data={'error': 'No satellite data available'},
        )

        self.assertEqual(scan.crop_health_status, 'Unknown')
        self.assertEqual(scan.processing_status, 'failed')

    def test_calculate_size_difference(self):
        """Test size-difference helper"""
        scan = SatelliteScan.objects.create(
            scan_id='SCAN-SIZE-001',
            farm=self.farm,  # declared size = 2.4
            satellite_type='sentinel2',
            acquisition_date=datetime.now(),
            cloud_cover_percentage=10.0,
            crop_health_status='Healthy',
            verified_farm_size=2.76,  # 15 % larger
            raw_satellite_data={},
        )

        diff = scan.calculate_size_difference()
        self.assertAlmostEqual(diff, 15.0, places=1)

    def test_needs_rescan_on_failed_status(self):
        """needs_rescan() returns True when processing_status is 'failed'"""
        scan = SatelliteScan.objects.create(
            scan_id='SCAN-RESCAN-001',
            farm=self.farm,
            satellite_type='sentinel1',
            acquisition_date=datetime.now(),
            processing_status='failed',
            cloud_cover_percentage=100,
            crop_health_status='Unknown',
            verified_farm_size=2.4,
            raw_satellite_data={},
        )

        self.assertTrue(scan.needs_rescan())


class NDVIHistoryModelTestCase(BaseSatelliteTestCase):
    """Test cases for NDVIHistory model"""

    def setUp(self):
        self._create_base_fixtures()

    def test_create_ndvi_history(self):
        """Test creating NDVI history entry"""
        history = NDVIHistory.objects.create(
            farm=self.farm,
            date=datetime.now().date(),
            ndvi_value=0.72,
        )

        self.assertEqual(history.farm, self.farm)
        self.assertEqual(history.ndvi_value, 0.72)

    def test_ndvi_unique_constraint(self):
        """Test NDVI history unique constraint (farm + date)"""
        date = datetime.now().date()

        NDVIHistory.objects.create(farm=self.farm, date=date, ndvi_value=0.70)

        with self.assertRaises(Exception):
            NDVIHistory.objects.create(farm=self.farm, date=date, ndvi_value=0.75)

    def test_get_trend_indicator_improving(self):
        """get_trend_indicator returns 'improving' when diff > 0.05"""
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        NDVIHistory.objects.create(farm=self.farm, date=yesterday, ndvi_value=0.60)
        entry = NDVIHistory.objects.create(farm=self.farm, date=today, ndvi_value=0.70)

        self.assertEqual(entry.get_trend_indicator(), 'improving')

    def test_get_trend_indicator_declining(self):
        """get_trend_indicator returns 'declining' when diff < -0.05"""
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        NDVIHistory.objects.create(farm=self.farm, date=yesterday, ndvi_value=0.70)
        entry = NDVIHistory.objects.create(farm=self.farm, date=today, ndvi_value=0.60)

        self.assertEqual(entry.get_trend_indicator(), 'declining')

    def test_get_trend_indicator_stable(self):
        """get_trend_indicator returns 'stable' when |diff| <= 0.05"""
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        NDVIHistory.objects.create(farm=self.farm, date=yesterday, ndvi_value=0.65)
        entry = NDVIHistory.objects.create(farm=self.farm, date=today, ndvi_value=0.67)

        self.assertEqual(entry.get_trend_indicator(), 'stable')

    def test_context_fields_saved(self):
        """All context fields (evi, savi, soil_moisture, temp, rainfall) round-trip"""
        entry = NDVIHistory.objects.create(
            farm=self.farm,
            date=datetime.now().date(),
            ndvi_value=0.70,
            evi_value=0.55,
            savi_value=0.60,
            soil_moisture=45.0,
            temperature=24.5,
            rainfall_mm=12.3,
        )

        entry.refresh_from_db()
        self.assertEqual(entry.evi_value, 0.55)
        self.assertEqual(entry.savi_value, 0.60)
        self.assertEqual(entry.soil_moisture, 45.0)
        self.assertEqual(entry.temperature, 24.5)
        self.assertEqual(entry.rainfall_mm, 12.3)


# ===========================================================================
# SERVICE TESTS — NDVICalculator
# ===========================================================================

class NDVICalculatorTestCase(TestCase):
    """Test cases for NDVI Calculator service"""

    def setUp(self):
        self.calculator = NDVICalculator()

    def test_interpret_excellent_ndvi(self):
        result = self.calculator.interpret_ndvi(0.80)
        self.assertEqual(result['status'], 'Healthy')
        self.assertEqual(result['category'], 'excellent')
        self.assertIn('Excellent', result['description'])

    def test_interpret_good_ndvi(self):
        result = self.calculator.interpret_ndvi(0.65)
        self.assertEqual(result['status'], 'Healthy')
        self.assertEqual(result['category'], 'good')

    def test_interpret_moderate_ndvi(self):
        result = self.calculator.interpret_ndvi(0.50)
        self.assertEqual(result['status'], 'Stressed')
        self.assertEqual(result['category'], 'moderate')

    def test_interpret_poor_ndvi(self):
        result = self.calculator.interpret_ndvi(0.25)
        self.assertEqual(result['status'], 'Stressed')
        self.assertEqual(result['category'], 'poor')

    def test_interpret_critical_ndvi(self):
        result = self.calculator.interpret_ndvi(0.10)
        self.assertEqual(result['status'], 'Poor')
        self.assertEqual(result['category'], 'critical')

    def test_interpret_none_ndvi(self):
        result = self.calculator.interpret_ndvi(None)
        self.assertEqual(result['category'], 'no_data')

    def test_compare_with_maize_baseline_optimal(self):
        result = self.calculator.compare_with_crop_baseline(0.70, 'maize')
        self.assertEqual(result['crop_type'], 'maize')
        self.assertEqual(result['performance'], 'optimal')
        self.assertIn('healthy_range', result)

    def test_compare_with_maize_baseline_concerning(self):
        result = self.calculator.compare_with_crop_baseline(0.30, 'maize')
        self.assertEqual(result['performance'], 'concerning')

    def test_compare_with_unknown_crop_defaults_to_maize(self):
        result = self.calculator.compare_with_crop_baseline(0.70, 'unknown_crop')
        # Should use maize ranges as default
        self.assertEqual(result['healthy_range']['min'], 0.65)

    def test_generate_health_score_high(self):
        score = self.calculator.generate_health_score(
            ndvi_value=0.75,
            soil_moisture=60,
            rainfall_data=120,
        )
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        self.assertGreater(score, 80)

    def test_generate_health_score_low(self):
        score = self.calculator.generate_health_score(
            ndvi_value=0.10,
            soil_moisture=10,
            rainfall_data=5,
        )
        self.assertLess(score, 50)

    def test_generate_health_score_no_optional_data(self):
        """When soil_moisture and rainfall are None, defaults are applied"""
        score = self.calculator.generate_health_score(ndvi_value=0.75)
        # 60 (ndvi) + 15 (default moisture) + 10 (default rain) = 85
        self.assertEqual(score, 85)

    def test_get_seasonal_baseline_maize_peak(self):
        result = self.calculator.get_seasonal_baseline(month=4, crop_type='maize')
        self.assertEqual(result['season'], 'peak_growth')
        self.assertEqual(result['expected_range']['min'], 0.65)

    def test_get_seasonal_baseline_perennial(self):
        result = self.calculator.get_seasonal_baseline(month=6, crop_type='coffee')
        self.assertEqual(result['season'], 'year_round')


# ===========================================================================
# SERVICE TESTS — CloudClassifier
# ===========================================================================

class CloudClassifierTestCase(TestCase):
    """Test cases for CloudClassifier service"""

    def setUp(self):
        self.classifier = CloudClassifier()

    # --- classify_cloud_coverage ---

    def test_classify_clear(self):
        result = self.classifier.classify_cloud_coverage(5)
        self.assertEqual(result['category'], 'clear')
        self.assertEqual(result['quality'], 'excellent')
        self.assertFalse(result['use_sar'])

    def test_classify_partly_cloudy(self):
        result = self.classifier.classify_cloud_coverage(20)
        self.assertEqual(result['category'], 'partly_cloudy')
        self.assertEqual(result['quality'], 'good')
        self.assertTrue(result['use_sar'])

    def test_classify_mostly_cloudy(self):
        result = self.classifier.classify_cloud_coverage(50)
        self.assertEqual(result['category'], 'mostly_cloudy')
        self.assertEqual(result['quality'], 'fair')

    def test_classify_overcast(self):
        result = self.classifier.classify_cloud_coverage(80)
        self.assertEqual(result['category'], 'overcast')
        self.assertEqual(result['quality'], 'poor')

    def test_classify_completely_overcast(self):
        result = self.classifier.classify_cloud_coverage(95)
        self.assertEqual(result['category'], 'completely_overcast')
        self.assertEqual(result['quality'], 'very_poor')

    # --- boundary values ---

    def test_classify_boundary_at_clear_threshold(self):
        """Exactly at CLEAR threshold (10) → partly_cloudy"""
        result = self.classifier.classify_cloud_coverage(10)
        self.assertEqual(result['category'], 'partly_cloudy')

    def test_classify_boundary_just_below_clear(self):
        result = self.classifier.classify_cloud_coverage(9.9)
        self.assertEqual(result['category'], 'clear')

    # --- recommend_satellite_type ---

    def test_recommend_optical_when_clear(self):
        result = self.classifier.recommend_satellite_type(15, urgency='normal')
        self.assertEqual(result['primary_satellite'], 'sentinel2')
        self.assertEqual(result['backup_satellite'], 'sentinel1')

    def test_recommend_sar_when_cloudy(self):
        result = self.classifier.recommend_satellite_type(60, urgency='normal')
        self.assertEqual(result['primary_satellite'], 'sentinel1')

    def test_recommend_wait_when_low_urgency_and_mostly_cloudy(self):
        result = self.classifier.recommend_satellite_type(50, urgency='low')
        # 50 >= MOSTLY_CLOUDY(70)? No → falls into the "mostly_cloudy and low" branch
        # Actually 50 < 70 so it hits the second elif (< MOSTLY_CLOUDY and low urgency)
        self.assertEqual(result['primary_satellite'], 'sentinel2')

    def test_recommend_sar_forced_when_high_urgency_and_cloudy(self):
        result = self.classifier.recommend_satellite_type(75, urgency='high')
        self.assertEqual(result['primary_satellite'], 'sentinel1')
        self.assertFalse(result['wait_recommended'])

    # --- _estimate_wait_time ---

    def test_estimate_wait_time_clear(self):
        self.assertEqual(self.classifier._estimate_wait_time(5), 0)

    def test_estimate_wait_time_overcast(self):
        self.assertEqual(self.classifier._estimate_wait_time(85), 5)

    def test_estimate_wait_time_completely_overcast(self):
        self.assertEqual(self.classifier._estimate_wait_time(95), 7)

    # --- predict_optimal_scan_window ---

    def test_predict_optimal_scan_window_empty_data(self):
        result = self.classifier.predict_optimal_scan_window([])
        self.assertEqual(result['optimal_months'], [])
        self.assertIn('Insufficient', result['message'])

    def test_predict_optimal_scan_window_with_data(self):
        from datetime import date
        data = [
            {'date': date(2024, 1, 15), 'cloud_percentage': 10},
            {'date': date(2024, 1, 20), 'cloud_percentage': 12},
            {'date': date(2024, 6, 10), 'cloud_percentage': 80},
            {'date': date(2024, 6, 15), 'cloud_percentage': 75},
        ]
        result = self.classifier.predict_optimal_scan_window(data)
        self.assertIn('January', result['optimal_months'])
        self.assertNotIn('June', result['optimal_months'])

    # --- assess_scan_quality ---

    def test_assess_scan_quality_excellent(self):
        result = self.classifier.assess_scan_quality(5, clear_pixel_percentage=95)
        self.assertEqual(result['quality_level'], 'excellent')
        self.assertTrue(result['usable'])

    def test_assess_scan_quality_poor(self):
        result = self.classifier.assess_scan_quality(90, clear_pixel_percentage=20)
        self.assertEqual(result['quality_level'], 'poor')
        self.assertFalse(result['usable'])

    def test_assess_scan_quality_no_clear_pixel_data(self):
        """When clear_pixel_percentage is None, only cloud_cover drives score"""
        result = self.classifier.assess_scan_quality(5)
        self.assertTrue(result['usable'])


# ===========================================================================
# SERVICE TESTS — SARProcessor
# ===========================================================================

class SARProcessorTestCase(TestCase):
    """Test cases for SARProcessor service"""

    def setUp(self):
        self.processor = SARProcessor()

    # --- process_sar_backscatter ---

    def test_process_valid_backscatter(self):
        result = self.processor.process_sar_backscatter(-15, -10)
        self.assertTrue(result['valid'])
        self.assertEqual(result['vh_backscatter'], -15)
        self.assertEqual(result['vv_backscatter'], -10)
        self.assertIn('soil_moisture_estimate', result)
        self.assertIn('crop_likelihood', result)
        self.assertIn('surface_roughness', result)

    def test_process_missing_backscatter(self):
        result = self.processor.process_sar_backscatter(None, -10)
        self.assertFalse(result['valid'])

        result2 = self.processor.process_sar_backscatter(-15, None)
        self.assertFalse(result2['valid'])

    def test_vh_vv_ratio_zero_vv(self):
        """Division by zero guard when vv_value == 0"""
        result = self.processor.process_sar_backscatter(-15, 0)
        self.assertTrue(result['valid'])
        self.assertEqual(result['vh_vv_ratio'], 0)

    # --- estimate_soil_moisture_from_vh ---

    def test_soil_moisture_dry(self):
        moisture = self.processor.estimate_soil_moisture_from_vh(-25)
        self.assertEqual(moisture, 0.0)

    def test_soil_moisture_wet(self):
        moisture = self.processor.estimate_soil_moisture_from_vh(-5)
        self.assertEqual(moisture, 100.0)

    def test_soil_moisture_mid(self):
        moisture = self.processor.estimate_soil_moisture_from_vh(-15)
        self.assertEqual(moisture, 50.0)

    def test_soil_moisture_clamped_below(self):
        """Values below -25 dB should clamp to 0 %"""
        moisture = self.processor.estimate_soil_moisture_from_vh(-30)
        self.assertEqual(moisture, 0.0)

    def test_soil_moisture_clamped_above(self):
        """Values above -5 dB should clamp to 100 %"""
        moisture = self.processor.estimate_soil_moisture_from_vh(0)
        self.assertEqual(moisture, 100.0)

    def test_soil_moisture_none(self):
        self.assertIsNone(self.processor.estimate_soil_moisture_from_vh(None))

    # --- detect_flooding ---

    def test_flooding_high(self):
        result = self.processor.detect_flooding(-26, -21)
        self.assertEqual(result['flooding_likelihood'], 'high')
        self.assertGreater(result['confidence'], 0.8)

    def test_flooding_low(self):
        result = self.processor.detect_flooding(-10, -10)
        self.assertEqual(result['flooding_likelihood'], 'low')

    # --- calculate_biomass_estimate ---

    def test_biomass_high(self):
        result = self.processor.calculate_biomass_estimate(-10, -12)
        self.assertEqual(result['category'], 'high')

    def test_biomass_very_low(self):
        result = self.processor.calculate_biomass_estimate(-22, -20)
        self.assertEqual(result['category'], 'very_low')

    # --- apply_speckle_filter ---

    def test_speckle_filter_basic(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        filtered = self.processor.apply_speckle_filter(values, window_size=3)
        self.assertEqual(len(filtered), len(values))
        # Middle values should be smoothed
        self.assertAlmostEqual(filtered[3], 4.0, places=1)

    def test_speckle_filter_short_input(self):
        """Input shorter than window_size returns input unchanged"""
        values = [1.0, 2.0]
        filtered = self.processor.apply_speckle_filter(values, window_size=5)
        self.assertEqual(filtered, values)

    # --- generate_sar_quality_score ---

    def test_sar_quality_good(self):
        result = self.processor.generate_sar_quality_score(-15, -10, 'Descending')
        self.assertGreaterEqual(result['quality_score'], 70)
        self.assertTrue(result['usable'])

    def test_sar_quality_out_of_range(self):
        result = self.processor.generate_sar_quality_score(-35, -35, 'Ascending')
        self.assertIn('VH backscatter out of typical range', result['issues'])
        self.assertIn('VV backscatter out of typical range', result['issues'])

    def test_sar_quality_saturation(self):
        result = self.processor.generate_sar_quality_score(-2, -1)
        self.assertIn('Possible saturation detected', result['issues'])

    # --- detect_surface_roughness ---

    def test_surface_roughness_categories(self):
        self.assertEqual(self.processor.detect_surface_roughness(-5, -8), 'very_rough')
        self.assertEqual(self.processor.detect_surface_roughness(-10, -12), 'rough')
        self.assertEqual(self.processor.detect_surface_roughness(-15, -16), 'moderate')
        self.assertEqual(self.processor.detect_surface_roughness(-20, -20), 'smooth')


# ===========================================================================
# SERVICE TESTS — ImageCacheService
# ===========================================================================

class ImageCacheServiceTestCase(TestCase):
    """Test cases for ImageCacheService — uses Django's default test cache backend"""

    def setUp(self):
        self.cache_service = ImageCacheService()

    # --- generate_cache_key ---

    def test_cache_key_deterministic(self):
        key1 = self.cache_service.generate_cache_key('scan_result', 'FARM-001')
        key2 = self.cache_service.generate_cache_key('scan_result', 'FARM-001')
        self.assertEqual(key1, key2)

    def test_cache_key_different_prefix(self):
        key1 = self.cache_service.generate_cache_key('scan_result', 'FARM-001')
        key2 = self.cache_service.generate_cache_key('ndvi_history', 'FARM-001')
        self.assertNotEqual(key1, key2)

    def test_cache_key_different_args(self):
        key1 = self.cache_service.generate_cache_key('scan_result', 'FARM-001')
        key2 = self.cache_service.generate_cache_key('scan_result', 'FARM-002')
        self.assertNotEqual(key1, key2)

    # --- scan result round-trip ---

    def test_cache_and_retrieve_scan_result(self):
        data = {'scan_id': 'SCAN-001', 'ndvi': 0.72}
        self.assertTrue(self.cache_service.cache_scan_result('FARM-001', data))

        retrieved = self.cache_service.get_cached_scan_result('FARM-001')
        self.assertEqual(retrieved, data)

    def test_get_missing_scan_result_returns_none(self):
        self.assertIsNone(self.cache_service.get_cached_scan_result('FARM-MISSING'))

    # --- image URL round-trip ---

    def test_cache_and_retrieve_image_url(self):
        url = 'https://example.com/tile.png'
        self.assertTrue(
            self.cache_service.cache_image_url('FARM-001', '2024-06-01', url, 'sentinel2')
        )

        retrieved = self.cache_service.get_cached_image_url('FARM-001', '2024-06-01', 'sentinel2')
        self.assertEqual(retrieved, url)

    def test_get_missing_image_url_returns_none(self):
        self.assertIsNone(
            self.cache_service.get_cached_image_url('FARM-MISSING', '2024-01-01')
        )

    # --- NDVI history round-trip ---

    def test_cache_and_retrieve_ndvi_history(self):
        history = [{'date': '2024-06-01', 'ndvi': 0.65}]
        self.assertTrue(self.cache_service.cache_ndvi_history('FARM-001', history))

        retrieved = self.cache_service.get_cached_ndvi_history('FARM-001')
        self.assertEqual(retrieved, history)

    # --- farm health round-trip ---

    def test_cache_and_retrieve_farm_health(self):
        health = {'score': 82, 'status': 'Healthy'}
        self.assertTrue(self.cache_service.cache_farm_health_summary('FARM-001', health))

        retrieved = self.cache_service.get_cached_farm_health_summary('FARM-001')
        self.assertEqual(retrieved, health)

    # --- GEE computation round-trip ---

    def test_cache_and_retrieve_gee_computation(self):
        result = {'ndvi': 0.78, 'cloud_cover': 5}
        self.assertTrue(self.cache_service.cache_gee_computation('comp-abc-123', result))

        retrieved = self.cache_service.get_cached_gee_computation('comp-abc-123')
        self.assertEqual(retrieved, result)

    # --- invalidate_farm_cache ---

    def test_invalidate_farm_cache(self):
        self.cache_service.cache_scan_result('FARM-INV', {'x': 1})
        self.cache_service.cache_ndvi_history('FARM-INV', [{'y': 2}])

        self.assertTrue(self.cache_service.invalidate_farm_cache('FARM-INV'))

        self.assertIsNone(self.cache_service.get_cached_scan_result('FARM-INV'))
        self.assertIsNone(self.cache_service.get_cached_ndvi_history('FARM-INV'))

    # --- get_cache_stats ---

    def test_get_cache_stats_returns_timeouts(self):
        stats = self.cache_service.get_cache_stats()
        self.assertIn('scan_result_timeout', stats)
        self.assertIn('image_url_timeout', stats)
        self.assertIn('ndvi_history_timeout', stats)
        self.assertIn('farm_health_timeout', stats)


# ===========================================================================
# API TESTS — Satellite Scans
# ===========================================================================

class SatelliteScanAPITestCase(BaseSatelliteTestCase, APITestCase):
    """Test cases for Satellite Scan API"""

    def setUp(self):
        self.client = APIClient()
        self._create_base_fixtures()

        # Create sample scan
        self.scan = SatelliteScan.objects.create(
            scan_id='SCAN-TEST-001',
            farm=self.farm,
            satellite_type='sentinel2',
            acquisition_date=datetime.now(),
            processing_status='completed',
            image_url='https://example.com/test.jpg',
            cloud_cover_percentage=15.0,
            ndvi=0.75,
            crop_health_status='Healthy',
            verified_farm_size=2.35,
            matches_declared_size=True,
            raw_satellite_data={},
        )

        self.client.force_authenticate(user=self.user)

    def test_list_satellite_scans(self):
        url = reverse('satellite:scan_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_list_includes_new_fields(self):
        """SatelliteScanSerializer now exposes processing_status etc."""
        url = reverse('satellite:scan_list')
        response = self.client.get(url)

        scan_data = response.data['results'][0]
        self.assertIn('processing_status', scan_data)
        self.assertIn('data_quality_score', scan_data)
        self.assertIn('vh_backscatter', scan_data)
        self.assertIn('size_difference_percentage', scan_data)

    def test_get_scan_detail(self):
        url = reverse('satellite:scan_detail', kwargs={'scan_id': self.scan.scan_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scan_id'], self.scan.scan_id)
        self.assertIn('vegetation_indices', response.data)
        # Detail serializer now includes ndwi and msavi keys
        self.assertIn('ndwi', response.data['vegetation_indices'])
        self.assertIn('msavi', response.data['vegetation_indices'])
        # SAR metrics block present
        self.assertIn('sar_metrics', response.data)

    def test_get_farm_latest_scan(self):
        url = reverse('satellite:farm_latest_scan', kwargs={'farm_id': self.farm.farm_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scan_id'], self.scan.scan_id)

    @patch('apps.satellite.tasks.process_satellite_scan.delay')
    def test_trigger_satellite_scan(self, mock_task):
        mock_task.return_value = MagicMock(id='test-task-id')

        url = reverse('satellite:trigger_scan')
        response = self.client.post(url, {'farm_id': self.farm.farm_id})

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('task_id', response.data['data'])

    def test_unauthorized_access(self):
        other_user = User.objects.create_user(
            username='otherfarmer',
            email='other@test.com',
            phone_number='+254722222222',
            password='TestPass123!',
            user_type='farmer',
        )

        self.client.force_authenticate(user=other_user)

        url = reverse('satellite:scan_detail', kwargs={'scan_id': self.scan.scan_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ===========================================================================
# API TESTS — NDVI Trends
# ===========================================================================

class NDVITrendAPITestCase(BaseSatelliteTestCase, APITestCase):
    """Test cases for NDVI Trend API"""

    def setUp(self):
        self.client = APIClient()
        self._create_base_fixtures()

        # Create NDVI history — increasing trend
        for i in range(10):
            NDVIHistory.objects.create(
                farm=self.farm,
                date=(datetime.now() - timedelta(days=i * 3)).date(),
                ndvi_value=0.60 + (i * 0.02),
            )

        self.client.force_authenticate(user=self.user)

    def test_get_ndvi_trend(self):
        url = reverse('satellite:ndvi_trend', kwargs={'farm_id': self.farm.farm_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('trend', response.data)
        self.assertIn('data_points', response.data)
        self.assertEqual(len(response.data['data_points']), 10)

    def test_ndvi_history_list(self):
        url = reverse('satellite:ndvi_history')
        response = self.client.get(url, {'farm_id': self.farm.farm_id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)
        # New context fields present in response
        first = response.data['results'][0]
        self.assertIn('evi_value', first)
        self.assertIn('soil_moisture', first)
        self.assertIn('temperature', first)
        self.assertIn('rainfall_mm', first)
        self.assertIn('trend_indicator', first)


# ===========================================================================
# API TESTS — Farm Health Summary
# ===========================================================================

class FarmHealthSummaryAPITestCase(BaseSatelliteTestCase, APITestCase):
    """Test cases for Farm Health Summary API"""

    def setUp(self):
        self.client = APIClient()
        self._create_base_fixtures()

        self.scan = SatelliteScan.objects.create(
            scan_id='SCAN-TEST-001',
            farm=self.farm,
            satellite_type='sentinel2',
            acquisition_date=datetime.now(),
            processing_status='completed',
            image_url='https://example.com/test.jpg',
            cloud_cover_percentage=10.0,
            ndvi=0.75,
            soil_moisture=65.0,
            crop_health_status='Healthy',
            verified_farm_size=2.35,
            matches_declared_size=True,
            raw_satellite_data={},
        )

        for i in range(5):
            NDVIHistory.objects.create(
                farm=self.farm,
                date=(datetime.now() - timedelta(days=i * 7)).date(),
                ndvi_value=0.70 + (i * 0.01),
            )

        self.client.force_authenticate(user=self.user)

    def test_get_health_summary(self):
        url = reverse('satellite:farm_health_summary', kwargs={'farm_id': self.farm.farm_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('latest_scan', response.data)
        self.assertIn('ndvi_trend', response.data)
        self.assertIn('health_score', response.data)
        self.assertIn('recommendations', response.data)

        # Health score should be good with these values
        self.assertGreater(response.data['health_score'], 70)

    def test_health_summary_response_goes_through_serializer(self):
        """Verify the response contains all FarmHealthSummarySerializer fields"""
        url = reverse('satellite:farm_health_summary', kwargs={'farm_id': self.farm.farm_id})
        response = self.client.get(url)

        self.assertIn('farm_id', response.data)
        self.assertIn('latest_scan', response.data)
        self.assertIn('ndvi_trend', response.data)
        self.assertIn('health_score', response.data)
        self.assertIn('recommendations', response.data)
        self.assertIn('last_updated', response.data)