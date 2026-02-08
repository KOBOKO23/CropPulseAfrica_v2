"""
Fraud Detection Algorithms

Detects suspicious patterns that may indicate:
- Ghost farms (non-existent farms)
- Duplicate farms (same farm registered multiple times)
- NDVI mismatches (claimed vs. actual crop health)
- Payment fraud
- Identity fraud
"""

from django.db.models import Count, Q
from django.utils import timezone
from django.contrib.gis.measure import Distance
from datetime import timedelta


class FraudDetector:
    """
    Multi-layered fraud detection system.
    """
    
    @staticmethod
    def run_all_checks(farmer, farm):
        """
        Run all fraud detection checks.
        
        Args:
            farmer: Farmer model instance
            farm: Farm model instance
        
        Returns:
            list: List of FraudAlert instances created (if any)
        """
        alerts = []
        
        # Run each check
        alerts.extend(FraudDetector.check_ghost_farm(farm))
        alerts.extend(FraudDetector.check_duplicate_farm(farm))
        alerts.extend(FraudDetector.check_ndvi_mismatch(farm))
        alerts.extend(FraudDetector.check_duplicate_identity(farmer))
        alerts.extend(FraudDetector.check_rapid_applications(farmer))
        
        return alerts
    
    @staticmethod
    def check_ghost_farm(farm):
        """
        Detect ghost farms (farms with no actual vegetation).
        
        Ghost farms show extremely low NDVI across multiple scans.
        
        Args:
            farm: Farm model instance
        
        Returns:
            list: FraudAlert instances (empty if no fraud detected)
        """
        from apps.scoring.models import FraudAlert
        from apps.satellite.models import NDVIHistory
        
        # Get last 3 NDVI scans
        recent_scans = NDVIHistory.objects.filter(
            farm=farm
        ).order_by('-acquisition_date')[:3]
        
        if recent_scans.count() < 2:
            return []  # Not enough data
        
        # Check if all scans show very low NDVI (< 0.3)
        low_ndvi_count = sum(
            1 for scan in recent_scans 
            if scan.ndvi_mean < 0.3
        )
        
        if low_ndvi_count >= 2:
            # Potential ghost farm
            alert, created = FraudAlert.objects.get_or_create(
                farmer=farm.farmer,
                farm=farm,
                alert_type='ghost_farm',
                defaults={
                    'severity': 'high',
                    'description': f'Farm shows persistently low NDVI (<0.3) across {low_ndvi_count} scans',
                    'evidence': {
                        'scans_checked': recent_scans.count(),
                        'low_ndvi_scans': low_ndvi_count,
                        'ndvi_values': [float(s.ndvi_mean) for s in recent_scans]
                    },
                    'score_impact': 300,
                    'blocks_lending': True
                }
            )
            return [alert] if created else []
        
        return []
    
    @staticmethod
    def check_duplicate_farm(farm):
        """
        Detect duplicate farm registrations (same location, different owners).
        
        Args:
            farm: Farm model instance
        
        Returns:
            list: FraudAlert instances
        """
        from apps.scoring.models import FraudAlert
        from apps.farms.models import Farm
        
        # Check for farms within 100m with different owners
        nearby_farms = Farm.objects.filter(
            location__distance_lte=(farm.location, Distance(m=100))
        ).exclude(id=farm.id).exclude(farmer=farm.farmer)
        
        if nearby_farms.exists():
            alert, created = FraudAlert.objects.get_or_create(
                farmer=farm.farmer,
                farm=farm,
                alert_type='duplicate_farm',
                defaults={
                    'severity': 'high',
                    'description': f'Farm location overlaps with {nearby_farms.count()} other farm(s)',
                    'evidence': {
                        'nearby_farms': nearby_farms.count(),
                        'farm_ids': list(nearby_farms.values_list('id', flat=True))
                    },
                    'score_impact': 250,
                    'blocks_lending': True
                }
            )
            return [alert] if created else []
        
        return []
    
    @staticmethod
    def check_ndvi_mismatch(farm):
        """
        Detect NDVI mismatches (farmer claims don't match satellite data).
        
        Args:
            farm: Farm model instance
        
        Returns:
            list: FraudAlert instances
        """
        from apps.scoring.models import FraudAlert
        from apps.satellite.models import NDVIHistory
        
        latest_scan = NDVIHistory.objects.filter(
            farm=farm
        ).order_by('-acquisition_date').first()
        
        if not latest_scan:
            return []
        
        # Check if farmer's crop type claims don't match NDVI patterns
        # High-value crops should show good NDVI
        high_value_crops = ['coffee', 'tea', 'horticulture', 'flowers']
        
        if farm.crop_type and farm.crop_type.lower() in high_value_crops:
            if latest_scan.ndvi_mean < 0.5:
                alert, created = FraudAlert.objects.get_or_create(
                    farmer=farm.farmer,
                    farm=farm,
                    alert_type='ndvi_mismatch',
                    defaults={
                        'severity': 'medium',
                        'description': f'Claimed crop ({farm.crop_type}) shows poor NDVI ({latest_scan.ndvi_mean:.2f})',
                        'evidence': {
                            'claimed_crop': farm.crop_type,
                            'ndvi': float(latest_scan.ndvi_mean),
                            'expected_ndvi_min': 0.5
                        },
                        'score_impact': 150,
                        'blocks_lending': False
                    }
                )
                return [alert] if created else []
        
        return []
    
    @staticmethod
    def check_duplicate_identity(farmer):
        """
        Detect duplicate identities (same phone/ID used multiple times).
        
        Args:
            farmer: Farmer model instance
        
        Returns:
            list: FraudAlert instances
        """
        from apps.scoring.models import FraudAlert
        from apps.farmers.models import Farmer
        
        # Check for duplicate phone numbers
        duplicate_phone = Farmer.objects.filter(
            phone_number=farmer.phone_number
        ).exclude(id=farmer.id)
        
        if duplicate_phone.exists():
            alert, created = FraudAlert.objects.get_or_create(
                farmer=farmer,
                alert_type='duplicate_identity',
                defaults={
                    'severity': 'critical',
                    'description': f'Phone number used by {duplicate_phone.count() + 1} farmers',
                    'evidence': {
                        'phone_number': farmer.phone_number,
                        'duplicate_count': duplicate_phone.count(),
                        'farmer_ids': list(duplicate_phone.values_list('id', flat=True))
                    },
                    'score_impact': 400,
                    'blocks_lending': True
                }
            )
            return [alert] if created else []
        
        return []
    
    @staticmethod
    def check_rapid_applications(farmer):
        """
        Detect suspicious rapid loan applications.
        
        Args:
            farmer: Farmer model instance
        
        Returns:
            list: FraudAlert instances
        """
        from apps.scoring.models import FraudAlert
        from apps.loans.models import LoanApplication
        
        # Check for multiple loan applications in short timeframe
        recent_apps = LoanApplication.objects.filter(
            farmer=farmer,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        if recent_apps >= 3:
            alert, created = FraudAlert.objects.get_or_create(
                farmer=farmer,
                alert_type='rapid_applications',
                defaults={
                    'severity': 'medium',
                    'description': f'{recent_apps} loan applications in 7 days',
                    'evidence': {
                        'applications_count': recent_apps,
                        'timeframe_days': 7
                    },
                    'score_impact': 100,
                    'blocks_lending': False
                }
            )
            return [alert] if created else []
        
        return []
    
    @staticmethod
    def resolve_alert(alert, resolved_by, notes=''):
        """
        Resolve a fraud alert.
        
        Args:
            alert: FraudAlert instance
            resolved_by: User who resolved the alert
            notes: Resolution notes
        
        Returns:
            FraudAlert: Updated alert
        """
        alert.status = 'resolved'
        alert.reviewed_by = resolved_by
        alert.reviewed_at = timezone.now()
        alert.resolution_notes = notes
        alert.save()
        
        return alert
    
    @staticmethod
    def mark_false_positive(alert, reviewed_by, notes=''):
        """
        Mark alert as false positive.
        
        Args:
            alert: FraudAlert instance
            reviewed_by: User who reviewed
            notes: Explanation
        
        Returns:
            FraudAlert: Updated alert
        """
        alert.status = 'false_positive'
        alert.reviewed_by = reviewed_by
        alert.reviewed_at = timezone.now()
        alert.resolution_notes = notes
        alert.score_impact = 0  # Remove penalty
        alert.save()
        
        return alert