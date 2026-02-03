# apps/accounts/serializers.py

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, AuditLog


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'phone_number',
            'first_name',
            'last_name',
            'user_type',
            'profile_image',
            'country_code',
            'language_preference',
            'is_verified',
            'is_active',
            'date_joined',
            'last_login',
            'last_activity',
            'days_since_joined',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'is_verified',
            'date_joined',
            'created_at',
            'updated_at'
        ]

    def get_full_name(self, obj):
        """Get user's full name"""
        return obj.get_full_name()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'phone_number',
            'password',
            'password_confirm',
            'first_name',
            'last_name',
            'user_type'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'phone_number': {'required': True},
            'user_type': {'required': True}
        }
    
    def validate(self, attrs):
        """Validate password confirmation"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password": "Password fields didn't match."
            })
        return attrs
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        # Remove spaces and dashes
        cleaned = value.replace(' ', '').replace('-', '')
        
        # Check if starts with +254 or 254 or 0
        if not (cleaned.startswith('+254') or cleaned.startswith('254') or cleaned.startswith('0')):
            raise serializers.ValidationError(
                "Phone number must start with +254, 254, or 0"
            )
        
        # Normalize to +254 format
        if cleaned.startswith('0'):
            cleaned = '+254' + cleaned[1:]
        elif cleaned.startswith('254'):
            cleaned = '+' + cleaned
        
        # Check length (should be +254XXXXXXXXX = 13 characters)
        if len(cleaned) != 13:
            raise serializers.ValidationError(
                "Invalid phone number length"
            )
        
        return cleaned
    
    def validate_user_type(self, value):
        """Validate user type"""
        valid_types = ['farmer', 'bank', 'admin']
        if value not in valid_types:
            raise serializers.ValidationError(
                f"User type must be one of: {', '.join(valid_types)}"
            )
        return value
    
    def create(self, validated_data):
        """Create new user"""
        # Remove password_confirm as it's not a model field
        validated_data.pop('password_confirm')
        
        # Create user
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            phone_number=validated_data['phone_number'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            user_type=validated_data['user_type'],
            is_verified=False  # Users start unverified
        )
        
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    
    username = serializers.CharField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        """Authenticate user"""
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            # Try authentication
            user = authenticate(
                request=self.context.get('request'),
                username=username,
                password=password
            )
            
            if not user:
                raise serializers.ValidationError(
                    'Unable to log in with provided credentials.',
                    code='authorization'
                )
            
            if not user.is_active:
                raise serializers.ValidationError(
                    'User account is disabled.',
                    code='authorization'
                )
            
        else:
            raise serializers.ValidationError(
                'Must include "username" and "password".',
                code='authorization'
            )
        
        attrs['user'] = user
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change"""
    
    old_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    
    def validate_old_password(self, value):
        """Validate old password"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect.')
        return value
    
    def validate(self, attrs):
        """Validate new password confirmation"""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                "new_password": "New password fields didn't match."
            })
        return attrs
    
    def save(self, **kwargs):
        """Save new password"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile"""
    
    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone_number'
        ]
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        cleaned = value.replace(' ', '').replace('-', '')
        
        if not (cleaned.startswith('+254') or cleaned.startswith('254') or cleaned.startswith('0')):
            raise serializers.ValidationError(
                "Phone number must start with +254, 254, or 0"
            )
        
        if cleaned.startswith('0'):
            cleaned = '+254' + cleaned[1:]
        elif cleaned.startswith('254'):
            cleaned = '+' + cleaned
        
        if len(cleaned) != 13:
            raise serializers.ValidationError("Invalid phone number length")
        
        # Check if phone number already exists (excluding current user)
        user = self.context['request'].user
        if User.objects.filter(phone_number=cleaned).exclude(id=user.id).exists():
            raise serializers.ValidationError(
                "This phone number is already registered."
            )
        
        return cleaned
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        user = self.context['request'].user
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError(
                "This email address is already registered."
            )
        return value


class PhoneVerificationSerializer(serializers.Serializer):
    """Serializer for phone number verification"""
    
    phone_number = serializers.CharField(required=True)
    verification_code = serializers.CharField(required=True, min_length=6, max_length=6)
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        cleaned = value.replace(' ', '').replace('-', '')
        
        if not (cleaned.startswith('+254') or cleaned.startswith('254') or cleaned.startswith('0')):
            raise serializers.ValidationError(
                "Phone number must start with +254, 254, or 0"
            )
        
        if cleaned.startswith('0'):
            cleaned = '+254' + cleaned[1:]
        elif cleaned.startswith('254'):
            cleaned = '+' + cleaned
        
        if len(cleaned) != 13:
            raise serializers.ValidationError("Invalid phone number length")
        
        return cleaned


class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer with additional user information"""
    
    full_name = serializers.SerializerMethodField()
    days_since_joined = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'phone_number',
            'first_name',
            'last_name',
            'full_name',
            'user_type',
            'is_verified',
            'is_active',
            'date_joined',
            'last_login',
            'days_since_joined',
            'created_at',
            'updated_at'
        ]
        read_only_fields = fields
    
    def get_full_name(self, obj):
        """Get user's full name"""
        if obj.first_name and obj.last_name:
            return f"{obj.first_name} {obj.last_name}"
        return obj.username
    
    def get_days_since_joined(self, obj):
        """Calculate days since user joined"""
        from django.utils import timezone
        delta = timezone.now() - obj.date_joined
        return delta.days
    
class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for Audit Logs"""
    
    user_username = serializers.CharField(source='user.username', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user',
            'user_username',
            'action',
            'action_display',
            'ip_address',
            'user_agent',
            'metadata',
            'timestamp'
        ]
        read_only_fields = fields