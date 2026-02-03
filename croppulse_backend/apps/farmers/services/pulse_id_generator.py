# apps/farmers/services/pulse_id_generator.py

import random
import hashlib
from django.db import transaction
from apps.farmers.models import Farmer


class PulseIDGenerator:
    """
    Service for generating unique Pulse IDs
    Format: CP-XXX-CC where:
    - CP = CropPulse prefix
    - XXX = 3-digit random number (100-999)
    - CC = County code (first 2 letters)
    """
    
    # County code mapping for consistency
    COUNTY_CODES = {
        'Baringo': 'BA',
        'Bomet': 'BO',
        'Bungoma': 'BU',
        'Busia': 'BS',
        'Elgeyo-Marakwet': 'EM',
        'Embu': 'EB',
        'Garissa': 'GA',
        'Homa Bay': 'HB',
        'Isiolo': 'IS',
        'Kajiado': 'KJ',
        'Kakamega': 'KK',
        'Kericho': 'KE',
        'Kiambu': 'KB',
        'Kilifi': 'KF',
        'Kirinyaga': 'KR',
        'Kisii': 'KS',
        'Kisumu': 'KM',
        'Kitui': 'KT',
        'Kwale': 'KW',
        'Laikipia': 'LK',
        'Lamu': 'LM',
        'Machakos': 'MC',
        'Makueni': 'MK',
        'Mandera': 'MD',
        'Marsabit': 'MB',
        'Meru': 'ME',
        'Migori': 'MG',
        'Mombasa': 'MM',
        'Murang\'a': 'MR',
        'Nairobi': 'NB',
        'Nakuru': 'NK',
        'Nandi': 'ND',
        'Narok': 'NR',
        'Nyamira': 'NM',
        'Nyandarua': 'NY',
        'Nyeri': 'NE',
        'Samburu': 'SB',
        'Siaya': 'SY',
        'Taita-Taveta': 'TT',
        'Tana River': 'TR',
        'Tharaka-Nithi': 'TN',
        'Trans Nzoia': 'TZ',
        'Turkana': 'TK',
        'Uasin Gishu': 'UG',
        'Vihiga': 'VH',
        'Wajir': 'WJ',
        'West Pokot': 'WP'
    }
    
    @classmethod
    def generate(cls, county, max_attempts=100):
        """
        Generate a unique Pulse ID
        
        Args:
            county (str): County name
            max_attempts (int): Maximum generation attempts
            
        Returns:
            str: Generated Pulse ID (e.g., CP-882-NK)
            
        Raises:
            ValueError: If unique ID cannot be generated
        """
        county_code = cls.get_county_code(county)
        
        for _ in range(max_attempts):
            # Generate random 3-digit number
            number = random.randint(100, 999)
            pulse_id = f"CP-{number}-{county_code}"
            
            # Check uniqueness
            if not Farmer.objects.filter(pulse_id=pulse_id).exists():
                return pulse_id
        
        # If failed after max_attempts, use hash-based generation
        return cls._generate_hash_based(county, county_code)
    
    @classmethod
    def get_county_code(cls, county):
        """
        Get 2-letter county code
        
        Args:
            county (str): County name
            
        Returns:
            str: 2-letter county code
        """
        # Normalize county name
        county_clean = county.strip().title()
        
        # Try to get from mapping
        if county_clean in cls.COUNTY_CODES:
            return cls.COUNTY_CODES[county_clean]
        
        # Fallback: use first 2 letters
        return county_clean[:2].upper()
    
    @classmethod
    def _generate_hash_based(cls, county, county_code):
        """
        Generate Pulse ID using hash when random fails
        
        Args:
            county (str): County name
            county_code (str): County code
            
        Returns:
            str: Generated Pulse ID
        """
        import time
        
        # Create unique hash
        unique_string = f"{county}{time.time()}{random.random()}"
        hash_obj = hashlib.md5(unique_string.encode())
        hash_hex = hash_obj.hexdigest()
        
        # Use first 3 digits of hash
        number = int(hash_hex[:3], 16) % 900 + 100  # Ensure 100-999
        
        return f"CP-{number}-{county_code}"
    
    @classmethod
    def validate(cls, pulse_id):
        """
        Validate Pulse ID format
        
        Args:
            pulse_id (str): Pulse ID to validate
            
        Returns:
            bool: True if valid format
        """
        import re
        
        pattern = r'^CP-\d{3}-[A-Z]{2}$'
        return bool(re.match(pattern, pulse_id))
    
    @classmethod
    def parse(cls, pulse_id):
        """
        Parse Pulse ID into components
        
        Args:
            pulse_id (str): Pulse ID (e.g., CP-882-NK)
            
        Returns:
            dict: Parsed components or None if invalid
        """
        if not cls.validate(pulse_id):
            return None
        
        parts = pulse_id.split('-')
        
        return {
            'prefix': parts[0],
            'number': parts[1],
            'county_code': parts[2]
        }
    
    @classmethod
    def get_county_from_code(cls, county_code):
        """
        Reverse lookup: get county name from code
        
        Args:
            county_code (str): 2-letter county code
            
        Returns:
            str: County name or None
        """
        for county, code in cls.COUNTY_CODES.items():
            if code == county_code:
                return county
        return None
    
    @classmethod
    @transaction.atomic
    def regenerate(cls, farmer):
        """
        Regenerate Pulse ID for a farmer (admin only)
        
        Args:
            farmer: Farmer instance
            
        Returns:
            str: New Pulse ID
        """
        old_pulse_id = farmer.pulse_id
        new_pulse_id = cls.generate(farmer.county)
        
        farmer.pulse_id = new_pulse_id
        farmer.save(update_fields=['pulse_id'])
        
        # Log the change (you can add audit logging here)
        print(f"Regenerated Pulse ID: {old_pulse_id} -> {new_pulse_id}")
        
        return new_pulse_id