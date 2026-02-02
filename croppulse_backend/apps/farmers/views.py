# apps/farmers/views.py

from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from .models import Farmer, VoiceRegistration
from .serializers import (
    FarmerSerializer,
    FarmerCreateSerializer,
    FarmerUpdateSerializer,
    FarmerDetailSerializer,
    VoiceRegistrationSerializer,
    VoiceRegistrationCreateSerializer,
    FarmerStatsSerializer,
    FarmerOnboardingSerializer
)
from core.permissions import IsFarmerOwnerOrAdmin


class FarmerCreateView(generics.CreateAPIView):
    """
    POST /api/v1/farmers/register/
    
    Create a new farmer profile
    """
    serializer_class = FarmerCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        # Add user to serializer context
        serializer = self.get_serializer(
            data=request.data,
            context={'user': request.user}
        )
        serializer.is_valid(raise_exception=True)
        farmer = serializer.save()
        
        return Response({
            'message': 'Farmer profile created successfully',
            'farmer': FarmerDetailSerializer(farmer).data
        }, status=status.HTTP_201_CREATED)


class FarmerListView(generics.ListAPIView):
    """
    GET /api/v1/farmers/
    
    List all farmers (with filters)
    """
    serializer_class = FarmerSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Farmer.objects.select_related('user').all()
        
        # If regular farmer, only show their own profile
        if self.request.user.user_type == 'farmer':
            queryset = queryset.filter(user=self.request.user)
        
        # Filter by county
        county = self.request.query_params.get('county')
        if county:
            queryset = queryset.filter(county__iexact=county)
        
        # Filter by crop
        crop = self.request.query_params.get('crop')
        if crop:
            queryset = queryset.filter(primary_crop__icontains=crop)
        
        # Filter by verification status
        is_verified = self.request.query_params.get('is_verified')
        if is_verified is not None:
            verified = is_verified.lower() == 'true'
            queryset = queryset.filter(user__is_verified=verified)
        
        # Filter by onboarding status
        onboarded = self.request.query_params.get('onboarded')
        if onboarded is not None:
            is_onboarded = onboarded.lower() == 'true'
            queryset = queryset.filter(onboarding_completed=is_onboarded)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=active)
        
        # Search by name or pulse_id
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(pulse_id__icontains=search) |
                Q(id_number__icontains=search)
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
        queryset = Farmer.objects.select_related('user').prefetch_related('farms')
        
        # Farmers can only view their own profile
        if self.request.user.user_type == 'farmer':
            queryset = queryset.filter(user=self.request.user)
        
        return queryset


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
        
        return Response({
            'message': 'Farmer profile updated successfully',
            'farmer': FarmerDetailSerializer(instance).data
        })


class MyFarmerProfileView(APIView):
    """
    GET /api/v1/farmers/me/
    
    Get current user's farmer profile
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            farmer = Farmer.objects.get(user=request.user)
            serializer = FarmerDetailSerializer(farmer)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Farmer.DoesNotExist:
            return Response({
                'error': 'No farmer profile found for this user',
                'message': 'Please create a farmer profile first'
            }, status=status.HTTP_404_NOT_FOUND)


class VoiceRegistrationCreateView(generics.CreateAPIView):
    """
    POST /api/v1/farmers/voice-registration/
    
    Upload and process voice registration
    """
    serializer_class = VoiceRegistrationCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        voice_registration = serializer.save()
        
        return Response({
            'message': 'Voice registration processed successfully',
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
        
        return VoiceRegistration.objects.filter(farmer=farmer).order_by('-created_at')


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
        
        # Calculate onboarding steps
        steps = {
            'profile_created': True,  # If farmer exists, this is done
            'phone_verified': farmer.user.is_verified,
            'voice_registered': farmer.voice_recordings.exists(),
            'farm_added': farmer.farms.exists(),
            'photo_uploaded': bool(farmer.photo),
        }
        
        completed_steps = sum(steps.values())
        total_steps = len(steps)
        progress = int((completed_steps / total_steps) * 100)
        
        # Determine next step
        if not steps['phone_verified']:
            next_step = 'Verify your phone number'
        elif not steps['voice_registered']:
            next_step = 'Complete voice registration'
        elif not steps['farm_added']:
            next_step = 'Add your farm location'
        elif not steps['photo_uploaded']:
            next_step = 'Upload your photo'
        else:
            next_step = 'Onboarding complete!'
        
        data = {
            'farmer_id': farmer.id,
            'pulse_id': farmer.pulse_id,
            'steps_completed': steps,
            'progress_percentage': progress,
            'next_step': next_step,
            'is_complete': farmer.onboarding_completed
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
    
    # Verify all required steps are done
    if not farmer.user.is_verified:
        return Response({
            'error': 'Phone number must be verified before completing onboarding'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not farmer.voice_recordings.exists():
        return Response({
            'error': 'Voice registration required before completing onboarding'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not farmer.farms.exists():
        return Response({
            'error': 'At least one farm must be added before completing onboarding'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Mark as complete
    farmer.onboarding_completed = True
    farmer.save(update_fields=['onboarding_completed'])
    
    return Response({
        'message': 'Onboarding completed successfully',
        'farmer': FarmerDetailSerializer(farmer).data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAdminUser])
def farmer_statistics(request):
    """
    GET /api/v1/farmers/statistics/
    
    Get farmer statistics (admin only)
    """
    from apps.farms.models import Farm
    
    total_farmers = Farmer.objects.count()
    active_farmers = Farmer.objects.filter(is_active=True).count()
    verified_farmers = Farmer.objects.filter(user__is_verified=True).count()
    onboarded_farmers = Farmer.objects.filter(onboarding_completed=True).count()
    
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
        'by_county': by_county,
        'by_crop': by_crop,
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
    
    # Only admins and banks can search all farmers
    if request.user.user_type == 'farmer':
        return Response({
            'error': 'Farmers cannot search other farmers'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Search
    farmers = Farmer.objects.filter(
        Q(full_name__icontains=query) |
        Q(pulse_id__icontains=query) |
        Q(user__phone_number__icontains=query) |
        Q(id_number__icontains=query)
    ).select_related('user').prefetch_related('farms')[:20]
    
    results = []
    for farmer in farmers:
        results.append({
            'pulse_id': farmer.pulse_id,
            'full_name': farmer.full_name,
            'county': farmer.county,
            'primary_crop': farmer.primary_crop,
            'phone_number': farmer.user.phone_number,
            'is_verified': farmer.user.is_verified,
            'farms_count': farmer.farms.count()
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
    try:
        farmer = Farmer.objects.select_related('user').get(pulse_id=pulse_id)
        
        return Response({
            'exists': True,
            'pulse_id': farmer.pulse_id,
            'full_name': farmer.full_name,
            'county': farmer.county,
            'is_verified': farmer.user.is_verified,
            'is_active': farmer.is_active,
            'onboarding_completed': farmer.onboarding_completed
        }, status=status.HTTP_200_OK)
    
    except Farmer.DoesNotExist:
        return Response({
            'exists': False,
            'message': 'Pulse ID not found'
        }, status=status.HTTP_404_NOT_FOUND)