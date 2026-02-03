# apps/farmers/tests.py

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile
from decimal import Decimal

from apps.accounts.models import User
from .models import Farmer, VoiceRegistration, FarmerNote
from .services import PulseIDGenerator, FarmerProfileService


class PulseIDGeneratorTestCase(TestCase):
    """Test cases for Pulse ID Generator"""
    
    def test_generate_pulse_id(self):
        """Test generating a Pulse ID"""
        pulse_id = PulseIDGenerator.generate('Nakuru')
        
        self.assertTrue(pulse_id.startswith('CP-'))
        self.assertEqual(len(pulse_id), 9)  # CP-XXX-CC
        self.assertTrue(pulse_id.endswith('-NK'))
    
    def test_pulse_id_validation(self):
        """Test Pulse ID validation"""
        valid_id = 'CP-123-NK'
        invalid_id = 'INVALID'
        
        self.assertTrue(PulseIDGenerator.validate(valid_id))
        self.assertFalse(PulseIDGenerator.validate(invalid_id))
    
    def test_parse_pulse_id(self):
        """Test parsing Pulse ID"""
        pulse_id = 'CP-882-NK'
        parsed = PulseIDGenerator.parse(pulse_id)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['prefix'], 'CP')
        self.assertEqual(parsed['number'], '882')
        self.assertEqual(parsed['county_code'], 'NK')
    
    def test_get_county_code(self):
        """Test getting county code"""
        code = PulseIDGenerator.get_county_code('Nakuru')
        self.assertEqual(code, 'NK')
        
        code = PulseIDGenerator.get_county_code('Kiambu')
        self.assertEqual(code, 'KB')


