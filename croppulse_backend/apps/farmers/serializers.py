# apps/farmers/serializers.py

from rest_framework import serializers
from django.utils import timezone
from decimal import Decimal
from .models import Farmer, VoiceRegistration, FarmerNote
from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from .services import PulseIDGenerator, FarmerProfileService


class FarmerSerializer(serializers.ModelSerializer):
    """Basic serializer for Farmer model"""
    
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    is_verified = serializers.BooleanField(source='user.is_verified', read_only=True)
    total_farm_size = serializers.SerializerMethodField()
    full_location = serializers.SerializerMethodField()
    
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
            'full_location',
            'latitude',
            'longitude',
            'years_farming',
            'primary_crop',
            'secondary_crops',
            'farming_method',
            'irrigation_access',
            'photo',
            'phone_number',
            'email',
            'is_verified',
            'fraud_status',
            'onboarding_completed',
            'is_active',
            'total_farm_size',
            'preferred_language',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'pulse_id',
            'fraud_status',
            'created_at',
            'updated_at'
        ]
    
    def get_total_farm_size(self, obj):
        """Get total farm size"""
        return float(obj.get_total_farm_size())
    
    def get_full_location(self, obj):
        """Get full location string"""
        return obj.get_full_location()


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
            'latitude',
            'longitude',
            'years_farming',
            'primary_crop',
            'secondary_crops',
            'farming_method',
            'irrigation_access',
            'photo',
            'preferred_language',
            'referral_source'
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
            raise serializers.ValidationError("Years farming seems unrealistic (max 80).")
        return value
    
    def validate_county(self, value):
        """Validate county is recognized"""
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
        
        value_title = value.strip().title()
        if value_title not in kenyan_counties:
            raise serializers.ValidationError(
                f"'{value}' is not a recognized Kenyan county."
            )
        
        return value_title
    
    def validate_latitude(self, value):
        """Validate latitude range"""
        if value and (value < -5 or value > 5):
            raise serializers.ValidationError(
                "Latitude must be within Kenya's range (-5 to 5)"
            )
        return value
    
    def validate_longitude(self, value):
        """Validate longitude range"""
        if value and (value < 33 or value > 42):
            raise serializers.ValidationError(
                "Longitude must be within Kenya's range (33 to 42)"
            )
        return value
    
    def create(self, validated_data):
        """Create farmer profile using service"""
        user = self.context.get('user')
        
        if not user:
            raise serializers.ValidationError("User is required")
        
        # Use service to create farmer
        farmer = FarmerProfileService.create_farmer_profile(user, validated_data)
        
        return farmer


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
            'latitude',
            'longitude',
            'years_farming',
            'primary_crop',
            'secondary_crops',
            'farming_method',
            'irrigation_access',
            'photo',
            'preferred_language'
        ]
    
    def validate_years_farming(self, value):
        """Validate years of farming"""
        if value < 0:
            raise serializers.ValidationError("Years farming cannot be negative.")
        if value > 80:
            raise serializers.ValidationError("Years farming seems unrealistic.")
        return value


class FarmerDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer with additional information"""
    
    user_details = UserSerializer(source='user', read_only=True)
    farms_count = serializers.SerializerMethodField()
    total_farm_size = serializers.SerializerMethodField()
    crops_list = serializers.SerializerMethodField()
    latest_pulse_score = serializers.SerializerMethodField()
    days_since_registered = serializers.SerializerMethodField()
    onboarding_progress = serializers.SerializerMethodField()
    full_location = serializers.SerializerMethodField()
    is_fraud_flagged = serializers.SerializerMethodField()
    
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
            'full_location',
            'latitude',
            'longitude',
            'years_farming',
            'primary_crop',
            'secondary_crops',
            'crops_list',
            'farming_method',
            'irrigation_access',
            'photo',
            'fraud_status',
            'onboarding_completed',
            'onboarding_completed_at',
            'is_active',
            'farms_count',
            'total_farm_size',
            'latest_pulse_score',
            'days_since_registered',
            'onboarding_progress',
            'is_fraud_flagged',
            'preferred_language',
            'referral_source',
            'created_at',
            'updated_at'
        ]
        read_only_fields = fields
    
    def get_farms_count(self, obj):
        """Get number of farms"""
        return obj.farms.filter(is_active=True).count()
    
    def get_total_farm_size(self, obj):
        """Get total farm size in acres"""
        return float(obj.get_total_farm_size())
    
    def get_crops_list(self, obj):
        """Get all crops"""
        return obj.get_crops_list()
    
    def get_latest_pulse_score(self, obj):
        """Get latest Pulse Score"""
        try:
            from apps.scoring.models import PulseScore
            latest = PulseScore.objects.filter(farmer=obj).order_by('-created_at').first()
            if latest:
                return {
                    'score': latest.score,
                    'created_at': latest.created_at,
                    'confidence': latest.confidence
                }
        except:
            pass
        return None
    
    def get_days_since_registered(self, obj):
        """Calculate days since registration"""
        delta = timezone.now() - obj.created_at
        return delta.days
    
    def get_onboarding_progress(self, obj):
        """Get onboarding progress"""
        return FarmerProfileService.get_onboarding_progress(obj)
    
    def get_full_location(self, obj):
        """Get full location"""
        return obj.get_full_location()
    
    def get_is_fraud_flagged(self, obj):
        """Check if fraud flagged"""
        return obj.is_fraud_flagged()


class VoiceRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for Voice Registration"""
    
    farmer_name = serializers.CharField(source='farmer.full_name', read_only=True)
    pulse_id = serializers.CharField(source='farmer.pulse_id', read_only=True)
    confidence_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = VoiceRegistration
        fields = [
            'id',
            'farmer',
            'farmer_name',
            'pulse_id',
            'audio_file',
            'audio_duration',
            'audio_format',
            'audio_size',
            'transcript',
            'detected_language',
            'confidence_score',
            'confidence_percentage',
            'processed_data',
            'field_confidence',
            'processing_status',
            'processing_error',
            'created_at',
            'processed_at'
        ]
        read_only_fields = [
            'id',
            'transcript',
            'detected_language',
            'confidence_score',
            'processed_data',
            'field_confidence',
            'processing_status',
            'processing_error',
            'audio_duration',
            'audio_format',
            'audio_size',
            'created_at',
            'processed_at'
        ]
    
    def get_confidence_percentage(self, obj):
        """Get confidence as percentage"""
        return obj.get_confidence_percentage()


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
        allowed_types = ['audio/wav', 'audio/mp3', 'audio/mpeg', 'audio/ogg', 'audio/webm']
        if hasattr(value, 'content_type') and value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"Invalid audio format. Allowed: {', '.join(allowed_types)}"
            )
        
        return value
    
    def create(self, validated_data):
        """Process voice registration"""
        audio_file = validated_data['audio_file']
        
        # Extract metadata
        audio_size = audio_file.size
        audio_format = audio_file.name.split('.')[-1] if '.' in audio_file.name else 'unknown'
        
        # Create voice registration (processing will be done async)
        voice_registration = VoiceRegistration.objects.create(
            farmer=validated_data['farmer'],
            audio_file=audio_file,
            audio_size=audio_size,
            audio_format=audio_format,
            transcript='[Processing...]',
            detected_language='en',
            confidence_score=0.0,
            processed_data={},
            field_confidence={},
            processing_status='pending'
        )
        
        # TODO: Trigger async task to process audio with Whisper
        # from apps.voice.tasks import process_voice_registration
        # process_voice_registration.delay(voice_registration.id)
        
        return voice_registration


class FarmerNoteSerializer(serializers.ModelSerializer):
    """Serializer for Farmer Notes"""
    
    created_by_name = serializers.CharField(
        source='created_by.get_full_name',
        read_only=True
    )
    
    class Meta:
        model = FarmerNote
        fields = [
            'id',
            'farmer',
            'created_by',
            'created_by_name',
            'note_type',
            'content',
            'is_internal',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FarmerNoteCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating farmer notes"""
    
    class Meta:
        model = FarmerNote
        fields = ['farmer', 'note_type', 'content', 'is_internal']
    
    def create(self, validated_data):
        """Create note with current user"""
        user = self.context.get('user')
        
        return FarmerNote.objects.create(
            created_by=user,
            **validated_data
        )


class FarmerStatsSerializer(serializers.Serializer):
    """Serializer for farmer statistics"""
    
    total_farmers = serializers.IntegerField()
    active_farmers = serializers.IntegerField()
    verified_farmers = serializers.IntegerField()
    onboarded_farmers = serializers.IntegerField()
    flagged_farmers = serializers.IntegerField()
    by_county = serializers.ListField()
    by_crop = serializers.ListField()
    by_fraud_status = serializers.ListField()
    average_farm_size = serializers.FloatField()
    average_experience = serializers.FloatField()


class FarmerOnboardingSerializer(serializers.Serializer):
    """Serializer for onboarding progress"""
    
    farmer_id = serializers.IntegerField()
    pulse_id = serializers.CharField()
    steps = serializers.DictField()
    completed = serializers.IntegerField()
    total = serializers.IntegerField()
    percentage = serializers.IntegerField()
    next_step = serializers.CharField()
    is_complete = serializers.BooleanField()


class FarmerSearchResultSerializer(serializers.Serializer):
    """Serializer for search results"""
    
    pulse_id = serializers.CharField()
    full_name = serializers.CharField()
    county = serializers.CharField()
    primary_crop = serializers.CharField()
    phone_number = serializers.CharField()
    is_verified = serializers.BooleanField()
    fraud_status = serializers.CharField()
    farms_count = serializers.IntegerField()