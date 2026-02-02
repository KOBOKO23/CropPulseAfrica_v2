# apps/farmers/serializers.py

from rest_framework import serializers
from django.utils import timezone
from .models import Farmer, VoiceRegistration
from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer


class FarmerSerializer(serializers.ModelSerializer):
    """Basic serializer for Farmer model"""
    
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    is_verified = serializers.BooleanField(source='user.is_verified', read_only=True)
    
    class Meta:
        model = Farmer
        fields = [
            'id',
            'pulse_id',
            'full_name',
            'date_of_birth',
            'id_number',
            'county',
            'sub_county',
            'nearest_town',
            'years_farming',
            'primary_crop',
            'secondary_crops',
            'photo',
            'phone_number',
            'email',
            'is_verified',
            'onboarding_completed',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'pulse_id', 'created_at', 'updated_at']


class FarmerCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new farmer profile"""
    
    class Meta:
        model = Farmer
        fields = [
            'full_name',
            'date_of_birth',
            'id_number',
            'county',
            'sub_county',
            'nearest_town',
            'years_farming',
            'primary_crop',
            'secondary_crops',
            'photo'
        ]
    
    def validate_id_number(self, value):
        """Validate ID number uniqueness"""
        if Farmer.objects.filter(id_number=value).exists():
            raise serializers.ValidationError(
                "A farmer with this ID number already exists."
            )
        return value
    
    def validate_years_farming(self, value):
        """Validate years of farming"""
        if value < 0:
            raise serializers.ValidationError("Years farming cannot be negative.")
        if value > 80:
            raise serializers.ValidationError("Years farming seems unrealistic.")
        return value
    
    def validate_county(self, value):
        """Validate county is in Kenya"""
        kenyan_counties = [
            'Baringo', 'Bomet', 'Bungoma', 'Busia', 'Elgeyo-Marakwet',
            'Embu', 'Garissa', 'Homa Bay', 'Isiolo', 'Kajiado', 'Kakamega',
            'Kericho', 'Kiambu', 'Kilifi', 'Kirinyaga', 'Kisii', 'Kisumu',
            'Kitui', 'Kwale', 'Laikipia', 'Lamu', 'Machakos', 'Makueni',
            'Mandera', 'Marsabit', 'Meru', 'Migori', 'Mombasa', 'Murang\'a',
            'Nairobi', 'Nakuru', 'Nandi', 'Narok', 'Nyamira', 'Nyandarua',
            'Nyeri', 'Samburu', 'Siaya', 'Taita-Taveta', 'Tana River',
            'Tharaka-Nithi', 'Trans Nzoia', 'Turkana', 'Uasin Gishu',
            'Vihiga', 'Wajir', 'West Pokot'
        ]
        
        if value.title() not in kenyan_counties:
            raise serializers.ValidationError(
                f"'{value}' is not a recognized Kenyan county."
            )
        
        return value.title()
    
    def create(self, validated_data):
        """Create farmer profile"""
        user = self.context.get('user')
        
        if not user:
            raise serializers.ValidationError("User is required")
        
        # Check if user already has a farmer profile
        if hasattr(user, 'farmer_profile'):
            raise serializers.ValidationError(
                "This user already has a farmer profile"
            )
        
        # Generate Pulse ID
        pulse_id = self._generate_pulse_id(validated_data['county'])
        
        # Create farmer
        farmer = Farmer.objects.create(
            user=user,
            pulse_id=pulse_id,
            **validated_data
        )
        
        return farmer
    
    def _generate_pulse_id(self, county):
        """Generate unique Pulse ID: CP-XXX-CC"""
        import random
        
        # Get county code (first 2 letters)
        county_code = county[:2].upper()
        
        # Generate unique number
        while True:
            number = random.randint(100, 999)
            pulse_id = f"CP-{number}-{county_code}"
            
            if not Farmer.objects.filter(pulse_id=pulse_id).exists():
                return pulse_id


class FarmerUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating farmer profile"""
    
    class Meta:
        model = Farmer
        fields = [
            'full_name',
            'date_of_birth',
            'county',
            'sub_county',
            'nearest_town',
            'years_farming',
            'primary_crop',
            'secondary_crops',
            'photo'
        ]


class FarmerDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer with additional information"""
    
    user_details = UserSerializer(source='user', read_only=True)
    farms_count = serializers.SerializerMethodField()
    total_farm_size = serializers.SerializerMethodField()
    latest_pulse_score = serializers.SerializerMethodField()
    days_since_registered = serializers.SerializerMethodField()
    
    class Meta:
        model = Farmer
        fields = [
            'id',
            'pulse_id',
            'user_details',
            'full_name',
            'date_of_birth',
            'id_number',
            'county',
            'sub_county',
            'nearest_town',
            'years_farming',
            'primary_crop',
            'secondary_crops',
            'photo',
            'onboarding_completed',
            'is_active',
            'farms_count',
            'total_farm_size',
            'latest_pulse_score',
            'days_since_registered',
            'created_at',
            'updated_at'
        ]
        read_only_fields = fields
    
    def get_farms_count(self, obj):
        """Get number of farms"""
        return obj.farms.count()
    
    def get_total_farm_size(self, obj):
        """Get total farm size in acres"""
        total = sum(float(farm.size_acres) for farm in obj.farms.all())
        return round(total, 2)
    
    def get_latest_pulse_score(self, obj):
        """Get latest Pulse Score"""
        # This will be populated when scoring app is built
        return None
    
    def get_days_since_registered(self, obj):
        """Calculate days since registration"""
        delta = timezone.now() - obj.created_at
        return delta.days


class VoiceRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for Voice Registration"""
    
    farmer_name = serializers.CharField(source='farmer.full_name', read_only=True)
    pulse_id = serializers.CharField(source='farmer.pulse_id', read_only=True)
    
    class Meta:
        model = VoiceRegistration
        fields = [
            'id',
            'farmer',
            'farmer_name',
            'pulse_id',
            'audio_file',
            'transcript',
            'detected_language',
            'confidence_score',
            'processed_data',
            'created_at'
        ]
        read_only_fields = [
            'id',
            'transcript',
            'detected_language',
            'confidence_score',
            'processed_data',
            'created_at'
        ]


class VoiceRegistrationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating voice registration"""
    
    class Meta:
        model = VoiceRegistration
        fields = ['farmer', 'audio_file']
    
    def validate_audio_file(self, value):
        """Validate audio file"""
        # Check file size (max 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                "Audio file size cannot exceed 10MB"
            )
        
        # Check file type
        allowed_types = ['audio/wav', 'audio/mp3', 'audio/mpeg', 'audio/ogg']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"Invalid audio format. Allowed: {', '.join(allowed_types)}"
            )
        
        return value
    
    def create(self, validated_data):
        """Process voice registration"""
        # For now, create with dummy data
        # In production, this would call OpenAI Whisper service
        
        voice_registration = VoiceRegistration.objects.create(
            farmer=validated_data['farmer'],
            audio_file=validated_data['audio_file'],
            transcript='[Voice processing placeholder]',
            detected_language='en',
            confidence_score=0.85,
            processed_data={}
        )
        
        return voice_registration


class FarmerStatsSerializer(serializers.Serializer):
    """Serializer for farmer statistics"""
    
    total_farmers = serializers.IntegerField()
    active_farmers = serializers.IntegerField()
    verified_farmers = serializers.IntegerField()
    onboarded_farmers = serializers.IntegerField()
    by_county = serializers.ListField()
    by_crop = serializers.ListField()
    average_farm_size = serializers.FloatField()
    average_experience = serializers.FloatField()


class FarmerOnboardingSerializer(serializers.Serializer):
    """Serializer for onboarding progress"""
    
    farmer_id = serializers.IntegerField()
    pulse_id = serializers.CharField()
    steps_completed = serializers.DictField()
    progress_percentage = serializers.IntegerField()
    next_step = serializers.CharField()
    is_complete = serializers.BooleanField()