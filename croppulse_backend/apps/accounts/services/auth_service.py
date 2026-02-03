# apps/accounts/services/auth_service.py

import secrets
import hashlib
from datetime import datetime, timedelta
from django.core.cache import cache
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings


class AuthService:
    """
    Service class for authentication-related operations
    """
    
    @staticmethod
    def generate_tokens(user):
        """
        Generate JWT access and refresh tokens for user
        
        Args:
            user: User instance
            
        Returns:
            dict: Dictionary containing access and refresh tokens
        """
        refresh = RefreshToken.for_user(user)
        
        # Add custom claims
        refresh['user_type'] = user.user_type
        refresh['is_verified'] = user.is_verified
        refresh['email'] = user.email
        refresh['phone_number'] = user.phone_number
        
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'access_expires': (
                timezone.now() + timedelta(minutes=settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME', 60))
            ).isoformat(),
            'refresh_expires': (
                timezone.now() + timedelta(days=settings.SIMPLE_JWT.get('REFRESH_TOKEN_LIFETIME', 7))
            ).isoformat()
        }
    
    @staticmethod
    def generate_api_key():
        """
        Generate a secure API key for banks
        
        Returns:
            str: 64-character API key
        """
        return secrets.token_urlsafe(48)
    
    @staticmethod
    def hash_api_key(api_key):
        """
        Hash an API key for secure storage
        
        Args:
            api_key: API key string
            
        Returns:
            str: Hashed API key
        """
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @staticmethod
    def generate_verification_code(phone_number):
        """
        Generate and cache a 6-digit verification code
        
        Args:
            phone_number: User's phone number
            
        Returns:
            str: 6-digit verification code
        """
        # Generate random 6-digit code
        code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        
        # Cache code for 10 minutes
        cache_key = f'verification_code:{phone_number}'
        cache.set(cache_key, code, timeout=600)  # 10 minutes
        
        return code
    
    @staticmethod
    def verify_code(phone_number, code):
        """
        Verify a verification code against cached value
        
        Args:
            phone_number: User's phone number
            code: Code to verify
            
        Returns:
            bool: True if code is valid, False otherwise
        """
        cache_key = f'verification_code:{phone_number}'
        cached_code = cache.get(cache_key)
        
        if cached_code and cached_code == code:
            # Delete code after successful verification
            cache.delete(cache_key)
            return True
        
        return False
    
    @staticmethod
    def generate_password_reset_token(user):
        """
        Generate a password reset token
        
        Args:
            user: User instance
            
        Returns:
            str: Password reset token
        """
        token = secrets.token_urlsafe(32)
        
        # Cache token for 1 hour
        cache_key = f'password_reset:{user.id}'
        cache.set(cache_key, token, timeout=3600)
        
        return token
    
    @staticmethod
    def verify_password_reset_token(user_id, token):
        """
        Verify a password reset token
        
        Args:
            user_id: User ID
            token: Token to verify
            
        Returns:
            bool: True if token is valid, False otherwise
        """
        cache_key = f'password_reset:{user_id}'
        cached_token = cache.get(cache_key)
        
        if cached_token and cached_token == token:
            # Keep token in cache (will be deleted after password reset)
            return True
        
        return False
    
    @staticmethod
    def invalidate_password_reset_token(user_id):
        """
        Invalidate password reset token after use
        
        Args:
            user_id: User ID
        """
        cache_key = f'password_reset:{user_id}'
        cache.delete(cache_key)
    
    @staticmethod
    def track_login_attempt(identifier, success=True):
        """
        Track login attempts to prevent brute force
        
        Args:
            identifier: Username, email, or phone number
            success: Whether login was successful
        """
        cache_key = f'login_attempts:{identifier}'
        
        if success:
            # Clear attempts on successful login
            cache.delete(cache_key)
        else:
            # Increment failed attempts
            attempts = cache.get(cache_key, 0)
            attempts += 1
            
            # Lock account for 30 minutes after 5 failed attempts
            timeout = 1800 if attempts >= 5 else 300  # 30 min or 5 min
            cache.set(cache_key, attempts, timeout=timeout)
    
    @staticmethod
    def is_account_locked(identifier):
        """
        Check if account is locked due to failed login attempts
        
        Args:
            identifier: Username, email, or phone number
            
        Returns:
            tuple: (is_locked, attempts_remaining)
        """
        cache_key = f'login_attempts:{identifier}'
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:
            return True, 0
        
        return False, 5 - attempts
    
    @staticmethod
    def generate_session_id():
        """
        Generate a unique session ID
        
        Returns:
            str: Session ID
        """
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def create_audit_log(user, action, ip_address=None, user_agent=None, metadata=None):
        """
        Create an audit log entry
        
        Args:
            user: User instance
            action: Action performed (e.g., 'login', 'logout', 'password_change')
            ip_address: IP address
            user_agent: User agent string
            metadata: Additional metadata (dict)
        """
        from apps.accounts.models import AuditLog
        
        AuditLog.objects.create(
            user=user,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {},
            timestamp=timezone.now()
        )
    
    @staticmethod
    def check_password_strength(password):
        """
        Check password strength
        
        Args:
            password: Password to check
            
        Returns:
            dict: Strength analysis with score and feedback
        """
        score = 0
        feedback = []
        
        # Length check
        if len(password) >= 8:
            score += 1
        else:
            feedback.append('Password should be at least 8 characters')
        
        if len(password) >= 12:
            score += 1
        
        # Uppercase check
        if any(c.isupper() for c in password):
            score += 1
        else:
            feedback.append('Include at least one uppercase letter')
        
        # Lowercase check
        if any(c.islower() for c in password):
            score += 1
        else:
            feedback.append('Include at least one lowercase letter')
        
        # Digit check
        if any(c.isdigit() for c in password):
            score += 1
        else:
            feedback.append('Include at least one number')
        
        # Special character check
        special_chars = '!@#$%^&*()_+-=[]{}|;:,.<>?'
        if any(c in special_chars for c in password):
            score += 1
        else:
            feedback.append('Include at least one special character')
        
        # Calculate strength
        if score <= 2:
            strength = 'weak'
        elif score <= 4:
            strength = 'medium'
        else:
            strength = 'strong'
        
        return {
            'score': score,
            'max_score': 6,
            'strength': strength,
            'feedback': feedback
        }