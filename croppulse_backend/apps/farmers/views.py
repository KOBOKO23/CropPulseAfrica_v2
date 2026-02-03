# apps/farmers/views.py

from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from django.core.cache import cache

from .models import Farmer, VoiceRegistration, FarmerNote
from .serializers import (
    FarmerSerializer,
    FarmerCreateSerializer,
    FarmerUpdateSerializer,
    FarmerDetailSerializer,
    VoiceRegistrationSerializer,
    VoiceRegistrationCreateSerializer,
    FarmerNoteSerializer,
    FarmerNoteCreateSerializer,
    FarmerStatsSerializer,
    FarmerOnboardingSerializer,
    FarmerSearchResultSerializer
)
from .services import FarmerProfileService, PulseIDGenerator
from core.permissions import IsFarmerOwnerOrAdmin
from apps.accounts.services import AuthService


class FarmerCreateView(generics.CreateAPIView):
    """
    POST /api/v1/farmers/register/
    
    Create a new farmer profile
    """
    serializer_class = FarmerCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        # Check if user already has a farmer profile
        if hasattr(request.user, 'farmer_profile'):
            return Response({
                'error': 'You already have a farmer profile',
                'pulse_id': request.user.farmer_profile.pulse_id
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Add user to serializer context
        serializer = self.get_serializer(
            data=request.data,
            context={'user': request.user}
        )
        serializer.is_valid(raise_exception=True)
        farmer = serializer.save()
        
        # Create audit log
        AuthService.create_audit_log(
            user=request.user,
            action='farmer_profile_created',
            ip_address=self.get_client_ip(request),
            metadata={'pulse_id': farmer.pulse_id}
        )
        
        return Response({
            'message': 'Farmer profile created successfully',
            'farmer': FarmerDetailSerializer(farmer).data
        }, status=status.HTTP_201_CREATED)
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class FarmerListView(generics.ListAPIView):
    """
    GET /api/v1/farmers/
    
    List all farmers (with filters and pagination)
    """
    serializer_class = FarmerSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Farmer.objects.select_related('user').prefetch_related('farms').all()
        
        # Tenant filtering based on user type
        if self.request.user.user_type == 'farmer':
            # Farmers only see their own profile
            queryset = queryset.filter(user=self.request.user)
        elif self.request.user.user_type == 'bank':
            # Banks see only their linked farmers
            from apps.accounts.services import TenantService
            accessible_farmers = TenantService.get_accessible_farmers(self.request.user)
            queryset = accessible_farmers
        # Admins and exporters see all
        
        # Apply filters
        county = self.request.query_params.get('county')
        if county:
            queryset = queryset.filter(county__iexact=county)
        
        crop = self.request.query_params.get('crop')
        if crop:
            queryset = queryset.filter(
                Q(primary_crop__icontains=crop) |
                Q(secondary_crops__icontains=crop)
            )
        
        is_verified = self.request.query_params.get('is_verified')
        if is_verified is not None:
            verified = is_verified.lower() == 'true'
            queryset = queryset.filter(user__is_verified=verified)
        
        onboarded = self.request.query_params.get('onboarded')
        if onboarded is not None:
            is_onboarded = onboarded.lower() == 'true'
            queryset = queryset.filter(onboarding_completed=is_onboarded)
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=active)
        
        fraud_status = self.request.query_params.get('fraud_status')
        if fraud_status:
            queryset = queryset.filter(fraud_status=fraud_status)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(pulse_id__icontains=search) |
                Q(id_number__icontains=search) |
                Q(user__phone_number__icontains=search)
            )
        
        return queryset.order_by('-created_at')


class FarmerDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/farmers/{pulse_id}/
    
    Get detailed farmer information
    """
    serializer_class = FarmerDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pulse_id'
    
    def get_queryset(self):
        queryset = Farmer.objects.select_related('user').prefetch_related(
            'farms',
            'voice_recordings',
            'notes'
        )
        
        # Tenant filtering
        if self.request.user.user_type == 'farmer':
            queryset = queryset.filter(user=self.request.user)
        elif self.request.user.user_type == 'bank':
            from apps.accounts.services import TenantService
            accessible_farmers = TenantService.get_accessible_farmers(self.request.user)
            queryset = accessible_farmers
        
        return queryset
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Update last activity
        request.user.update_last_activity()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class FarmerUpdateView(generics.UpdateAPIView):
    """
    PUT/PATCH /api/v1/farmers/{pulse_id}/update/
    
    Update farmer profile
    """
    serializer_class = FarmerUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsFarmerOwnerOrAdmin]
    lookup_field = 'pulse_id'
    
    def get_queryset(self):
        queryset = Farmer.objects.all()
        
        # Farmers can only update their own profile
        if self.request.user.user_type == 'farmer':
            queryset = queryset.filter(user=self.request.user)
        
        return queryset
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Clear cache
        cache.delete(f'farmer_profile:{instance.user.id}')
        cache.delete(f'farmer_pulse_id:{instance.pulse_id}')
        
        # Create audit log
        AuthService.create_audit_log(
            user=request.user,
            action='profile_update',
            ip_address=self.get_client_ip(request),
            metadata={'pulse_id': instance.pulse_id}
        )
        
        return Response({
            'message': 'Farmer profile updated successfully',
            'farmer': FarmerDetailSerializer(instance).data
        })
    
    def get_client_ip(self, request):
        """Get client IP"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class MyFarmerProfileView(APIView):
    """
    GET /api/v1/farmers/me/
    
    Get current user's farmer profile
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            farmer = Farmer.objects.select_related('user').prefetch_related(
                'farms',
                'voice_recordings'
            ).get(user=request.user)
            
            serializer = FarmerDetailSerializer(farmer)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except Farmer.DoesNotExist:
            return Response({
                'error': 'No farmer profile found for this user',
                'message': 'Please create a farmer profile first',
                'has_profile': False
            }, status=status.HTTP_404_NOT_FOUND)


class VoiceRegistrationCreateView(generics.CreateAPIView):
    """
    POST /api/v1/farmers/voice-registration/
    
    Upload and process voice registration
    """
    serializer_class = VoiceRegistrationCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        voice_registration = serializer.save()
        
        # Create audit log
        AuthService.create_audit_log(
            user=request.user,
            action='voice_registration',
            metadata={
                'voice_registration_id': voice_registration.id,
                'farmer_id': voice_registration.farmer.id
            }
        )
        
        return Response({
            'message': 'Voice registration uploaded successfully. Processing...',
            'data': VoiceRegistrationSerializer(voice_registration).data
        }, status=status.HTTP_201_CREATED)


class VoiceRegistrationListView(generics.ListAPIView):
    """
    GET /api/v1/farmers/{pulse_id}/voice-recordings/
    
    List voice recordings for a farmer
    """
    serializer_class = VoiceRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        pulse_id = self.kwargs.get('pulse_id')
        farmer = get_object_or_404(Farmer, pulse_id=pulse_id)
        
        # Check permissions
        if self.request.user.user_type == 'farmer':
            if farmer.user != self.request.user:
                return VoiceRegistration.objects.none()
        
        return VoiceRegistration.objects.filter(
            farmer=farmer
        ).order_by('-created_at')


class FarmerOnboardingStatusView(APIView):
    """
    GET /api/v1/farmers/{pulse_id}/onboarding-status/
    
    Get onboarding progress for a farmer
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, pulse_id):
        farmer = get_object_or_404(Farmer, pulse_id=pulse_id)
        
        # Check permissions
        if request.user.user_type == 'farmer' and farmer.user != request.user:
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get onboarding progress
        progress = FarmerProfileService.get_onboarding_progress(farmer)
        
        data = {
            'farmer_id': farmer.id,
            'pulse_id': farmer.pulse_id,
            **progress
        }
        
        serializer = FarmerOnboardingSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsFarmerOwnerOrAdmin])
def complete_onboarding(request, pulse_id):
    """
    POST /api/v1/farmers/{pulse_id}/complete-onboarding/
    
    Mark farmer's onboarding as complete
    """
    farmer = get_object_or_404(Farmer, pulse_id=pulse_id)
    
    try:
        FarmerProfileService.complete_onboarding(farmer)
        
        # Create audit log
        AuthService.create_audit_log(
            user=request.user,
            action='onboarding_completed',
            metadata={'pulse_id': farmer.pulse_id}
        )
        
        return Response({
            'message': 'Onboarding completed successfully',
            'farmer': FarmerDetailSerializer(farmer).data
        }, status=status.HTTP_200_OK)
    
    except ValueError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAdminUser])
