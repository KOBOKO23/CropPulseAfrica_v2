# apps/farmers/services/farmer_profile_service.py

from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from apps.farmers.models import Farmer, VoiceRegistration, FarmerNote
from .pulse_id_generator import PulseIDGenerator
from django.db import models


class FarmerProfileService:
    """
    Service class for farmer profile operations
    """
    
    @staticmethod
    @transaction.atomic
    def create_farmer_profile(user, data):
        """
        Create a complete farmer profile
        
        Args:
            user: User instance
            data: Dictionary with farmer data
            
        Returns:
            Farmer: Created farmer instance
            
        Raises:
            ValueError: If validation fails
        """
        # Check if user already has profile
        if hasattr(user, 'farmer_profile'):
            raise ValueError("User already has a farmer profile")
        
        # Generate Pulse ID
        pulse_id = PulseIDGenerator.generate(data['county'])
        
        # Create farmer
        farmer = Farmer.objects.create(
            user=user,
            pulse_id=pulse_id,
            full_name=data['full_name'],
            date_of_birth=data.get('date_of_birth'),
            id_number=data['id_number'],
            county=data['county'],
            sub_county=data['sub_county'],
            nearest_town=data['nearest_town'],
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            years_farming=data['years_farming'],
            primary_crop=data['primary_crop'],
            secondary_crops=data.get('secondary_crops', []),
            farming_method=data.get('farming_method', 'traditional'),
            irrigation_access=data.get('irrigation_access', False),
            photo=data.get('photo'),
            preferred_language=data.get('preferred_language', 'sw'),
            referral_source=data.get('referral_source')
        )
        
        # Clear cache
        cache.delete(f'farmer_profile:{user.id}')
        
        return farmer
    
    @staticmethod
    def get_farmer_by_pulse_id(pulse_id):
        """
        Get farmer by Pulse ID with caching
        
        Args:
            pulse_id: Pulse ID string
            
        Returns:
            Farmer: Farmer instance or None
        """
        cache_key = f'farmer_pulse_id:{pulse_id}'
        farmer = cache.get(cache_key)
        
        if not farmer:
            try:
                farmer = Farmer.objects.select_related('user').get(
                    pulse_id=pulse_id,
                    is_active=True
                )
                cache.set(cache_key, farmer, timeout=3600)  # 1 hour
            except Farmer.DoesNotExist:
                return None
        
        return farmer
    
    @staticmethod
    def get_onboarding_progress(farmer):
        """
        Calculate farmer's onboarding progress
        
        Args:
            farmer: Farmer instance
            
        Returns:
            dict: Onboarding progress details
        """
        steps = {
            'profile_created': True,  # Always true if farmer exists
            'phone_verified': farmer.user.is_verified,
            'voice_registered': farmer.voice_recordings.filter(
                processing_status='completed'
            ).exists(),
            'farm_added': farmer.farms.exists(),
            'photo_uploaded': bool(farmer.photo),
            'location_set': bool(farmer.latitude and farmer.longitude),
        }
        
        completed_steps = sum(steps.values())
        total_steps = len(steps)
        progress_percentage = int((completed_steps / total_steps) * 100)
        
        # Determine next step
        if not steps['phone_verified']:
            next_step = 'verify_phone'
        elif not steps['voice_registered']:
            next_step = 'voice_registration'
        elif not steps['farm_added']:
            next_step = 'add_farm'
        elif not steps['photo_uploaded']:
            next_step = 'upload_photo'
        elif not steps['location_set']:
            next_step = 'set_location'
        else:
            next_step = 'complete'
        
        return {
            'steps': steps,
            'completed': completed_steps,
            'total': total_steps,
            'percentage': progress_percentage,
            'next_step': next_step,
            'is_complete': farmer.onboarding_completed
        }
    
    @staticmethod
    @transaction.atomic
    def complete_onboarding(farmer):
        """
        Mark farmer onboarding as complete with validation
        
        Args:
            farmer: Farmer instance
            
        Returns:
            bool: True if completed successfully
            
        Raises:
            ValueError: If requirements not met
        """
        progress = FarmerProfileService.get_onboarding_progress(farmer)
        
        # Check if all requirements met
        if progress['percentage'] < 100:
            missing_steps = [
                step for step, completed in progress['steps'].items()
                if not completed
            ]
            raise ValueError(
                f"Cannot complete onboarding. Missing steps: {', '.join(missing_steps)}"
            )
        
        farmer.mark_onboarding_complete()
        
        # Clear cache
        cache.delete(f'farmer_profile:{farmer.user.id}')
        cache.delete(f'farmer_pulse_id:{farmer.pulse_id}')
        
        return True
    
    @staticmethod
    def get_farmer_statistics(farmer):
        """
        Get comprehensive farmer statistics
        
        Args:
            farmer: Farmer instance
            
        Returns:
            dict: Statistics
        """
        from apps.farms.models import Farm
        from apps.loans.models import Loan
        from apps.scoring.models import PulseScore
        
        # Farm statistics
        farms = farmer.farms.filter(is_active=True)
        total_farm_size = farms.aggregate(
            total=models.Sum('size_acres')
        )['total'] or 0
        
        # Loan statistics
        loans = Loan.objects.filter(farmer=farmer)
        total_loans = loans.count()
        active_loans = loans.filter(status='active').count()
        total_borrowed = loans.aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        
        # Score history
        latest_score = PulseScore.objects.filter(
            farmer=farmer
        ).order_by('-created_at').first()
        
        return {
            'farms': {
                'count': farms.count(),
                'total_size': float(total_farm_size),
                'average_size': float(total_farm_size / farms.count()) if farms.count() > 0 else 0
            },
            'loans': {
                'total_count': total_loans,
                'active_count': active_loans,
                'total_borrowed': float(total_borrowed)
            },
            'score': {
                'current': latest_score.score if latest_score else None,
                'last_updated': latest_score.created_at if latest_score else None
            },
            'account': {
                'created': farmer.created_at,
                'days_active': (timezone.now() - farmer.created_at).days,
                'onboarded': farmer.onboarding_completed
            }
        }
    
    @staticmethod
    def search_farmers(query, filters=None):
        """
        Search farmers with filters
        
        Args:
            query: Search string
            filters: Dictionary of filters
            
        Returns:
            QuerySet: Filtered farmers
        """
        from django.db.models import Q
        
        farmers = Farmer.objects.select_related('user').filter(is_active=True)
        
        # Apply search query
        if query:
            farmers = farmers.filter(
                Q(full_name__icontains=query) |
                Q(pulse_id__icontains=query) |
                Q(id_number__icontains=query) |
                Q(user__phone_number__icontains=query) |
                Q(user__email__icontains=query)
            )
        
        # Apply filters
        if filters:
            if 'county' in filters:
                farmers = farmers.filter(county__iexact=filters['county'])
            
            if 'crop' in filters:
                farmers = farmers.filter(primary_crop__icontains=filters['crop'])
            
            if 'is_verified' in filters:
                farmers = farmers.filter(user__is_verified=filters['is_verified'])
            
            if 'onboarded' in filters:
                farmers = farmers.filter(onboarding_completed=filters['onboarded'])
            
            if 'fraud_status' in filters:
                farmers = farmers.filter(fraud_status=filters['fraud_status'])
        
        return farmers.order_by('-created_at')
    
    @staticmethod
    @transaction.atomic
    def flag_for_fraud(farmer, reason, flagged_by):
        """
        Flag a farmer for fraud review
        
        Args:
            farmer: Farmer instance
            reason: Reason for flagging
            flagged_by: User who flagged
            
        Returns:
            FarmerNote: Created note
        """
        from django.utils import timezone
        
        # Update fraud status
        farmer.fraud_status = 'flagged'
        farmer.last_fraud_check = timezone.now()
        farmer.save(update_fields=['fraud_status', 'last_fraud_check'])
        
        # Create internal note
        note = FarmerNote.objects.create(
            farmer=farmer,
            created_by=flagged_by,
            note_type='fraud_alert',
            content=f"FRAUD ALERT: {reason}",
            is_internal=True
        )
        
        # Clear cache
        cache.delete(f'farmer_profile:{farmer.user.id}')
        cache.delete(f'farmer_pulse_id:{farmer.pulse_id}')
        
        return note
    
    @staticmethod
    @transaction.atomic
    def clear_fraud_flag(farmer, reason, cleared_by):
        """
        Clear fraud flag for a farmer
        
        Args:
            farmer: Farmer instance
            reason: Reason for clearing
            cleared_by: User who cleared
            
        Returns:
            FarmerNote: Created note
        """
        from django.utils import timezone
        
        # Update fraud status
        farmer.fraud_status = 'verified'
        farmer.last_fraud_check = timezone.now()
        farmer.save(update_fields=['fraud_status', 'last_fraud_check'])
        
        # Create internal note
        note = FarmerNote.objects.create(
            farmer=farmer,
            created_by=cleared_by,
            note_type='fraud_alert',
            content=f"FRAUD FLAG CLEARED: {reason}",
            is_internal=True
        )
        
        # Clear cache
        cache.delete(f'farmer_profile:{farmer.user.id}')
        cache.delete(f'farmer_pulse_id:{farmer.pulse_id}')
        
        return note
    
    @staticmethod
    def add_note(farmer, created_by, note_type, content, is_internal=True):
        """
        Add a note to farmer profile
        
        Args:
            farmer: Farmer instance
            created_by: User creating note
            note_type: Type of note
            content: Note content
            is_internal: Whether note is internal
            
        Returns:
            FarmerNote: Created note
        """
        return FarmerNote.objects.create(
            farmer=farmer,
            created_by=created_by,
            note_type=note_type,
            content=content,
            is_internal=is_internal
        )
    
    @staticmethod
    def get_farmer_notes(farmer, include_internal=True):
        """
        Get notes for a farmer
        
        Args:
            farmer: Farmer instance
            include_internal: Whether to include internal notes
            
        Returns:
            QuerySet: Notes
        """
        notes = farmer.notes.select_related('created_by').all()
        
        if not include_internal:
            notes = notes.filter(is_internal=False)
        
        return notes.order_by('-created_at')