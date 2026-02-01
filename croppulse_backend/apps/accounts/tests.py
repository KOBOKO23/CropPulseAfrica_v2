# apps/accounts/tests.py

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from .models import User


class UserModelTestCase(TestCase):
    """Test cases for User model"""
    
    def setUp(self):
        """Set up test data"""
        self.user_data = {
            'username': 'testfarmer',
            'email': 'farmer@test.com',
            'phone_number': '+254712345678',
            'password': 'TestPass123!',
            'user_type': 'farmer'
        }
    
    def test_create_user(self):
        """Test creating a user"""
        user = User.objects.create_user(**self.user_data)
        
        self.assertEqual(user.username, self.user_data['username'])
        self.assertEqual(user.email, self.user_data['email'])
        self.assertEqual(user.phone_number, self.user_data['phone_number'])
        self.assertEqual(user.user_type, self.user_data['user_type'])
        self.assertFalse(user.is_verified)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
    
    def test_create_superuser(self):
        """Test creating a superuser"""
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            phone_number='+254700000000',
            password='AdminPass123!',
            user_type='admin'
        )
        
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
    
    def test_user_str_representation(self):
        """Test user string representation"""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(str(user), user.username)
    
    def test_phone_number_unique(self):
        """Test phone number uniqueness"""
        User.objects.create_user(**self.user_data)
        
        # Try to create another user with same phone
        duplicate_data = self.user_data.copy()
        duplicate_data['username'] = 'different'
        duplicate_data['email'] = 'different@test.com'
        
        with self.assertRaises(Exception):
            User.objects.create_user(**duplicate_data)