def farmer_statistics(request):
    """
    GET /api/v1/farmers/statistics/
    
    Get comprehensive farmer statistics (admin only)
    """
    from apps.farms.models import Farm
    
    total_farmers = Farmer.objects.count()
    active_farmers = Farmer.objects.filter(is_active=True).count()
    verified_farmers = Farmer.objects.filter(user__is_verified=True).count()
    onboarded_farmers = Farmer.objects.filter(onboarding_completed=True).count()
    flagged_farmers = Farmer.objects.filter(
        fraud_status__in=['flagged', 'under_review', 'suspended']
    ).count()
    
    # By county
    by_county = list(
        Farmer.objects.values('county')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    
    # By crop
    by_crop = list(
        Farmer.objects.values('primary_crop')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    
    # By fraud status
    by_fraud_status = list(
        Farmer.objects.values('fraud_status')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    # Average farm size
    avg_farm_size = Farm.objects.aggregate(
        avg_size=Avg('size_acres')
    )['avg_size'] or 0
    
    # Average experience
    avg_experience = Farmer.objects.aggregate(
        avg_years=Avg('years_farming')
    )['avg_years'] or 0
    
    data = {
        'total_farmers': total_farmers,
        'active_farmers': active_farmers,
        'verified_farmers': verified_farmers,
        'onboarded_farmers': onboarded_farmers,
        'flagged_farmers': flagged_farmers,
        'by_county': by_county,
        'by_crop': by_crop,
        'by_fraud_status': by_fraud_status,
        'average_farm_size': round(avg_farm_size, 2),
        'average_experience': round(avg_experience, 1)
    }
    
    serializer = FarmerStatsSerializer(data)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def search_farmers(request):
    """
    GET /api/v1/farmers/search/?q=query
    
    Search farmers by name, pulse_id, or phone
    """
    query = request.query_params.get('q', '').strip()
    
    if not query or len(query) < 2:
        return Response({
            'error': 'Search query must be at least 2 characters'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Only admins, banks, and exporters can search
    if request.user.user_type == 'farmer':
        return Response({
            'error': 'Farmers cannot search other farmers'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get filters from query params
    filters = {}
    if request.query_params.get('county'):
        filters['county'] = request.query_params.get('county')
    if request.query_params.get('crop'):
        filters['crop'] = request.query_params.get('crop')
    if request.query_params.get('is_verified'):
        filters['is_verified'] = request.query_params.get('is_verified').lower() == 'true'
    
    # Search using service
    farmers = FarmerProfileService.search_farmers(query, filters)[:20]
    
    # Serialize results
    results = []
    for farmer in farmers:
        results.append({
            'pulse_id': farmer.pulse_id,
            'full_name': farmer.full_name,
            'county': farmer.county,
            'primary_crop': farmer.primary_crop,
            'phone_number': farmer.user.phone_number,
            'is_verified': farmer.user.is_verified,
            'fraud_status': farmer.fraud_status,
            'farms_count': farmer.farms.filter(is_active=True).count()
        })
    
    return Response({
        'query': query,
        'results': results,
        'count': len(results)
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated, IsFarmerOwnerOrAdmin])
def deactivate_farmer(request, pulse_id):
    """
    DELETE /api/v1/farmers/{pulse_id}/deactivate/
    
    Deactivate a farmer profile
    """
    farmer = get_object_or_404(Farmer, pulse_id=pulse_id)
    
    # Require password confirmation
    password = request.data.get('password')
    if not password:
        return Response({
            'error': 'Password is required to deactivate profile'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not farmer.user.check_password(password):
        return Response({
            'error': 'Incorrect password'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Deactivate
    farmer.is_active = False
    farmer.save(update_fields=['is_active'])
    
    # Also deactivate user account
    farmer.user.is_active = False
    farmer.user.save(update_fields=['is_active'])
    
    # Create audit log
    AuthService.create_audit_log(
        user=request.user,
        action='farmer_deactivated',
        metadata={'pulse_id': farmer.pulse_id}
    )
    
    # Clear cache
    cache.delete(f'farmer_profile:{farmer.user.id}')
    cache.delete(f'farmer_pulse_id:{farmer.pulse_id}')
    
    return Response({
        'message': 'Farmer profile deactivated successfully'
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def verify_pulse_id(request, pulse_id):
    """
    GET /api/v1/farmers/verify-pulse-id/{pulse_id}/
    
    Verify if a Pulse ID exists and is active
    """
    farmer = FarmerProfileService.get_farmer_by_pulse_id(pulse_id)
    
    if not farmer:
        return Response({
            'exists': False,
            'message': 'Pulse ID not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'exists': True,
        'pulse_id': farmer.pulse_id,
        'full_name': farmer.full_name,
        'county': farmer.county,
        'is_verified': farmer.user.is_verified,
        'is_active': farmer.is_active,
        'fraud_status': farmer.fraud_status,
        'onboarding_completed': farmer.onboarding_completed
    }, status=status.HTTP_200_OK)


# Farmer Notes Endpoints

class FarmerNoteCreateView(generics.CreateAPIView):
    """
    POST /api/v1/farmers/{pulse_id}/notes/
    
    Create a note for a farmer
    """
    serializer_class = FarmerNoteCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        pulse_id = self.kwargs.get('pulse_id')
        farmer = get_object_or_404(Farmer, pulse_id=pulse_id)
        
        # Add farmer to data
        data = request.data.copy()
        data['farmer'] = farmer.id
        
        serializer = self.get_serializer(
            data=data,
            context={'user': request.user}
        )
        serializer.is_valid(raise_exception=True)
        note = serializer.save()
        
        return Response({
            'message': 'Note created successfully',
            'note': FarmerNoteSerializer(note).data
        }, status=status.HTTP_201_CREATED)


class FarmerNoteListView(generics.ListAPIView):
    """
    GET /api/v1/farmers/{pulse_id}/notes/
    
    List notes for a farmer
    """
    serializer_class = FarmerNoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        pulse_id = self.kwargs.get('pulse_id')
        farmer = get_object_or_404(Farmer, pulse_id=pulse_id)
        
        # Check permissions
        if self.request.user.user_type == 'farmer':
            # Farmers only see non-internal notes
            if farmer.user != self.request.user:
                return FarmerNote.objects.none()
            return farmer.notes.filter(is_internal=False).order_by('-created_at')
        
        # Banks and admins see all notes
        return farmer.notes.select_related('created_by').order_by('-created_at')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def flag_farmer_for_fraud(request, pulse_id):
    """
    POST /api/v1/farmers/{pulse_id}/flag-fraud/
    
    Flag a farmer for fraud review (admin/bank only)
    """
    # Only banks and admins can flag
    if request.user.user_type not in ['bank', 'admin']:
        return Response({
            'error': 'Permission denied'
        }, status=status.HTTP_403_FORBIDDEN)
    
    farmer = get_object_or_404(Farmer, pulse_id=pulse_id)
    reason = request.data.get('reason', 'No reason provided')
    
    # Flag using service
    note = FarmerProfileService.flag_for_fraud(farmer, reason, request.user)
    
    return Response({
        'message': 'Farmer flagged for fraud review',
        'farmer': FarmerSerializer(farmer).data,
        'note': FarmerNoteSerializer(note).data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def clear_farmer_fraud_flag(request, pulse_id):
    """
    POST /api/v1/farmers/{pulse_id}/clear-fraud/
    
    Clear fraud flag for a farmer (admin only)
    """
    farmer = get_object_or_404(Farmer, pulse_id=pulse_id)
    reason = request.data.get('reason', 'Flag cleared by admin')
    
    # Clear using service
    note = FarmerProfileService.clear_fraud_flag(farmer, reason, request.user)
    
    return Response({
        'message': 'Fraud flag cleared',
        'farmer': FarmerSerializer(farmer).data,
        'note': FarmerNoteSerializer(note).data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_farmer_stats_detailed(request, pulse_id):
    """
    GET /api/v1/farmers/{pulse_id}/stats/
    
    Get detailed statistics for a specific farmer
    """
    farmer = get_object_or_404(Farmer, pulse_id=pulse_id)
    
    # Check permissions
    if request.user.user_type == 'farmer' and farmer.user != request.user:
        return Response({
            'error': 'Permission denied'
        }, status=status.HTTP_403_FORBIDDEN)
    
    stats = FarmerProfileService.get_farmer_statistics(farmer)
    
    return Response(stats, status=status.HTTP_200_OK)