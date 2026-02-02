# apps/farms/tests.py

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.measure import D

from apps.accounts.models import User
from apps.farmers.models import Farmer
from .models import Farm, FarmBoundaryPoint


class FarmModelTestCase(TestCase):
    """Test cases for Farm model"""
    
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
            pulse_id='CP-123-NA',
            full_name='Test Farmer',
            id_number='12345678',
            county='Nakuru',
            sub_county='Nakuru West',
            nearest_town='Nakuru',
            years_farming=5,
            primary_crop='Maize'
        )
    
    def test_create_farm_with_polygon(self):
        """Test creating a farm with polygon boundary"""
        # Create polygon coordinates
        coords = [
            (36.0800, -0.3031),
            (36.0820, -0.3031),
            (36.0820, -0.3051),
            (36.0800, -0.3051),
            (36.0800, -0.3031)
        ]
        
        boundary = Polygon(coords)
        center_point = Point(36.0810, -0.3041)
        
        farm = Farm.objects.create(
            farmer=self.farmer,
            farm_id='FARM-123-01',
            boundary=boundary,
            center_point=center_point,
            size_acres=2.47,
            size_hectares=1.00,
            county='Nakuru',
            sub_county='Nakuru West',
            ward='Flamingo'
        )
        
        self.assertEqual(farm.farm_id, 'FARM-123-01')
        self.assertEqual(farm.farmer, self.farmer)
        self.assertIsNotNone(farm.boundary)
        self.assertIsNotNone(farm.center_point)
        self.assertTrue(farm.is_primary)
        self.assertFalse(farm.satellite_verified)
    
    def test_farm_area_calculation(self):
        """Test that farm area is correctly set"""
        coords = [
            (36.0800, -0.3031),
            (36.0820, -0.3031),
            (36.0820, -0.3051),
            (36.0800, -0.3051),
            (36.0800, -0.3031)
        ]
        
        boundary = Polygon(coords)
        
        # Calculate expected area
        area_sq_meters = boundary.area
        expected_acres = area_sq_meters / 4046.86
        expected_hectares = area_sq_meters / 10000
        
        farm = Farm.objects.create(
            farmer=self.farmer,
            farm_id='FARM-123-02',
            boundary=boundary,
            center_point=boundary.centroid,
            size_acres=round(expected_acres, 2),
            size_hectares=round(expected_hectares, 2),
            county='Nakuru',
            sub_county='Nakuru West',
            ward='Test Ward'
        )
        
        self.assertAlmostEqual(float(farm.size_acres), expected_acres, places=2)
        self.assertAlmostEqual(float(farm.size_hectares), expected_hectares, places=2)
    
    def test_farm_center_point(self):
        """Test center point calculation"""
        coords = [
            (36.0800, -0.3031),
            (36.0820, -0.3031),
            (36.0820, -0.3051),
            (36.0800, -0.3051),
            (36.0800, -0.3031)
        ]
        
        boundary = Polygon(coords)
        center = boundary.centroid
        
        farm = Farm.objects.create(
            farmer=self.farmer,
            farm_id='FARM-123-03',
            boundary=boundary,
            center_point=center,
            size_acres=2.0,
            size_hectares=0.81,
            county='Nakuru',
            sub_county='Nakuru West',
            ward='Test Ward'
        )
        
        # Check center point is within boundary
        self.assertTrue(boundary.contains(farm.center_point))
    
    def test_multiple_farms_per_farmer(self):
        """Test farmer can have multiple farms"""
        coords1 = [
            (36.0800, -0.3031),
            (36.0820, -0.3031),
            (36.0820, -0.3051),
            (36.0800, -0.3051),
            (36.0800, -0.3031)
        ]
        
        coords2 = [
            (36.0900, -0.3100),
            (36.0920, -0.3100),
            (36.0920, -0.3120),
            (36.0900, -0.3120),
            (36.0900, -0.3100)
        ]
        
        farm1 = Farm.objects.create(
            farmer=self.farmer,
            farm_id='FARM-123-04',
            boundary=Polygon(coords1),
            center_point=Polygon(coords1).centroid,
            size_acres=2.0,
            size_hectares=0.81,
            county='Nakuru',
            sub_county='Nakuru West',
            ward='Ward 1',
            is_primary=True
        )
        
        farm2 = Farm.objects.create(
            farmer=self.farmer,
            farm_id='FARM-123-05',
            boundary=Polygon(coords2),
            center_point=Polygon(coords2).centroid,
            size_acres=1.5,
            size_hectares=0.61,
            county='Nakuru',
            sub_county='Nakuru East',
            ward='Ward 2',
            is_primary=False
        )
        
        self.assertEqual(self.farmer.farms.count(), 2)
        self.assertEqual(Farm.objects.filter(farmer=self.farmer, is_primary=True).count(), 1)