class RegistrationAPITestCase(APITestCase):
    """Test cases for user registration API"""
    
    def setUp(self):
        """Set up test client"""
        self.client = APIClient()
        self.register_url = reverse('accounts:register')
        self.valid_data = {
            'username': 'newfarmer',
            'email': 'new@farmer.com',
            'phone_number': '+254798765432',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'first_name': 'John',
            'last_name': 'Doe',
            'user_type': 'farmer'
        }
    
    def test_user_registration_success(self):
        """Test successful user registration"""
        response = self.client.post(self.register_url, self.valid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', response.data)
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])
        
        # Check user was created
        user = User.objects.get(username=self.valid_data['username'])
        self.assertEqual(user.email, self.valid_data['email'])
        self.assertFalse(user.is_verified)
    
    def test_registration_password_mismatch(self):
        """Test registration with password mismatch"""
        data = self.valid_data.copy()
        data['password_confirm'] = 'DifferentPassword123!'
        
        response = self.client.post(self.register_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)
    
    def test_registration_invalid_phone(self):
        """Test registration with invalid phone number"""
        data = self.valid_data.copy()
        data['phone_number'] = '123456'
        
        response = self.client.post(self.register_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone_number', response.data)
    
    def test_registration_duplicate_username(self):
        """Test registration with duplicate username"""
        # Create first user
        User.objects.create_user(
            username='duplicate',
            email='first@test.com',
            phone_number='+254700111111',
            password='Pass123!',
            user_type='farmer'
        )
        
        # Try to register with same username
        data = self.valid_data.copy()
        data['username'] = 'duplicate'
        
        response = self.client.post(self.register_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)
    
    def test_registration_missing_required_fields(self):
        """Test registration with missing required fields"""
        response = self.client.post(self.register_url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)
        self.assertIn('password', response.data)


class LoginAPITestCase(APITestCase):
    """Test cases for login API"""
    
    def setUp(self):
        """Set up test client and user"""
        self.client = APIClient()
        self.login_url = reverse('accounts:login')
        
        # Create test user
        self.user = User.objects.create_user(
            username='loginuser',
            email='login@test.com',
            phone_number='+254722222222',
            password='LoginPass123!',
            user_type='farmer'
        )
    
    def test_login_success(self):
        """Test successful login"""
        response = self.client.post(self.login_url, {
            'username': 'loginuser',
            'password': 'LoginPass123!'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', response.data)
        self.assertIn('user', response.data)
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])
    
    def test_login_wrong_password(self):
        """Test login with wrong password"""
        response = self.client.post(self.login_url, {
            'username': 'loginuser',
            'password': 'WrongPassword!'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_nonexistent_user(self):
        """Test login with non-existent username"""
        response = self.client.post(self.login_url, {
            'username': 'nonexistent',
            'password': 'SomePassword123!'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_inactive_user(self):
        """Test login with inactive user"""
        self.user.is_active = False
        self.user.save()
        
        response = self.client.post(self.login_url, {
            'username': 'loginuser',
            'password': 'LoginPass123!'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserProfileAPITestCase(APITestCase):
    """Test cases for user profile API"""
    
    def setUp(self):
        """Set up authenticated client"""
        self.client = APIClient()
        
        # Create and authenticate user
        self.user = User.objects.create_user(
            username='profileuser',
            email='profile@test.com',
            phone_number='+254733333333',
            password='ProfilePass123!',
            first_name='Profile',
            last_name='User',
            user_type='farmer'
        )
        
        self.client.force_authenticate(user=self.user)
        self.profile_url = reverse('accounts:user_profile')
    
    def test_get_profile(self):
        """Test getting user profile"""
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], self.user.username)
        self.assertEqual(response.data['email'], self.user.email)
    
    def test_update_profile(self):
        """Test updating user profile"""
        response = self.client.patch(self.profile_url, {
            'first_name': 'Updated',
            'last_name': 'Name'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify update
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'Name')
    
    def test_unauthenticated_profile_access(self):
        """Test accessing profile without authentication"""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordChangeAPITestCase(APITestCase):
    """Test cases for password change API"""
    
    def setUp(self):
        """Set up authenticated client"""
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            username='passuser',
            email='pass@test.com',
            phone_number='+254744444444',
            password='OldPass123!',
            user_type='farmer'
        )
        
        self.client.force_authenticate(user=self.user)
        self.password_change_url = reverse('accounts:password_change')
    
    def test_password_change_success(self):
        """Test successful password change"""
        response = self.client.post(self.password_change_url, {
            'old_password': 'OldPass123!',
            'new_password': 'NewPass456!',
            'new_password_confirm': 'NewPass456!'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify password changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass456!'))
    
    def test_password_change_wrong_old_password(self):
        """Test password change with wrong old password"""
        response = self.client.post(self.password_change_url, {
            'old_password': 'WrongOldPass!',
            'new_password': 'NewPass456!',
            'new_password_confirm': 'NewPass456!'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_password_change_mismatch(self):
        """Test password change with mismatched new passwords"""
        response = self.client.post(self.password_change_url, {
            'old_password': 'OldPass123!',
            'new_password': 'NewPass456!',
            'new_password_confirm': 'DifferentPass789!'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PhoneVerificationAPITestCase(APITestCase):
    """Test cases for phone verification API"""
    
    def setUp(self):
        """Set up authenticated client"""
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            username='verifyuser',
            email='verify@test.com',
            phone_number='+254755555555',
            password='VerifyPass123!',
            user_type='farmer'
        )
        
        self.client.force_authenticate(user=self.user)
        self.verify_url = reverse('accounts:verify_phone')
        self.send_code_url = reverse('accounts:send_verification_code')
    
    def test_send_verification_code(self):
        """Test sending verification code"""
        response = self.client.post(self.send_code_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_verify_phone_success(self):
        """Test successful phone verification"""
        response = self.client.post(self.verify_url, {
            'phone_number': self.user.phone_number,
            'verification_code': '123456'  # Test code
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user is marked as verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)
    
    def test_verify_phone_wrong_code(self):
        """Test phone verification with wrong code"""
        response = self.client.post(self.verify_url, {
            'phone_number': self.user.phone_number,
            'verification_code': '999999'
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserStatisticsAPITestCase(APITestCase):
    """Test cases for user statistics API"""
    
    def setUp(self):
        """Set up admin client"""
        self.client = APIClient()
        
        # Create admin user
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            phone_number='+254700000000',
            password='AdminPass123!',
            user_type='admin'
        )
        
        # Create some test users
        User.objects.create_user(
            username='farmer1',
            email='farmer1@test.com',
            phone_number='+254711111111',
            password='Pass123!',
            user_type='farmer',
            is_verified=True
        )
        
        User.objects.create_user(
            username='bank1',
            email='bank1@test.com',
            phone_number='+254722222222',
            password='Pass123!',
            user_type='bank'
        )
        
        self.client.force_authenticate(user=self.admin)
        self.stats_url = reverse('accounts:user_statistics')
    
    def test_get_statistics(self):
        """Test getting user statistics"""
        response = self.client.get(self.stats_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_users', response.data)
        self.assertIn('verified_users', response.data)
        self.assertIn('by_type', response.data)
        
        # Should have 3 users total (admin + 2 test users)
        self.assertEqual(response.data['total_users'], 3)
    
    def test_statistics_non_admin(self):
        """Test accessing statistics as non-admin"""
        # Create regular user
        user = User.objects.create_user(
            username='regular',
            email='regular@test.com',
            phone_number='+254788888888',
            password='Pass123!',
            user_type='farmer'
        )
        
        self.client.force_authenticate(user=user)
        response = self.client.get(self.stats_url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)