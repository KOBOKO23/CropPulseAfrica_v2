"""
Django management command to seed database
Run: python manage.py seed_db
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.farmers.models import Farmer
from apps.farms.models import Farm, FarmBoundaryPoint
from apps.banks.models import Bank
from apps.scoring.models import PulseScore
from apps.climate.models import ClimateData
from apps.loans.models import LoanApplication, InterestRatePolicy
from decimal import Decimal
from datetime import datetime, timedelta
import random

User = get_user_model()

COUNTIES = [
    ('Kiambu', -1.1748, 36.8356), ('Nakuru', -0.3031, 36.0800),
    ('Uasin Gishu', 0.5143, 35.2698), ('Trans Nzoia', 1.0522, 34.9503),
    ('Bungoma', 0.5635, 34.5606), ('Kakamega', 0.2827, 34.7519),
    ('Kisumu', -0.0917, 34.7680), ('Meru', 0.0469, 37.6556),
]

CROPS = ['maize', 'beans', 'wheat', 'tea', 'coffee', 'potatoes']

class Command(BaseCommand):
    help = 'Seed database with sample data'

    def handle(self, *args, **kwargs):
        self.stdout.write('🌱 Seeding database...\n')
        
        # Banks
        self.stdout.write('💰 Creating banks...')
        banks = self._create_banks()
        
        # Farmers & Farms
        self.stdout.write('👨‍🌾 Creating farmers...')
        farmers = self._create_farmers(50)
        
        # Climate Data
        self.stdout.write('🌦️  Creating climate data...')
        self._create_climate_data()
        
        # Loans
        self.stdout.write('💵 Creating loans...')
        self._create_loans(farmers, banks)
        
        self.stdout.write(self.style.SUCCESS('\n✅ Seeding completed!'))
        self._print_summary()

    def _create_banks(self):
        banks = []
        for name, code, tier in [
            ('Equity Bank', 'EQB', 'enterprise'),
            ('KCB Bank', 'KCB', 'professional'),
            ('Cooperative Bank', 'COOP', 'basic'),
        ]:
            user, _ = User.objects.get_or_create(
                username=code.lower(),
                defaults={
                    'phone_number': f'+25471{random.randint(1000000, 9999999)}',
                    'user_type': 'bank',
                    'is_verified': True,
                }
            )
            bank, _ = Bank.objects.get_or_create(
                user=user,
                defaults={'name': name, 'bank_code': code, 'tier': tier}
            )
            banks.append(bank)
        return banks

    def _create_farmers(self, count):
        farmers = []
        for i in range(count):
            county, lat, lng = random.choice(COUNTIES)
            
            user, _ = User.objects.get_or_create(
                username=f'farmer{i+1}',
                defaults={
                    'phone_number': f'+25471{random.randint(1000000, 9999999)}',
                    'user_type': 'farmer',
                    'county': county,
                    'is_verified': True,
                }
            )
            
            farmer, _ = Farmer.objects.get_or_create(
                user=user,
                defaults={
                    'first_name': f'John{i+1}',
                    'last_name': f'Kamau{i+1}',
                    'id_number': f'{random.randint(10000000, 99999999)}',
                    'county': county,
                    'latitude': Decimal(str(lat + random.uniform(-0.1, 0.1))),
                    'longitude': Decimal(str(lng + random.uniform(-0.1, 0.1))),
                    'years_farming': random.randint(2, 30),
                    'primary_crop': random.choice(CROPS),
                    'onboarding_complete': True,
                }
            )
            
            # Create farms
            for j in range(random.randint(1, 2)):
                farm_lat = lat + random.uniform(-0.05, 0.05)
                farm_lng = lng + random.uniform(-0.05, 0.05)
                
                farm, _ = Farm.objects.get_or_create(
                    farmer=farmer,
                    name=f'{farmer.first_name} Farm {j+1}',
                    defaults={
                        'crop_type': random.choice(CROPS),
                        'planting_date': datetime.now().date() - timedelta(days=random.randint(30, 180)),
                        'latitude': Decimal(str(farm_lat)),
                        'longitude': Decimal(str(farm_lng)),
                        'county': county,
                        'is_verified': random.choice([True, False]),
                        'is_primary': j == 0,
                    }
                )
                
                # Boundary points
                if not FarmBoundaryPoint.objects.filter(farm=farm).exists():
                    offset = 0.002
                    for idx, (dlat, dlng) in enumerate([(0,0), (offset,0), (offset,offset), (0,offset)]):
                        FarmBoundaryPoint.objects.create(
                            farm=farm,
                            latitude=Decimal(str(farm_lat + dlat)),
                            longitude=Decimal(str(farm_lng + dlng)),
                            order=idx + 1,
                        )
            
            # Credit score
            PulseScore.objects.get_or_create(
                farmer=farmer,
                defaults={
                    'score': random.randint(450, 950),
                    'farm_size_score': random.randint(50, 100),
                    'crop_health_score': random.randint(50, 100),
                    'climate_risk_score': random.randint(30, 90),
                    'expires_at': datetime.now() + timedelta(days=90),
                }
            )
            
            farmers.append(farmer)
        
        return farmers

    def _create_climate_data(self):
        for county, lat, lng in COUNTIES[:5]:
            for days_ago in range(30):
                date = datetime.now().date() - timedelta(days=days_ago)
                ClimateData.objects.get_or_create(
                    latitude=Decimal(str(lat)),
                    longitude=Decimal(str(lng)),
                    date=date,
                    defaults={
                        'temperature_avg': Decimal(str(random.uniform(18, 28))),
                        'rainfall': Decimal(str(random.uniform(0, 50))),
                        'humidity': Decimal(str(random.uniform(40, 85))),
                        'data_source': 'NASA_POWER',
                    }
                )

    def _create_loans(self, farmers, banks):
        # Interest rate policy
        InterestRatePolicy.objects.get_or_create(
            min_score=700,
            max_score=1000,
            defaults={'base_rate': Decimal('12.0')}
        )
        InterestRatePolicy.objects.get_or_create(
            min_score=500,
            max_score=699,
            defaults={'base_rate': Decimal('18.0')}
        )
        
        # Loan applications
        for farmer in random.sample(list(farmers), min(20, len(farmers))):
            LoanApplication.objects.get_or_create(
                farmer=farmer,
                bank=random.choice(banks),
                defaults={
                    'amount_requested': Decimal(str(random.randint(50000, 500000))),
                    'purpose': random.choice(['seeds', 'fertilizer', 'equipment', 'irrigation']),
                    'loan_term_months': random.choice([6, 12, 18, 24]),
                    'status': random.choice(['pending', 'approved', 'disbursed']),
                }
            )

    def _print_summary(self):
        self.stdout.write(f'\nSummary:')
        self.stdout.write(f'  Banks: {Bank.objects.count()}')
        self.stdout.write(f'  Farmers: {Farmer.objects.count()}')
        self.stdout.write(f'  Farms: {Farm.objects.count()}')
        self.stdout.write(f'  Loans: {LoanApplication.objects.count()}')
        self.stdout.write(f'  Climate Records: {ClimateData.objects.count()}')
