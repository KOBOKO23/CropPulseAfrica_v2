"""
Seed database with realistic Kenyan agricultural data
Run: python manage.py shell < scripts/seed_data.py
"""

from django.contrib.auth import get_user_model
from apps.farmers.models import Farmer
from apps.farms.models import Farm, FarmBoundaryPoint
from apps.banks.models import Bank
from apps.scoring.models import PulseScore
from apps.climate.models import ClimateData
from decimal import Decimal
from datetime import datetime, timedelta
import random

User = get_user_model()

# Kenyan counties and coordinates
COUNTIES = [
    ('Kiambu', -1.1748, 36.8356),
    ('Nakuru', -0.3031, 36.0800),
    ('Uasin Gishu', 0.5143, 35.2698),
    ('Trans Nzoia', 1.0522, 34.9503),
    ('Bungoma', 0.5635, 34.5606),
    ('Kakamega', 0.2827, 34.7519),
    ('Kisumu', -0.0917, 34.7680),
    ('Meru', 0.0469, 37.6556),
    ('Embu', -0.5381, 37.4570),
    ('Machakos', -1.5177, 37.2634),
]

CROPS = ['maize', 'beans', 'wheat', 'tea', 'coffee', 'potatoes', 'tomatoes', 'kale']

print("🌱 Starting database seeding...")

# 1. Create Banks
print("\n💰 Creating banks...")
banks_data = [
    {'name': 'Equity Bank', 'code': 'EQB', 'tier': 'enterprise'},
    {'name': 'KCB Bank', 'code': 'KCB', 'tier': 'professional'},
    {'name': 'Cooperative Bank', 'code': 'COOP', 'tier': 'basic'},
    {'name': 'NCBA Bank', 'code': 'NCBA', 'tier': 'professional'},
]

banks = []
for bank_data in banks_data:
    user, _ = User.objects.get_or_create(
        username=bank_data['code'].lower(),
        defaults={
            'phone_number': f'+25471{random.randint(1000000, 9999999)}',
            'user_type': 'bank',
            'is_verified': True,
        }
    )
    bank, created = Bank.objects.get_or_create(
        user=user,
        defaults={
            'name': bank_data['name'],
            'bank_code': bank_data['code'],
            'tier': bank_data['tier'],
        }
    )
    banks.append(bank)
    print(f"  ✓ {bank.name}")

# 2. Create Farmers with Farms
print("\n👨‍🌾 Creating farmers and farms...")
for i in range(50):
    county_name, base_lat, base_lng = random.choice(COUNTIES)
    
    # Create user
    user, _ = User.objects.get_or_create(
        username=f'farmer{i+1}',
        defaults={
            'phone_number': f'+25471{random.randint(1000000, 9999999)}',
            'user_type': 'farmer',
            'county': county_name,
            'is_verified': True,
        }
    )
    
    # Create farmer profile
    farmer, created = Farmer.objects.get_or_create(
        user=user,
        defaults={
            'first_name': f'John{i+1}',
            'last_name': f'Kamau{i+1}',
            'id_number': f'{random.randint(10000000, 99999999)}',
            'county': county_name,
            'sub_county': 'Central',
            'ward': 'Ward 1',
            'village': f'Village {i+1}',
            'latitude': Decimal(str(base_lat + random.uniform(-0.1, 0.1))),
            'longitude': Decimal(str(base_lng + random.uniform(-0.1, 0.1))),
            'years_farming': random.randint(2, 30),
            'primary_crop': random.choice(CROPS),
            'secondary_crops': ','.join(random.sample(CROPS, 2)),
            'onboarding_complete': True,
        }
    )
    
    # Create 1-3 farms per farmer
    num_farms = random.randint(1, 3)
    for j in range(num_farms):
        farm_lat = base_lat + random.uniform(-0.05, 0.05)
        farm_lng = base_lng + random.uniform(-0.05, 0.05)
        
        farm, _ = Farm.objects.get_or_create(
            farmer=farmer,
            name=f'{farmer.first_name} Farm {j+1}',
            defaults={
                'crop_type': random.choice(CROPS),
                'planting_date': datetime.now().date() - timedelta(days=random.randint(30, 180)),
                'expected_harvest_date': datetime.now().date() + timedelta(days=random.randint(30, 120)),
                'latitude': Decimal(str(farm_lat)),
                'longitude': Decimal(str(farm_lng)),
                'county': county_name,
                'is_verified': random.choice([True, False]),
                'is_primary': j == 0,
            }
        )
        
        # Create boundary points (4-point polygon)
        if not FarmBoundaryPoint.objects.filter(farm=farm).exists():
            offset = 0.002  # ~200 meters
            points = [
                (farm_lat, farm_lng),
                (farm_lat + offset, farm_lng),
                (farm_lat + offset, farm_lng + offset),
                (farm_lat, farm_lng + offset),
            ]
            
            for idx, (lat, lng) in enumerate(points):
                FarmBoundaryPoint.objects.create(
                    farm=farm,
                    latitude=Decimal(str(lat)),
                    longitude=Decimal(str(lng)),
                    order=idx + 1,
                )
    
    # Create credit score
    PulseScore.objects.get_or_create(
        farmer=farmer,
        defaults={
            'score': random.randint(450, 950),
            'farm_size_score': random.randint(50, 100),
            'crop_health_score': random.randint(50, 100),
            'climate_risk_score': random.randint(30, 90),
            'payment_history_score': random.randint(40, 100),
            'deforestation_score': random.randint(80, 100),
            'confidence_level': random.uniform(0.7, 0.95),
            'expires_at': datetime.now() + timedelta(days=90),
        }
    )
    
    if (i + 1) % 10 == 0:
        print(f"  ✓ Created {i+1} farmers with farms")

# 3. Create Climate Data
print("\n🌦️  Creating climate data...")
for county_name, lat, lng in COUNTIES[:5]:  # First 5 counties
    for days_ago in range(30):
        date = datetime.now().date() - timedelta(days=days_ago)
        ClimateData.objects.get_or_create(
            latitude=Decimal(str(lat)),
            longitude=Decimal(str(lng)),
            date=date,
            defaults={
                'temperature_avg': Decimal(str(random.uniform(18, 28))),
                'temperature_min': Decimal(str(random.uniform(12, 20))),
                'temperature_max': Decimal(str(random.uniform(25, 35))),
                'rainfall': Decimal(str(random.uniform(0, 50))),
                'humidity': Decimal(str(random.uniform(40, 85))),
                'wind_speed': Decimal(str(random.uniform(5, 25))),
                'data_source': 'NASA_POWER',
            }
        )
    print(f"  ✓ {county_name}: 30 days of climate data")

# 4. Link farmers to banks
print("\n🔗 Linking farmers to banks...")
farmers = Farmer.objects.all()
for farmer in farmers[:30]:  # Link first 30 farmers
    bank = random.choice(banks)
    farmer.linked_banks.add(bank)
print(f"  ✓ Linked {30} farmers to banks")

print("\n✅ Database seeding completed!")
print(f"\nSummary:")
print(f"  - Banks: {Bank.objects.count()}")
print(f"  - Farmers: {Farmer.objects.count()}")
print(f"  - Farms: {Farm.objects.count()}")
print(f"  - Boundary Points: {FarmBoundaryPoint.objects.count()}")
print(f"  - Credit Scores: {PulseScore.objects.count()}")
print(f"  - Climate Records: {ClimateData.objects.count()}")
