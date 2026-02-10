# apps/accounts/views.py

from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login, logout
from django.utils import timezone
from django.db.models import Count
from django.core.cache import cache
from django.conf import settings
from datetime import timedelta
import random
import logging

logger = logging.getLogger(__name__)

from .models import User, AuditLog
from .services import AuthService, TenantService
from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    UserProfileUpdateSerializer,
    PhoneVerificationSerializer,
    UserDetailSerializer,
    AuditLogSerializer
)


# ----------------------------
# User Registration & Auth
# ----------------------------
class RegisterView(generics.CreateAPIView):
    """
    POST /api/v1/auth/register/
    Register a new user account
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens using AuthService
        tokens = AuthService.generate_tokens(user)

        # Create audit log
        AuthService.create_audit_log(
            user=user,
            action='register',
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )

        return Response({
            'message': 'User registered successfully',
            'user': UserSerializer(user).data,
            'tokens': tokens
        }, status=status.HTTP_201_CREATED)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


class LoginView(APIView):
    """
    POST /api/v1/auth/login/
    Authenticate user and return JWT tokens
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        # Update last login and activity
        user.last_login = timezone.now()
        user.last_activity = timezone.now()
        user.save(update_fields=['last_login', 'last_activity'])

        # Login user for session-based auth
        login(request, user)

        # Generate JWT tokens
        tokens = AuthService.generate_tokens(user)

        # Create audit log
        AuthService.create_audit_log(
            user=user,
            action='login',
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT'),
            metadata={'login_method': 'password'}
        )

        return Response({
            'message': 'Login successful',
            'user': UserDetailSerializer(user).data,
            'tokens': tokens
        }, status=status.HTTP_200_OK)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    Logout user and blacklist refresh token
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            # Create audit log
            AuthService.create_audit_log(
                user=request.user,
                action='logout',
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )

            # Blacklist refresh token if provided
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            # Logout user
            logout(request)

            return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)

        except Exception:
            return Response({'error': 'Invalid token or logout failed'}, status=status.HTTP_400_BAD_REQUEST)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


# ----------------------------
# User Profile & Password
# ----------------------------
class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    GET/PUT/PATCH /api/v1/auth/profile/
    Get or update authenticated user's profile
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        return UserDetailSerializer if self.request.method == 'GET' else UserProfileUpdateSerializer

    def get_object(self):
        return self.request.user


class PasswordChangeView(APIView):
    """
    POST /api/v1/auth/password/change/
    Change user password
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({'message': 'Password changed successfully'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def check_password_strength(request):
    """
    POST /api/v1/auth/password/strength/
    Check password strength
    """
    password = request.data.get('password')
    if not password:
        return Response({'error': 'Password is required'}, status=status.HTTP_400_BAD_REQUEST)

    strength = AuthService.check_password_strength(password)
    return Response(strength, status=status.HTTP_200_OK)


# ----------------------------
# Phone Verification
# ----------------------------
class VerifyPhoneView(APIView):
    """
    POST /api/v1/auth/verify-phone/
    Verify user's phone number with code
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PhoneVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        code = serializer.validated_data['verification_code']

        # Verify code from cache/session
        cached_code = cache.get(f'verification_code_{user.id}')
        
        if cached_code and cached_code == code:
            user.is_verified = True
            user.save(update_fields=['is_verified'])
            cache.delete(f'verification_code_{user.id}')
            return Response({
                'message': 'Phone number verified successfully',
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)

        return Response({'error': 'Invalid or expired verification code'}, status=status.HTTP_400_BAD_REQUEST)


class SendVerificationCodeView(APIView):
    """
    POST /api/v1/auth/send-verification-code/
    Send verification code to user's phone
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # Store code in cache for 10 minutes
        cache.set(f'verification_code_{user.id}', code, timeout=600)
        
        # Send SMS via Africa's Talking or Twilio
        try:
            # TODO: Integrate SMS provider
            # For now, log the code (remove in production)
            logger.info(f'Verification code for {user.phone_number}: {code}')
        except Exception as e:
            logger.error(f'Failed to send SMS: {e}')
        
        return Response({
            'message': f'Verification code sent to {user.phone_number}',
            'code': code if settings.DEBUG else None  # Only show in debug mode
        }, status=status.HTTP_200_OK)


# ----------------------------
# User Management (Admin)
# ----------------------------
class UserListView(generics.ListAPIView):
    """
    GET /api/v1/auth/users/
    List all users (admin only)
    """
    queryset = User.objects.all()
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if 'user_type' in params:
            queryset = queryset.filter(user_type=params['user_type'])
        if 'is_verified' in params:
            queryset = queryset.filter(is_verified=params['is_verified'].lower() == 'true')
        if 'is_active' in params:
            queryset = queryset.filter(is_active=params['is_active'].lower() == 'true')
        return queryset.order_by('-date_joined')


class UserDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/auth/users/{id}/
    Get user details by ID (admin only)
    """
    queryset = User.objects.all()
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAdminUser]
    lookup_field = 'id'


@api_view(['GET'])
@permission_classes([permissions.IsAdminUser])
def user_statistics(request):
    """
    GET /api/v1/auth/statistics/
    Get user statistics (admin only)
    """
    now = timezone.now()
    stats = {
        'total_users': User.objects.count(),
        'by_type': User.objects.values('user_type').annotate(count=Count('id')),
        'verified_users': User.objects.filter(is_verified=True).count(),
        'unverified_users': User.objects.filter(is_verified=False).count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'inactive_users': User.objects.filter(is_active=False).count(),
        'new_users_today': User.objects.filter(date_joined__gte=now - timedelta(days=1)).count(),
        'new_users_this_week': User.objects.filter(date_joined__gte=now - timedelta(days=7)).count(),
        'new_users_this_month': User.objects.filter(date_joined__gte=now - timedelta(days=30)).count(),
    }
    return Response(stats, status=status.HTTP_200_OK)


# ----------------------------
# Account Actions
# ----------------------------
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def check_auth_status(request):
    """
    GET /api/v1/auth/status/
    Check if user is authenticated
    """
    user = request.user
    return Response({
        'authenticated': True,
        'user': UserDetailSerializer(user).data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def deactivate_account(request):
    """
    POST /api/v1/auth/deactivate/
    Deactivate user's own account
    """
    user = request.user
    password = request.data.get('password')
    if not password or not user.check_password(password):
        return Response({'error': 'Incorrect or missing password'}, status=status.HTTP_400_BAD_REQUEST)

    user.is_active = False
    user.save(update_fields=['is_active'])
    return Response({'message': 'Account deactivated successfully'}, status=status.HTTP_200_OK)


# ----------------------------
# Audit Logs
# ----------------------------
class AuditLogListView(generics.ListAPIView):
    """
    GET /api/v1/auth/audit-logs/
    List audit logs (own logs for users, all logs for admins)
    """
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = AuditLog.objects.all() if (user.is_staff or user.user_type == 'admin') else AuditLog.objects.filter(user=user)
        params = self.request.query_params
        if 'action' in params:
            queryset = queryset.filter(action=params['action'])
        if 'from_date' in params:
            queryset = queryset.filter(timestamp__gte=params['from_date'])
        if 'to_date' in params:
            queryset = queryset.filter(timestamp__lte=params['to_date'])
        return queryset.order_by('-timestamp')