class FarmBoundaryPointModelTestCase(TestCase):
    """Test cases for FarmBoundaryPoint model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testfarmer',
            email='farmer@test.com',
            phone_number='+254712345678',
            password='TestPass123!',
            user_type='farmer'
        )
        
        self.farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-456-KI',
            full_name='Test Farmer',
            id_number='87654321',
            county='Kiambu',
            sub_county='Kikuyu',
            nearest_town='Kikuyu',
            years_farming=3,
            primary_crop='Coffee'
        )
        
        coords = [
            (36.0800, -0.3031),
            (36.0820, -0.3031),
            (36.0820, -0.3051),
            (36.0800, -0.3051),
            (36.0800, -0.3031)
        ]
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_id='FARM-456-10',
            boundary=Polygon(coords),
            center_point=Polygon(coords).centroid,
            size_acres=2.5,
            size_hectares=1.01,
            county='Kiambu',
            sub_county='Kikuyu',
            ward='Test Ward'
        )
    
    def test_create_boundary_points(self):
        """Test creating boundary points"""
        points_data = [
            (36.0800, -0.3031),
            (36.0820, -0.3031),
            (36.0820, -0.3051),
            (36.0800, -0.3051)
        ]
        
        for i, (lng, lat) in enumerate(points_data):
            FarmBoundaryPoint.objects.create(
                farm=self.farm,
                point=Point(lng, lat),
                sequence=i
            )
        
        self.assertEqual(self.farm.boundary_points.count(), 4)
    
    def test_boundary_points_ordering(self):
        """Test boundary points are ordered by sequence"""
        points_data = [
            (36.0800, -0.3031, 0),
            (36.0820, -0.3031, 1),
            (36.0820, -0.3051, 2),
            (36.0800, -0.3051, 3)
        ]
        
        for lng, lat, seq in points_data:
            FarmBoundaryPoint.objects.create(
                farm=self.farm,
                point=Point(lng, lat),
                sequence=seq
            )
        
        ordered_points = self.farm.boundary_points.all()
        
        for i, point in enumerate(ordered_points):
            self.assertEqual(point.sequence, i)


class FarmAPITestCase(APITestCase):
    """Test cases for Farm API"""
    
    def setUp(self):
        """Set up test client"""
        self.client = APIClient()
        
        # Create user
        self.user = User.objects.create_user(
            username='testfarmer',
            email='farmer@test.com',
            phone_number='+254712345678',
            password='TestPass123!',
            user_type='farmer',
            is_verified=True
        )
        
        # Create farmer
        self.farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-789-ME',
            full_name='Test Farmer',
            id_number='11111111',
            county='Meru',
            sub_county='Imenti North',
            nearest_town='Meru',
            years_farming=4,
            primary_crop='Tea'
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_create_farm(self):
        """Test creating a farm via API"""
        url = reverse('farms:farm_create')
        data = {
            'farmer': self.farmer.id,
            'county': 'Meru',
            'sub_county': 'Imenti North',
            'ward': 'Abothuguchi Central',
            'elevation': 1650,
            'boundary_points': [
                {'lat': -0.0500, 'lng': 37.6500},
                {'lat': -0.0500, 'lng': 37.6520},
                {'lat': -0.0520, 'lng': 37.6520},
                {'lat': -0.0520, 'lng': 37.6500}
            ],
            'is_primary': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('farm', response.data)
        self.assertIn('farm_id', response.data['farm'])
        
        # Verify farm was created
        farm = Farm.objects.get(farmer=self.farmer)
        self.assertTrue(farm.farm_id.startswith('FARM-789-'))
        self.assertEqual(farm.county, 'Meru')
        self.assertEqual(farm.boundary_points.count(), 4)
    
    def test_create_farm_invalid_coordinates(self):
        """Test creating farm with invalid coordinates"""
        url = reverse('farms:farm_create')
        data = {
            'farmer': self.farmer.id,
            'county': 'Meru',
            'sub_county': 'Imenti North',
            'ward': 'Test Ward',
            'boundary_points': [
                {'lat': 100, 'lng': 200},  # Invalid
                {'lat': -0.0500, 'lng': 37.6520},
                {'lat': -0.0520, 'lng': 37.6520}
            ]
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_farm_too_few_points(self):
        """Test creating farm with too few boundary points"""
        url = reverse('farms:farm_create')
        data = {
            'farmer': self.farmer.id,
            'county': 'Meru',
            'sub_county': 'Imenti North',
            'ward': 'Test Ward',
            'boundary_points': [
                {'lat': -0.0500, 'lng': 37.6500},
                {'lat': -0.0500, 'lng': 37.6520}
            ]  # Only 2 points, need at least 3
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_list_farms(self):
        """Test listing farms"""
        # Create test farm
        coords = [
            (37.6500, -0.0500),
            (37.6520, -0.0500),
            (37.6520, -0.0520),
            (37.6500, -0.0520),
            (37.6500, -0.0500)
        ]
        
        Farm.objects.create(
            farmer=self.farmer,
            farm_id='FARM-789-11',
            boundary=Polygon(coords),
            center_point=Polygon(coords).centroid,
            size_acres=2.0,
            size_hectares=0.81,
            county='Meru',
            sub_county='Imenti North',
            ward='Test Ward'
        )
        
        url = reverse('farms:farm_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_farm_detail(self):
        """Test getting farm details"""
        coords = [
            (37.6500, -0.0500),
            (37.6520, -0.0500),
            (37.6520, -0.0520),
            (37.6500, -0.0520),
            (37.6500, -0.0500)
        ]
        
        farm = Farm.objects.create(
            farmer=self.farmer,
            farm_id='FARM-789-12',
            boundary=Polygon(coords),
            center_point=Polygon(coords).centroid,
            size_acres=2.0,
            size_hectares=0.81,
            county='Meru',
            sub_county='Imenti North',
            ward='Test Ward',
            elevation=1650
        )
        
        url = reverse('farms:farm_detail', kwargs={'farm_id': farm.farm_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['farm_id'], farm.farm_id)
        self.assertIn('location', response.data)
        self.assertIn('boundary_geojson', response.data)
    
    def test_update_farm(self):
        """Test updating farm details"""
        coords = [
            (37.6500, -0.0500),
            (37.6520, -0.0500),
            (37.6520, -0.0520),
            (37.6500, -0.0520),
            (37.6500, -0.0500)
        ]
        
        farm = Farm.objects.create(
            farmer=self.farmer,
            farm_id='FARM-789-13',
            boundary=Polygon(coords),
            center_point=Polygon(coords).centroid,
            size_acres=2.0,
            size_hectares=0.81,
            county='Meru',
            sub_county='Imenti North',
            ward='Old Ward',
            elevation=1650
        )
        
        url = reverse('farms:farm_update', kwargs={'farm_id': farm.farm_id})
        data = {
            'ward': 'New Ward',
            'elevation': 1700
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify update
        farm.refresh_from_db()
        self.assertEqual(farm.ward, 'New Ward')
        self.assertEqual(farm.elevation, 1700)
    
    def test_get_farmer_farms(self):
        """Test getting all farms for a farmer"""
        # Create multiple farms
        for i in range(3):
            coords = [
                (37.6500 + i*0.01, -0.0500),
                (37.6520 + i*0.01, -0.0500),
                (37.6520 + i*0.01, -0.0520),
                (37.6500 + i*0.01, -0.0520),
                (37.6500 + i*0.01, -0.0500)
            ]
            
            Farm.objects.create(
                farmer=self.farmer,
                farm_id=f'FARM-789-{20+i}',
                boundary=Polygon(coords),
                center_point=Polygon(coords).centroid,
                size_acres=2.0 + i*0.5,
                size_hectares=0.81 + i*0.2,
                county='Meru',
                sub_county='Imenti North',
                ward=f'Ward {i}',
                is_primary=(i == 0)
            )
        
        url = reverse('farms:farmer_farms', kwargs={'pulse_id': self.farmer.pulse_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_farms'], 3)
        self.assertIn('total_area', response.data)
    
    def test_unauthorized_access(self):
        """Test accessing another farmer's farm"""
        # Create another user/farmer
        other_user = User.objects.create_user(
            username='otherfarmer',
            email='other@test.com',
            phone_number='+254722222222',
            password='TestPass123!',
            user_type='farmer'
        )
        
        other_farmer = Farmer.objects.create(
            user=other_user,
            pulse_id='CP-999-NA',
            full_name='Other Farmer',
            id_number='99999999',
            county='Nakuru',
            sub_county='Nakuru West',
            nearest_town='Nakuru',
            years_farming=2,
            primary_crop='Maize'
        )
        
        coords = [
            (36.0800, -0.3031),
            (36.0820, -0.3031),
            (36.0820, -0.3051),
            (36.0800, -0.3051),
            (36.0800, -0.3031)
        ]
        
        other_farm = Farm.objects.create(
            farmer=other_farmer,
            farm_id='FARM-999-50',
            boundary=Polygon(coords),
            center_point=Polygon(coords).centroid,
            size_acres=3.0,
            size_hectares=1.21,
            county='Nakuru',
            sub_county='Nakuru West',
            ward='Test Ward'
        )
        
        # Try to access as current user
        url = reverse('farms:farm_detail', kwargs={'farm_id': other_farm.farm_id})
        response = self.client.get(url)
        
        # Should return 404 (not found) to hide existence
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class SpatialQueriesTestCase(APITestCase):
    """Test cases for spatial queries"""
    
    def setUp(self):
        """Set up test data with multiple farms"""
        self.client = APIClient()
        
        # Create admin user for spatial queries
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            phone_number='+254700000000',
            password='AdminPass123!',
            user_type='admin'
        )
        
        # Create multiple farmers and farms
        self.farms = []
        for i in range(5):
            user = User.objects.create_user(
                username=f'farmer{i}',
                email=f'farmer{i}@test.com',
                phone_number=f'+25471000000{i}',
                password='TestPass123!',
                user_type='farmer'
            )
            
            farmer = Farmer.objects.create(
                user=user,
                pulse_id=f'CP-{100+i}-NA',
                full_name=f'Farmer {i}',
                id_number=f'1111111{i}',
                county='Nakuru',
                sub_county='Nakuru West',
                nearest_town='Nakuru',
                years_farming=i+1,
                primary_crop='Maize'
            )
            
            # Create farms at different locations
            coords = [
                (36.0800 + i*0.01, -0.3031),
                (36.0820 + i*0.01, -0.3031),
                (36.0820 + i*0.01, -0.3051),
                (36.0800 + i*0.01, -0.3051),
                (36.0800 + i*0.01, -0.3031)
            ]
            
            farm = Farm.objects.create(
                farmer=farmer,
                farm_id=f'FARM-{100+i}-{i}',
                boundary=Polygon(coords),
                center_point=Polygon(coords).centroid,
                size_acres=2.0 + i*0.3,
                size_hectares=0.81 + i*0.12,
                county='Nakuru',
                sub_county='Nakuru West',
                ward=f'Ward {i}'
            )
            
            self.farms.append(farm)
        
        self.client.force_authenticate(user=self.admin)
    
    def test_nearby_farms_query(self):
        """Test finding nearby farms"""
        # Use first farm as reference
        reference_farm = self.farms[0]
        
        url = reverse('farms:nearby_farms', kwargs={'farm_id': reference_farm.farm_id})
        response = self.client.get(url, {'radius_km': 5})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('nearby_farms', response.data)
        self.assertGreaterEqual(response.data['count'], 1)
    
    def test_farms_in_area_query(self):
        """Test finding farms in an area"""
        # Use center of first farm
        center = self.farms[0].center_point
        
        url = reverse('farms:farms_in_area')
        response = self.client.get(url, {
            'lat': center.y,
            'lng': center.x,
            'radius_km': 10
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('farms', response.data)
        self.assertGreaterEqual(response.data['count'], 1)
    
    def test_farms_in_area_invalid_params(self):
        """Test farms in area with invalid parameters"""
        url = reverse('farms:farms_in_area')
        response = self.client.get(url, {'lat': 'invalid', 'lng': 36.0810})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class FarmActionsTestCase(APITestCase):
    """Test cases for farm actions"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            username='actiontest',
            email='action@test.com',
            phone_number='+254755555555',
            password='TestPass123!',
            user_type='farmer'
        )
        
        self.farmer = Farmer.objects.create(
            user=self.user,
            pulse_id='CP-888-KI',
            full_name='Action Test',
            id_number='88888888',
            county='Kiambu',
            sub_county='Thika',
            nearest_town='Thika',
            years_farming=3,
            primary_crop='Coffee'
        )
        
        coords = [
            (37.0800, -1.0300),
            (37.0820, -1.0300),
            (37.0820, -1.0320),
            (37.0800, -1.0320),
            (37.0800, -1.0300)
        ]
        
        self.farm = Farm.objects.create(
            farmer=self.farmer,
            farm_id='FARM-888-77',
            boundary=Polygon(coords),
            center_point=Polygon(coords).centroid,
            size_acres=2.5,
            size_hectares=1.01,
            county='Kiambu',
            sub_county='Thika',
            ward='Test Ward',
            is_primary=False
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_set_primary_farm(self):
        """Test setting a farm as primary"""
        url = reverse('farms:set_primary', kwargs={'farm_id': self.farm.farm_id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify farm is now primary
        self.farm.refresh_from_db()
        self.assertTrue(self.farm.is_primary)
    
    def test_get_boundary_points(self):
        """Test getting farm boundary points"""
        # Create boundary points
        points_data = [
            (37.0800, -1.0300, 0),
            (37.0820, -1.0300, 1),
            (37.0820, -1.0320, 2),
            (37.0800, -1.0320, 3)
        ]
        
        for lng, lat, seq in points_data:
            FarmBoundaryPoint.objects.create(
                farm=self.farm,
                point=Point(lng, lat),
                sequence=seq
            )
        
        url = reverse('farms:boundary_points', kwargs={'farm_id': self.farm.farm_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 4)
    
    def test_get_farm_geojson(self):
        """Test getting farm as GeoJSON"""
        url = reverse('farms:farm_geojson', kwargs={'farm_id': self.farm.farm_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('type', response.data)
        self.assertEqual(response.data['type'], 'Feature')
        self.assertIn('geometry', response.data)