# apps/accounts/views.py

from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login, logout
from django.utils import timezone
from .models import User
from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    UserProfileUpdateSerializer,
    PhoneVerificationSerializer,
    UserDetailSerializer
)


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
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'User registered successfully',
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


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
        
        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        # Login user (for session-based auth if needed)
        login(request, user)
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Login successful',
            'user': UserDetailSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    
    Logout user and blacklist refresh token
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            # Get refresh token from request
            refresh_token = request.data.get('refresh_token')
            
            if refresh_token:
                # Blacklist the refresh token
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            # Logout user from session
            logout(request)
            
            return Response({
                'message': 'Logout successful'
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                'error': 'Invalid token or logout failed'
            }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    GET /api/v1/auth/profile/
    PUT /api/v1/auth/profile/
    PATCH /api/v1/auth/profile/
    
    Get or update authenticated user's profile
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return UserDetailSerializer
        return UserProfileUpdateSerializer
    
    def get_object(self):
        return self.request.user


class PasswordChangeView(APIView):
    """
    POST /api/v1/auth/password/change/
    
    Change user password
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)


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
        phone_number = serializer.validated_data['phone_number']
        verification_code = serializer.validated_data['verification_code']
        
        # TODO: Implement actual SMS verification logic
        # For now, accept code '123456' as valid for testing
        if verification_code == '123456':
            user.is_verified = True
            user.save(update_fields=['is_verified'])
            
            return Response({
                'message': 'Phone number verified successfully',
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'error': 'Invalid verification code'
        }, status=status.HTTP_400_BAD_REQUEST)


class SendVerificationCodeView(APIView):
    """
    POST /api/v1/auth/send-verification-code/
    
    Send verification code to user's phone
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        # TODO: Implement actual SMS sending logic using AfricasTalking or Twilio
        # For now, return a mock success response
        
        # Generate 6-digit code
        import random
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # In production, send SMS here and store code in cache/database
        # For testing, just return success
        
        return Response({
            'message': f'Verification code sent to {user.phone_number}',
            'code': code  # Remove this in production!
        }, status=status.HTTP_200_OK)


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
        
        # Filter by user type if provided
        user_type = self.request.query_params.get('user_type')
        if user_type:
            queryset = queryset.filter(user_type=user_type)
        
        # Filter by verification status
        is_verified = self.request.query_params.get('is_verified')
        if is_verified is not None:
            queryset = queryset.filter(is_verified=is_verified.lower() == 'true')
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
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
@permission_classes([permissions.IsAuthenticated])
def check_auth_status(request):
    """
    GET /api/v1/auth/status/
    
    Check if user is authenticated and get basic info
    """
    user = request.user
    
    return Response({
        'authenticated': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'phone_number': user.phone_number,
            'user_type': user.user_type,
            'is_verified': user.is_verified,
            'is_active': user.is_active
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def deactivate_account(request):
    """
    POST /api/v1/auth/deactivate/
    
    Deactivate user's own account
    """
    user = request.user
    
    # Require password confirmation
    password = request.data.get('password')
    if not password:
        return Response({
            'error': 'Password is required to deactivate account'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not user.check_password(password):
        return Response({
            'error': 'Incorrect password'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Deactivate account
    user.is_active = False
    user.save(update_fields=['is_active'])
    
    return Response({
        'message': 'Account deactivated successfully'
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAdminUser])
def user_statistics(request):
    """
    GET /api/v1/auth/statistics/
    
    Get user statistics (admin only)
    """
    from django.db.models import Count, Q
    from datetime import timedelta
    
    now = timezone.now()
    
    stats = {
        'total_users': User.objects.count(),
        'by_type': User.objects.values('user_type').annotate(count=Count('id')),
        'verified_users': User.objects.filter(is_verified=True).count(),
        'unverified_users': User.objects.filter(is_verified=False).count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'inactive_users': User.objects.filter(is_active=False).count(),
        'new_users_today': User.objects.filter(
            date_joined__gte=now - timedelta(days=1)
        ).count(),
        'new_users_this_week': User.objects.filter(
            date_joined__gte=now - timedelta(days=7)
        ).count(),
        'new_users_this_month': User.objects.filter(
            date_joined__gte=now - timedelta(days=30)
        ).count(),
    }
    
    return Response(stats, status=status.HTTP_200_OK)