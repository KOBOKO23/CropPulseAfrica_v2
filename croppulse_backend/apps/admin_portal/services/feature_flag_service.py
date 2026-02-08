# apps/admin_portal/services/feature_flag_service.py

from django.core.cache import cache
from django.db.models import Q
import random


class FeatureFlagService:
    """
    Service for managing feature flags and tenant-specific overrides
    """
    
    CACHE_TIMEOUT = 3600  # 1 hour
    
    @staticmethod
    def is_feature_enabled(feature_name, user=None):
        """
        Check if a feature is enabled for a specific user or globally
        
        Args:
            feature_name: Name of the feature flag
            user: User instance (optional, for tenant-specific checks)
            
        Returns:
            bool: True if feature is enabled
        """
        from apps.admin_portal.models import FeatureFlag, TenantFeatureFlag
        
        # Check cache first
        cache_key = f'feature_flag:{feature_name}'
        if user:
            cache_key = f'feature_flag:{feature_name}:user_{user.id}'
        
        cached_value = cache.get(cache_key)
        if cached_value is not None:
            return cached_value
        
        try:
            feature_flag = FeatureFlag.objects.get(name=feature_name)
            
            # Check tenant-specific override if user is bank/exporter
            if user and user.user_type in ['bank', 'exporter']:
                try:
                    tenant_override = TenantFeatureFlag.objects.get(
                        feature_flag=feature_flag,
                        tenant_user=user
                    )
                    result = tenant_override.is_enabled
                    cache.set(cache_key, result, FeatureFlagService.CACHE_TIMEOUT)
                    return result
                except TenantFeatureFlag.DoesNotExist:
                    pass
            
            # Check global flag with rollout percentage
            if feature_flag.is_enabled:
                # If rollout is 100%, always enabled
                if feature_flag.rollout_percentage == 100:
                    result = True
                else:
                    # Use user ID for consistent rollout
                    if user:
                        user_hash = hash(f"{feature_name}:{user.id}") % 100
                        result = user_hash < feature_flag.rollout_percentage
                    else:
                        # Random for anonymous users
                        result = random.randint(0, 99) < feature_flag.rollout_percentage
                
                cache.set(cache_key, result, FeatureFlagService.CACHE_TIMEOUT)
                return result
            
            cache.set(cache_key, False, FeatureFlagService.CACHE_TIMEOUT)
            return False
            
        except FeatureFlag.DoesNotExist:
            # Feature flag doesn't exist, default to disabled
            cache.set(cache_key, False, FeatureFlagService.CACHE_TIMEOUT)
            return False
    
    @staticmethod
    def get_enabled_features(user=None):
        """
        Get all enabled features for a user
        
        Args:
            user: User instance (optional)
            
        Returns:
            list: List of enabled feature names
        """
        from apps.admin_portal.models import FeatureFlag
        
        enabled_features = []
        
        for feature in FeatureFlag.objects.filter(is_enabled=True):
            if FeatureFlagService.is_feature_enabled(feature.name, user):
                enabled_features.append(feature.name)
        
        return enabled_features
    
    @staticmethod
    def set_tenant_override(feature_name, user, is_enabled, custom_config=None):
        """
        Set tenant-specific feature flag override
        
        Args:
            feature_name: Name of the feature flag
            user: User instance (must be bank or exporter)
            is_enabled: Enable or disable the feature
            custom_config: Custom configuration dict
            
        Returns:
            TenantFeatureFlag instance
        """
        from apps.admin_portal.models import FeatureFlag, TenantFeatureFlag
        
        if user.user_type not in ['bank', 'exporter']:
            raise ValueError("User must be a bank or exporter")
        
        feature_flag = FeatureFlag.objects.get(name=feature_name)
        
        tenant_override, created = TenantFeatureFlag.objects.update_or_create(
            feature_flag=feature_flag,
            tenant_user=user,
            defaults={
                'is_enabled': is_enabled,
                'custom_config': custom_config or {}
            }
        )
        
        # Clear cache
        cache_key = f'feature_flag:{feature_name}:user_{user.id}'
        cache.delete(cache_key)
        
        return tenant_override
    
    @staticmethod
    def remove_tenant_override(feature_name, user):
        """
        Remove tenant-specific feature flag override
        
        Args:
            feature_name: Name of the feature flag
            user: User instance
        """
        from apps.admin_portal.models import FeatureFlag, TenantFeatureFlag
        
        try:
            feature_flag = FeatureFlag.objects.get(name=feature_name)
            TenantFeatureFlag.objects.filter(
                feature_flag=feature_flag,
                tenant_user=user
            ).delete()
            
            # Clear cache
            cache_key = f'feature_flag:{feature_name}:user_{user.id}'
            cache.delete(cache_key)
            
        except FeatureFlag.DoesNotExist:
            pass
    
    @staticmethod
    def clear_cache(feature_name=None):
        """
        Clear feature flag cache
        
        Args:
            feature_name: Specific feature to clear, or None to clear all
        """
        if feature_name:
            # Clear specific feature
            cache.delete_pattern(f'feature_flag:{feature_name}:*')
        else:
            # Clear all feature flags
            cache.delete_pattern('feature_flag:*')
    
    @staticmethod
    def create_feature_flag(name, display_name, **kwargs):
        """
        Create a new feature flag
        
        Args:
            name: Unique feature identifier
            display_name: Human-readable name
            **kwargs: Additional parameters
            
        Returns:
            FeatureFlag instance
        """
        from apps.admin_portal.models import FeatureFlag
        
        feature_flag = FeatureFlag.objects.create(
            name=name.lower().replace(' ', '_'),
            display_name=display_name,
            description=kwargs.get('description', ''),
            is_enabled=kwargs.get('is_enabled', False),
            is_beta=kwargs.get('is_beta', False),
            category=kwargs.get('category', 'general'),
            rollout_percentage=kwargs.get('rollout_percentage', 100),
            metadata=kwargs.get('metadata', {})
        )
        
        return feature_flag
    
    @staticmethod
    def update_rollout_percentage(feature_name, percentage):
        """
        Update feature rollout percentage
        
        Args:
            feature_name: Name of the feature flag
            percentage: New rollout percentage (0-100)
        """
        from apps.admin_portal.models import FeatureFlag
        
        if not 0 <= percentage <= 100:
            raise ValueError("Percentage must be between 0 and 100")
        
        feature_flag = FeatureFlag.objects.get(name=feature_name)
        feature_flag.rollout_percentage = percentage
        feature_flag.save()
        
        # Clear cache for this feature
        FeatureFlagService.clear_cache(feature_name)
    
    @staticmethod
    def get_feature_usage_stats(feature_name):
        """
        Get usage statistics for a feature
        
        Args:
            feature_name: Name of the feature flag
            
        Returns:
            dict: Usage statistics
        """
        from apps.admin_portal.models import FeatureFlag, TenantFeatureFlag
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        try:
            feature_flag = FeatureFlag.objects.get(name=feature_name)
            
            # Count tenant overrides
            overrides = TenantFeatureFlag.objects.filter(feature_flag=feature_flag)
            enabled_overrides = overrides.filter(is_enabled=True).count()
            disabled_overrides = overrides.filter(is_enabled=False).count()
            
            # Count potential users (banks and exporters)
            total_tenants = User.objects.filter(
                user_type__in=['bank', 'exporter']
            ).count()
            
            return {
                'feature_name': feature_name,
                'is_enabled_globally': feature_flag.is_enabled,
                'rollout_percentage': feature_flag.rollout_percentage,
                'total_tenants': total_tenants,
                'tenant_overrides': overrides.count(),
                'enabled_overrides': enabled_overrides,
                'disabled_overrides': disabled_overrides,
                'category': feature_flag.category,
                'is_beta': feature_flag.is_beta
            }
            
        except FeatureFlag.DoesNotExist:
            return None
    
    @staticmethod
    def bulk_enable_for_tenants(feature_name, user_ids):
        """
        Enable a feature for multiple tenants
        
        Args:
            feature_name: Name of the feature flag
            user_ids: List of user IDs (banks/exporters)
        """
        from apps.admin_portal.models import FeatureFlag, TenantFeatureFlag
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        feature_flag = FeatureFlag.objects.get(name=feature_name)
        users = User.objects.filter(
            id__in=user_ids,
            user_type__in=['bank', 'exporter']
        )
        
        for user in users:
            TenantFeatureFlag.objects.update_or_create(
                feature_flag=feature_flag,
                tenant_user=user,
                defaults={'is_enabled': True}
            )
            
            # Clear cache
            cache_key = f'feature_flag:{feature_name}:user_{user.id}'
            cache.delete(cache_key)
    
    @staticmethod
    def get_feature_config(feature_name, user=None):
        """
        Get feature configuration including tenant-specific config
        
        Args:
            feature_name: Name of the feature flag
            user: User instance (optional)
            
        Returns:
            dict: Feature configuration
        """
        from apps.admin_portal.models import FeatureFlag, TenantFeatureFlag
        
        try:
            feature_flag = FeatureFlag.objects.get(name=feature_name)
            
            config = {
                'is_enabled': FeatureFlagService.is_feature_enabled(feature_name, user),
                'global_config': feature_flag.metadata,
                'tenant_config': {}
            }
            
            # Get tenant-specific config if applicable
            if user and user.user_type in ['bank', 'exporter']:
                try:
                    tenant_override = TenantFeatureFlag.objects.get(
                        feature_flag=feature_flag,
                        tenant_user=user
                    )
                    config['tenant_config'] = tenant_override.custom_config
                except TenantFeatureFlag.DoesNotExist:
                    pass
            
            return config
            
        except FeatureFlag.DoesNotExist:
            return {'is_enabled': False, 'global_config': {}, 'tenant_config': {}}