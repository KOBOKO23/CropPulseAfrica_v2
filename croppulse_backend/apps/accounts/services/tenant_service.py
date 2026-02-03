# apps/accounts/services/tenant_service.py

from django.db.models import Q
from django.core.cache import cache


class TenantService:
    """
    Service class for multi-tenant operations
    Handles bank/exporter isolation and data filtering
    """
    
    @staticmethod
    def get_bank_farmers(bank_user):
        """
        Get all farmers associated with a specific bank
        
        Args:
            bank_user: Bank user instance
            
        Returns:
            QuerySet: Farmers linked to this bank
        """
        from apps.farmers.models import Farmer
        from apps.banks.models import BankFarmerLink
        
        # Get farmer IDs linked to this bank
        linked_farmer_ids = BankFarmerLink.objects.filter(
            bank__user=bank_user,
            is_active=True
        ).values_list('farmer_id', flat=True)
        
        return Farmer.objects.filter(id__in=linked_farmer_ids)
    
    @staticmethod
    def get_exporter_farmers(exporter_user):
        """
        Get all farmers associated with a specific exporter
        
        Args:
            exporter_user: Exporter user instance
            
        Returns:
            QuerySet: Farmers linked to this exporter
        """
        from apps.farmers.models import Farmer
        from apps.exporters.models import ExporterFarmerLink
        
        linked_farmer_ids = ExporterFarmerLink.objects.filter(
            exporter__user=exporter_user,
            is_active=True
        ).values_list('farmer_id', flat=True)
        
        return Farmer.objects.filter(id__in=linked_farmer_ids)
    
    @staticmethod
    def can_access_farmer(user, farmer):
        """
        Check if user can access specific farmer data
        
        Args:
            user: User instance
            farmer: Farmer instance
            
        Returns:
            bool: True if access allowed
        """
        # Admins can access all
        if user.user_type == 'admin':
            return True
        
        # Farmers can access their own data
        if user.user_type == 'farmer':
            return farmer.user == user
        
        # Banks can access linked farmers
        if user.user_type == 'bank':
            from apps.banks.models import BankFarmerLink
            return BankFarmerLink.objects.filter(
                bank__user=user,
                farmer=farmer,
                is_active=True
            ).exists()
        
        # Exporters can access linked farmers
        if user.user_type == 'exporter':
            from apps.exporters.models import ExporterFarmerLink
            return ExporterFarmerLink.objects.filter(
                exporter__user=user,
                farmer=farmer,
                is_active=True
            ).exists()
        
        return False
    
    @staticmethod
    def link_farmer_to_bank(farmer, bank):
        """
        Create a link between farmer and bank
        
        Args:
            farmer: Farmer instance
            bank: Bank instance
            
        Returns:
            BankFarmerLink: Created link
        """
        from apps.banks.models import BankFarmerLink
        
        link, created = BankFarmerLink.objects.get_or_create(
            farmer=farmer,
            bank=bank,
            defaults={'is_active': True}
        )
        
        if not created and not link.is_active:
            link.is_active = True
            link.save()
        
        # Clear cache
        cache_key = f'bank_farmers:{bank.id}'
        cache.delete(cache_key)
        
        return link
    
    @staticmethod
    def unlink_farmer_from_bank(farmer, bank):
        """
        Remove link between farmer and bank
        
        Args:
            farmer: Farmer instance
            bank: Bank instance
        """
        from apps.banks.models import BankFarmerLink
        
        BankFarmerLink.objects.filter(
            farmer=farmer,
            bank=bank
        ).update(is_active=False)
        
        # Clear cache
        cache_key = f'bank_farmers:{bank.id}'
        cache.delete(cache_key)
    
    @staticmethod
    def get_accessible_farmers(user):
        """
        Get all farmers accessible to a user based on their role
        
        Args:
            user: User instance
            
        Returns:
            QuerySet: Accessible farmers
        """
        from apps.farmers.models import Farmer
        
        # Admins see all
        if user.user_type == 'admin':
            return Farmer.objects.all()
        
        # Farmers see only themselves
        if user.user_type == 'farmer':
            return Farmer.objects.filter(user=user)
        
        # Banks see linked farmers
        if user.user_type == 'bank':
            return TenantService.get_bank_farmers(user)
        
        # Exporters see linked farmers
        if user.user_type == 'exporter':
            return TenantService.get_exporter_farmers(user)
        
        # Default: no access
        return Farmer.objects.none()
    
    @staticmethod
    def filter_by_tenant(queryset, user, tenant_field='farmer'):
        """
        Filter a queryset by tenant (bank/exporter)
        
        Args:
            queryset: Django QuerySet
            user: User instance
            tenant_field: Field name that links to farmer (default: 'farmer')
            
        Returns:
            QuerySet: Filtered queryset
        """
        # Admins see all
        if user.user_type == 'admin':
            return queryset
        
        # Farmers see only their own data
        if user.user_type == 'farmer':
            filter_kwargs = {f'{tenant_field}__user': user}
            return queryset.filter(**filter_kwargs)
        
        # Banks see linked farmers' data
        if user.user_type == 'bank':
            accessible_farmers = TenantService.get_bank_farmers(user)
            filter_kwargs = {f'{tenant_field}__in': accessible_farmers}
            return queryset.filter(**filter_kwargs)
        
        # Exporters see linked farmers' data
        if user.user_type == 'exporter':
            accessible_farmers = TenantService.get_exporter_farmers(user)
            filter_kwargs = {f'{tenant_field}__in': accessible_farmers}
            return queryset.filter(**filter_kwargs)
        
        # Default: no data
        return queryset.none()
    
    @staticmethod
    def get_tenant_statistics(user):
        """
        Get statistics for a tenant (bank/exporter)
        
        Args:
            user: User instance
            
        Returns:
            dict: Statistics
        """
        if user.user_type == 'bank':
            farmers = TenantService.get_bank_farmers(user)
            
            return {
                'total_farmers': farmers.count(),
                'verified_farmers': farmers.filter(user__is_verified=True).count(),
                'active_loans': farmers.filter(loans__status='active').count(),
                'default_rate': TenantService._calculate_default_rate(farmers)
            }
        
        elif user.user_type == 'exporter':
            farmers = TenantService.get_exporter_farmers(user)
            
            return {
                'total_farmers': farmers.count(),
                'compliant_farmers': farmers.filter(
                    compliance_certificates__is_valid=True
                ).distinct().count(),
                'export_ready': farmers.filter(
                    compliance_certificates__is_valid=True,
                    compliance_certificates__eudr_compliant=True
                ).distinct().count()
            }
        
        return {}
    
    @staticmethod
    def _calculate_default_rate(farmers):
        """
        Calculate default rate for a set of farmers
        
        Args:
            farmers: QuerySet of farmers
            
        Returns:
            float: Default rate as percentage
        """
        from apps.loans.models import Loan
        
        total_loans = Loan.objects.filter(farmer__in=farmers).count()
        
        if total_loans == 0:
            return 0.0
        
        defaulted_loans = Loan.objects.filter(
            farmer__in=farmers,
            status='defaulted'
        ).count()
        
        return round((defaulted_loans / total_loans) * 100, 2)