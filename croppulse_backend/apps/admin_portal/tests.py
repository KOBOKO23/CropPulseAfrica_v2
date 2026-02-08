# apps/admin_portal/tests.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from .models import (
    FeatureFlag,
    TenantFeatureFlag,
    GlobalSettings,
    SystemMetrics,
    BankConfiguration,
    SystemAlert
)
from .services import (
    FeatureFlagService,
    GlobalSettingsService,
    SystemMonitor
)

User = get_user_model()


class FeatureFlagServiceTestCase(TestCase):
    """Test cases for Feature Flag Service"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            phone_number='+254700000000',
            password='testpass123'
        )
        
        self.bank_user = User.objects.create_user(
            username='testbank',
            email='bank@test.com',
            phone_number='+254700000001',
            password='testpass123',
            user_type='bank'
        )
        
        self.feature_flag = FeatureFlag.objects.create(
            name='test_feature',
            display_name='Test Feature',
            is_enabled=True,
            category='general',
            rollout_percentage=100
        )
    
    def test_is_feature_enabled_global(self):
        """Test global feature flag check"""
        self.assertTrue(
            FeatureFlagService.is_feature_enabled('test_feature')
        )
    
    def test_is_feature_disabled(self):
        """Test disabled feature flag"""
        self.feature_flag.is_enabled = False
        self.feature_flag.save()
        
        self.assertFalse(
            FeatureFlagService.is_feature_enabled('test_feature')
        )
    
    def test_tenant_override(self):
        """Test tenant-specific override"""
        # Disable globally
        self.feature_flag.is_enabled = False
        self.feature_flag.save()
        
        # Enable for specific tenant
        FeatureFlagService.set_tenant_override(
            'test_feature',
            self.bank_user,
            True
        )
        
        # Check tenant has access
        self.assertTrue(
            FeatureFlagService.is_feature_enabled('test_feature', self.bank_user)
        )
        
        # Check others don't
        self.assertFalse(
            FeatureFlagService.is_feature_enabled('test_feature')
        )
    
    def test_rollout_percentage(self):
        """Test rollout percentage"""
        self.feature_flag.rollout_percentage = 0
        self.feature_flag.save()
        
        # Clear cache
        FeatureFlagService.clear_cache('test_feature')
        
        # Should be disabled for everyone
        self.assertFalse(
            FeatureFlagService.is_feature_enabled('test_feature', self.bank_user)
        )


class GlobalSettingsServiceTestCase(TestCase):
    """Test cases for Global Settings Service"""
    
    def setUp(self):
        """Set up test data"""
        GlobalSettings.objects.create(
            key='test.string',
            value='test_value',
            value_type='string',
            category='system'
        )
        
        GlobalSettings.objects.create(
            key='test.integer',
            value='42',
            value_type='integer',
            category='system'
        )
        
        GlobalSettings.objects.create(
            key='test.boolean',
            value='true',
            value_type='boolean',
            category='system'
        )
    
    def test_get_string_setting(self):
        """Test getting string setting"""
        value = GlobalSettingsService.get_setting('test.string')
        self.assertEqual(value, 'test_value')
    
    def test_get_integer_setting(self):
        """Test getting integer setting"""
        value = GlobalSettingsService.get_setting('test.integer')
        self.assertEqual(value, 42)
    
    def test_get_boolean_setting(self):
        """Test getting boolean setting"""
        value = GlobalSettingsService.get_setting('test.boolean')
        self.assertTrue(value)
    
    def test_get_nonexistent_setting(self):
        """Test getting non-existent setting with default"""
        value = GlobalSettingsService.get_setting('nonexistent', default='default_value')
        self.assertEqual(value, 'default_value')
    
    def test_set_setting(self):
        """Test setting a value"""
        GlobalSettingsService.set_setting(
            'test.new',
            'new_value',
            value_type='string',
            category='system'
        )
        
        value = GlobalSettingsService.get_setting('test.new')
        self.assertEqual(value, 'new_value')
    
    def test_bulk_update(self):
        """Test bulk update of settings"""
        updates = {
            'test.string': 'updated_value',
            'test.integer': '100'
        }
        
        count = GlobalSettingsService.bulk_update_settings(updates)
        self.assertEqual(count, 2)
        
        self.assertEqual(GlobalSettingsService.get_setting('test.string'), 'updated_value')
        self.assertEqual(GlobalSettingsService.get_setting('test.integer'), 100)


class FeatureFlagAPITestCase(TestCase):
    """Test cases for Feature Flag API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            phone_number='+254700000000',
            password='testpass123'
        )
        
        self.feature_flag = FeatureFlag.objects.create(
            name='api_test_feature',
            display_name='API Test Feature',
            is_enabled=True,
            category='general'
        )
        
        # Authenticate
        self.client.force_authenticate(user=self.admin_user)
    
    def test_list_feature_flags(self):
        """Test listing feature flags"""
        response = self.client.get('/api/v1/admin/feature-flags/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_create_feature_flag(self):
        """Test creating a feature flag"""
        data = {
            'name': 'new_feature',
            'display_name': 'New Feature',
            'description': 'A new feature',
            'is_enabled': False,
            'category': 'general',
            'rollout_percentage': 50
        }
        
        response = self.client.post('/api/v1/admin/feature-flags/', data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'new_feature')
    
    def test_toggle_feature_flag(self):
        """Test toggling feature flag"""
        original_status = self.feature_flag.is_enabled
        
        response = self.client.post(f'/api/v1/admin/feature-flags/{self.feature_flag.id}/toggle/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Refresh from database
        self.feature_flag.refresh_from_db()
        self.assertNotEqual(self.feature_flag.is_enabled, original_status)


class SystemMetricsTestCase(TestCase):
    """Test cases for System Metrics"""
    
    def test_collect_metrics(self):
        """Test metrics collection"""
        metrics = SystemMonitor.collect_metrics()
        
        self.assertIsNotNone(metrics)
        self.assertIsInstance(metrics, SystemMetrics)
        self.assertGreaterEqual(metrics.cpu_usage, 0)
        self.assertGreaterEqual(metrics.memory_usage, 0)
    
    def test_get_current_metrics(self):
        """Test getting current metrics"""
        # Collect metrics first
        SystemMonitor.collect_metrics()
        
        current = SystemMonitor.get_current_metrics()
        
        self.assertIsNotNone(current)
        self.assertIsInstance(current, SystemMetrics)
    
    def test_system_health_summary(self):
        """Test system health summary"""
        # Collect metrics first
        SystemMonitor.collect_metrics()
        
        summary = SystemMonitor.get_system_health_summary()
        
        self.assertIn('status', summary)
        self.assertIn('message', summary)
        self.assertIn('services', summary)


class SystemAlertTestCase(TestCase):
    """Test cases for System Alerts"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            phone_number='+254700000000',
            password='testpass123'
        )
        
        self.alert = SystemAlert.objects.create(
            title='Test Alert',
            message='This is a test alert',
            severity='warning',
            category='system',
            source='test'
        )
    
    def test_create_alert(self):
        """Test creating an alert"""
        alert = SystemAlert.objects.create(
            title='New Alert',
            message='New test alert',
            severity='info',
            category='system'
        )
        
        self.assertIsNotNone(alert)
        self.assertFalse(alert.is_resolved)
    
    def test_resolve_alert(self):
        """Test resolving an alert"""
        self.alert.resolve(self.admin_user)
        
        self.assertTrue(self.alert.is_resolved)
        self.assertEqual(self.alert.resolved_by, self.admin_user)
        self.assertIsNotNone(self.alert.resolved_at)
    
    def test_alert_filtering(self):
        """Test filtering alerts"""
        # Create different types of alerts
        SystemAlert.objects.create(
            title='Critical Alert',
            message='Critical',
            severity='critical',
            category='security'
        )
        
        SystemAlert.objects.create(
            title='Info Alert',
            message='Info',
            severity='info',
            category='system'
        )
        
        # Filter by severity
        critical_alerts = SystemAlert.objects.filter(severity='critical')
        self.assertEqual(critical_alerts.count(), 1)
        
        # Filter by unresolved
        unresolved = SystemAlert.objects.filter(is_resolved=False)
        self.assertGreater(unresolved.count(), 0)


class BankConfigurationTestCase(TestCase):
    """Test cases for Bank Configuration"""
    
    def setUp(self):
        """Set up test data"""
        from apps.banks.models import Bank
        
        self.bank_user = User.objects.create_user(
            username='testbank',
            email='bank@test.com',
            phone_number='+254700000001',
            password='testpass123',
            user_type='bank'
        )
        
        self.bank = Bank.objects.create(
            user=self.bank_user,
            name='Test Bank',
            registration_number='TEST123'
        )
    
    def test_create_bank_configuration(self):
        """Test creating bank configuration"""
        from .services import BankManager
        
        config = BankManager.create_bank_configuration(
            self.bank,
            api_rate_limit=2000,
            billing_plan='professional'
        )
        
        self.assertIsNotNone(config)
        self.assertEqual(config.api_rate_limit, 2000)
        self.assertEqual(config.billing_plan, 'professional')
    
    def test_update_billing_plan(self):
        """Test updating billing plan"""
        from .services import BankManager
        
        BankManager.update_billing_plan(self.bank, 'enterprise')
        
        config = BankConfiguration.objects.get(bank=self.bank)
        self.assertEqual(config.billing_plan, 'enterprise')