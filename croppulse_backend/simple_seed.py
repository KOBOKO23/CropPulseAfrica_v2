"""
Simple seed script - Run with: python simple_seed.py
Creates basic data without requiring full migrations
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'croppulse_backend.settings.base')
django.setup()

from django.contrib.auth import get_user_model
import random

User = get_user_model()

print("🌱 Creating seed data...")

# Create users
users_created = 0
for i in range(20):
    username = f'farmer{i+1}'
    if not User.objects.filter(username=username).exists():
        user = User.objects.create_user(
            username=username,
            email=f'farmer{i+1}@example.com',
            phone_number=f'+25471{i:07d}',
            password='password123',
            user_type='farmer'
        )
        user.is_verified = True
        user.save()
        users_created += 1

# Create bank users
for bank_name, code in [('Equity Bank', 'eqb'), ('KCB Bank', 'kcb'), ('Coop Bank', 'coop')]:
    if not User.objects.filter(username=code).exists():
        user = User.objects.create_user(
            username=code,
            email=f'{code}@bank.com',
            phone_number=f'+25472{random.randint(1000000, 9999999)}',
            password='password123',
            user_type='bank'
        )
        user.is_verified = True
        user.save()
        users_created += 1

print(f"✅ Created {users_created} users!")
print(f"📊 Total users in database: {User.objects.count()}")
print("\nLogin credentials:")
print("  Farmers: farmer1-farmer20 / password123")
print("  Banks: eqb, kcb, coop / password123")