class FarmerModelTestCase(TestCase):
    """Test cases for Farmer model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testfarmer',
            email='farmer@test.com',
            phone_number='+254712345678',
            password='TestPass123!',
            user_type='farmer'
        )
    
    def test_create_farmer(self):
        """Test creating a farmer"""
        farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-123-NA',
            full_name='Test Farmer',
            id_number='12345678',
            county='Nakuru',
            sub_county='Nakuru West',
            nearest_town='Nakuru',
            years_farming=5,
            primary_crop='Maize',
            secondary_crops=['Beans', 'Vegetables']
        )
        
        self.assertEqual(farmer.pulse_id, 'CP-123-NA')
        self.assertEqual(farmer.full_name, 'Test Farmer')
        self.assertEqual(farmer.user, self.user)
        self.assertFalse(farmer.onboarding_completed)
        self.assertTrue(farmer.is_active)
        self.assertEqual(farmer.fraud_status, 'clean')
    
    def test_farmer_str_representation(self):
        """Test farmer string representation"""
        farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-456-KI',
            full_name='John Doe',
            id_number='87654321',
            county='Kiambu',
            sub_county='Kikuyu',
            nearest_town='Kikuyu',
            years_farming=10,
            primary_crop='Coffee'
        )
        
        self.assertEqual(str(farmer), 'John Doe (CP-456-KI)')
    
    def test_get_full_location(self):
        """Test getting full location"""
        farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-789-ME',
            full_name='Location Test',
            id_number='11111111',
            county='Meru',
            sub_county='Imenti North',
            nearest_town='Meru',
            years_farming=3,
            primary_crop='Tea'
        )
        
        location = farmer.get_full_location()
        self.assertEqual(location, 'Meru, Imenti North, Meru')
    
    def test_get_crops_list(self):
        """Test getting crops list"""
        farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-999-NK',
            full_name='Crops Test',
            id_number='22222222',
            county='Nakuru',
            sub_county='Nakuru East',
            nearest_town='Nakuru',
            years_farming=7,
            primary_crop='Maize',
            secondary_crops=['Beans', 'Potatoes']
        )
        
        crops = farmer.get_crops_list()
        self.assertEqual(crops, ['Maize', 'Beans', 'Potatoes'])
    
    def test_is_fraud_flagged(self):
        """Test fraud flagged check"""
        farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-888-NK',
            full_name='Fraud Test',
            id_number='33333333',
            county='Nakuru',
            sub_county='Nakuru West',
            nearest_town='Nakuru',
            years_farming=2,
            primary_crop='Wheat',
            fraud_status='flagged'
        )
        
        self.assertTrue(farmer.is_fraud_flagged())


class FarmerAPITestCase(APITestCase):
    """Test cases for Farmer API"""
    
    def setUp(self):
        """Set up test client"""
        self.client = APIClient()
        
        # Create user
        self.user = User.objects.create_user(
            username='testfarmer',
            email='farmer@test.com',
            phone_number='+254712345678',
            password='TestPass123!',
            user_type='farmer'
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_create_farmer_profile(self):
        """Test creating farmer profile"""
        url = reverse('farmers:farmer_register')
        data = {
            'full_name': 'Samuel Ochieng',
            'id_number': '12345678',
            'county': 'Nakuru',
            'sub_county': 'Nakuru West',
            'nearest_town': 'Nakuru',
            'years_farming': 5,
            'primary_crop': 'Maize',
            'secondary_crops': ['Beans'],
            'latitude': -0.3031,
            'longitude': 36.0800
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('farmer', response.data)
        self.assertIn('pulse_id', response.data['farmer'])
        
        # Verify farmer was created
        farmer = Farmer.objects.get(user=self.user)
        self.assertEqual(farmer.full_name, 'Samuel Ochieng')
        self.assertTrue(farmer.pulse_id.startswith('CP-'))
    
    def test_create_duplicate_farmer_profile(self):
        """Test creating duplicate profile"""
        # Create first profile
        Farmer.objects.create(
            user=self.user,
            pulse_id='CP-111-NA',
            full_name='Existing Farmer',
            id_number='99999999',
            county='Nakuru',
            sub_county='Nakuru West',
            nearest_town='Nakuru',
            years_farming=5,
            primary_crop='Maize'
        )
        
        # Try to create another
        url = reverse('farmers:farmer_register')
        data = {
            'full_name': 'Another Name',
            'id_number': '88888888',
            'county': 'Kiambu',
            'sub_county': 'Kikuyu',
            'nearest_town': 'Kikuyu',
            'years_farming': 3,
            'primary_crop': 'Coffee'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_my_profile(self):
        """Test getting own profile"""
        farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-222-KI',
            full_name='Test Farmer',
            id_number='33333333',
            county='Kiambu',
            sub_county='Kikuyu',
            nearest_town='Kikuyu',
            years_farming=7,
            primary_crop='Tea'
        )
        
        url = reverse('farmers:my_profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['pulse_id'], farmer.pulse_id)
    
    def test_update_farmer_profile(self):
        """Test updating farmer profile"""
        farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-333-ME',
            full_name='Original Name',
            id_number='44444444',
            county='Meru',
            sub_county='Imenti North',
            nearest_town='Meru',
            years_farming=4,
            primary_crop='Coffee'
        )
        
        url = reverse('farmers:farmer_update', kwargs={'pulse_id': farmer.pulse_id})
        data = {
            'full_name': 'Updated Name',
            'primary_crop': 'Tea'
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify update
        farmer.refresh_from_db()
        self.assertEqual(farmer.full_name, 'Updated Name')
        self.assertEqual(farmer.primary_crop, 'Tea')


class FarmerOnboardingTestCase(APITestCase):
    """Test cases for farmer onboarding"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            username='onboardtest',
            email='onboard@test.com',
            phone_number='+254744444444',
            password='TestPass123!',
            user_type='farmer',
            is_verified=True
        )
        
        self.farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-666-NA',
            full_name='Onboarding Test',
            id_number='77777777',
            county='Nakuru',
            sub_county='Nakuru Town',
            nearest_town='Nakuru',
            years_farming=3,
            primary_crop='Maize'
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_get_onboarding_status(self):
        """Test getting onboarding status"""
        url = reverse('farmers:onboarding_status', kwargs={'pulse_id': self.farmer.pulse_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('steps', response.data)
        self.assertIn('percentage', response.data)
        self.assertIn('next_step', response.data)


class FarmerSearchTestCase(APITestCase):
    """Test cases for farmer search"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create admin user
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            phone_number='+254700000000',
            password='AdminPass123!',
            user_type='admin'
        )
        
        # Create test farmers
        for i in range(3):
            user = User.objects.create_user(
                username=f'farmer{i}',
                email=f'farmer{i}@test.com',
                phone_number=f'+25471000000{i}',
                password='TestPass123!',
                user_type='farmer'
            )
            
            Farmer.objects.create(
                user=user,
                pulse_id=f'CP-{100+i}-NA',
                full_name=f'Test Farmer {i}',
                id_number=f'1111111{i}',
                county='Nakuru',
                sub_county='Nakuru West',
                nearest_town='Nakuru',
                years_farming=i+1,
                primary_crop='Maize'
            )
        
        self.client.force_authenticate(user=self.admin_user)
    
    def test_search_farmers(self):
        """Test searching farmers"""
        url = reverse('farmers:search_farmers')
        response = self.client.get(url, {'q': 'Test Farmer'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['count'], 0)
        self.assertIn('results', response.data)
    
    def test_search_by_pulse_id(self):
        """Test searching by pulse ID"""
        url = reverse('farmers:search_farmers')
        response = self.client.get(url, {'q': 'CP-100'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)


class FarmerNoteTestCase(APITestCase):
    """Test cases for farmer notes"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            username='notetest',
            email='note@test.com',
            phone_number='+254755555555',
            password='TestPass123!',
            user_type='bank'
        )
        
        self.farmer_user = User.objects.create_user(
            username='farmeruser',
            email='farmer@test.com',
            phone_number='+254766666666',
            password='TestPass123!',
            user_type='farmer'
        )
        
        self.farmer = Farmer.objects.create(
            user=self.farmer_user,
            pulse_id='CP-777-NK',
            full_name='Note Test Farmer',
            id_number='88888888',
            county='Nakuru',
            sub_county='Nakuru West',
            nearest_town='Nakuru',
            years_farming=4,
            primary_crop='Coffee'
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_create_farmer_note(self):
        """Test creating a farmer note"""
        url = reverse('farmers:farmer_note_create', kwargs={'pulse_id': self.farmer.pulse_id})
        data = {
            'note_type': 'general',
            'content': 'Test note content',
            'is_internal': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('note', response.data)
        
        # Verify note was created
        note = FarmerNote.objects.get(farmer=self.farmer)
        self.assertEqual(note.content, 'Test note content')