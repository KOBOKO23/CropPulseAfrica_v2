# apps/admin_portal/services/global_settings.py

from django.core.cache import cache
import json


class GlobalSettingsService:
    """
    Service for managing global system settings
    """
    
    CACHE_TIMEOUT = 7200  # 2 hours
    CACHE_PREFIX = 'global_setting'
    
    @staticmethod
    def get_setting(key, default=None, use_cache=True):
        """
        Get a global setting value
        
        Args:
            key: Setting key
            default: Default value if setting doesn't exist
            use_cache: Whether to use cache
            
        Returns:
            Parsed setting value or default
        """
        from apps.admin_portal.models import GlobalSettings
        
        if use_cache:
            cache_key = f'{GlobalSettingsService.CACHE_PREFIX}:{key}'
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
        
        try:
            setting = GlobalSettings.objects.get(key=key)
            value = setting.get_value()
            
            if use_cache:
                cache.set(cache_key, value, GlobalSettingsService.CACHE_TIMEOUT)
            
            return value
            
        except GlobalSettings.DoesNotExist:
            return default
    
    @staticmethod
    def set_setting(key, value, value_type='string', category='system', 
                   description='', is_sensitive=False, is_editable=True):
        """
        Set a global setting
        
        Args:
            key: Setting key
            value: Setting value
            value_type: Type of value (string, integer, float, boolean, json)
            category: Setting category
            description: Setting description
            is_sensitive: Mark as sensitive
            is_editable: Can be edited
            
        Returns:
            GlobalSettings instance
        """
        from apps.admin_portal.models import GlobalSettings
        
        # Convert value to string based on type
        if value_type == 'json':
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value)
            else:
                value_str = str(value)
        elif value_type == 'boolean':
            value_str = str(bool(value)).lower()
        else:
            value_str = str(value)
        
        setting, created = GlobalSettings.objects.update_or_create(
            key=key,
            defaults={
                'value': value_str,
                'value_type': value_type,
                'category': category,
                'description': description,
                'is_sensitive': is_sensitive,
                'is_editable': is_editable
            }
        )
        
        # Clear cache
        cache_key = f'{GlobalSettingsService.CACHE_PREFIX}:{key}'
        cache.delete(cache_key)
        
        return setting
    
    @staticmethod
    def delete_setting(key):
        """
        Delete a global setting
        
        Args:
            key: Setting key
        """
        from apps.admin_portal.models import GlobalSettings
        
        GlobalSettings.objects.filter(key=key).delete()
        
        # Clear cache
        cache_key = f'{GlobalSettingsService.CACHE_PREFIX}:{key}'
        cache.delete(cache_key)
    
    @staticmethod
    def get_settings_by_category(category):
        """
        Get all settings in a category
        
        Args:
            category: Category name
            
        Returns:
            QuerySet of GlobalSettings
        """
        from apps.admin_portal.models import GlobalSettings
        
        return GlobalSettings.objects.filter(category=category)
    
    @staticmethod
    def get_all_settings(include_sensitive=False):
        """
        Get all settings as a dictionary
        
        Args:
            include_sensitive: Include sensitive settings
            
        Returns:
            dict: All settings
        """
        from apps.admin_portal.models import GlobalSettings
        
        queryset = GlobalSettings.objects.all()
        
        if not include_sensitive:
            queryset = queryset.filter(is_sensitive=False)
        
        settings_dict = {}
        for setting in queryset:
            settings_dict[setting.key] = setting.get_value()
        
        return settings_dict
    
    @staticmethod
    def bulk_update_settings(settings_dict):
        """
        Update multiple settings at once
        
        Args:
            settings_dict: Dict of {key: value} pairs
            
        Returns:
            int: Number of settings updated
        """
        from apps.admin_portal.models import GlobalSettings
        
        updated_count = 0
        
        for key, value in settings_dict.items():
            try:
                setting = GlobalSettings.objects.get(key=key)
                
                if not setting.is_editable:
                    continue
                
                # Determine value type and convert
                if setting.value_type == 'json':
                    if isinstance(value, (dict, list)):
                        value_str = json.dumps(value)
                    else:
                        value_str = str(value)
                elif setting.value_type == 'boolean':
                    value_str = str(bool(value)).lower()
                else:
                    value_str = str(value)
                
                setting.value = value_str
                setting.save()
                
                # Clear cache
                cache_key = f'{GlobalSettingsService.CACHE_PREFIX}:{key}'
                cache.delete(cache_key)
                
                updated_count += 1
                
            except GlobalSettings.DoesNotExist:
                pass
        
        return updated_count
    
    @staticmethod
    def clear_cache(key=None):
        """
        Clear settings cache
        
        Args:
            key: Specific key to clear, or None to clear all
        """
        if key:
            cache_key = f'{GlobalSettingsService.CACHE_PREFIX}:{key}'
            cache.delete(cache_key)
        else:
            # Clear all settings
            cache.delete_pattern(f'{GlobalSettingsService.CACHE_PREFIX}:*')
    
    @staticmethod
    def initialize_default_settings():
        """
        Initialize default system settings
        """
        defaults = [
            # API Settings
            {
                'key': 'api.rate_limit.default',
                'value': '1000',
                'value_type': 'integer',
                'category': 'api',
                'description': 'Default API rate limit per hour'
            },
            {
                'key': 'api.timeout.default',
                'value': '30',
                'value_type': 'integer',
                'category': 'api',
                'description': 'Default API timeout in seconds'
            },
            {
                'key': 'api.max_request_size',
                'value': '10485760',
                'value_type': 'integer',
                'category': 'api',
                'description': 'Maximum request size in bytes (10MB)'
            },
            
            # Security Settings
            {
                'key': 'security.password_min_length',
                'value': '8',
                'value_type': 'integer',
                'category': 'security',
                'description': 'Minimum password length'
            },
            {
                'key': 'security.session_timeout',
                'value': '3600',
                'value_type': 'integer',
                'category': 'security',
                'description': 'Session timeout in seconds'
            },
            {
                'key': 'security.max_login_attempts',
                'value': '5',
                'value_type': 'integer',
                'category': 'security',
                'description': 'Maximum login attempts before lockout'
            },
            
            # Notification Settings
            {
                'key': 'notifications.email_enabled',
                'value': 'true',
                'value_type': 'boolean',
                'category': 'notifications',
                'description': 'Enable email notifications'
            },
            {
                'key': 'notifications.sms_enabled',
                'value': 'true',
                'value_type': 'boolean',
                'category': 'notifications',
                'description': 'Enable SMS notifications'
            },
            
            # Scoring Settings
            {
                'key': 'scoring.min_score',
                'value': '0',
                'value_type': 'integer',
                'category': 'scoring',
                'description': 'Minimum credit score'
            },
            {
                'key': 'scoring.max_score',
                'value': '100',
                'value_type': 'integer',
                'category': 'scoring',
                'description': 'Maximum credit score'
            },
            {
                'key': 'scoring.auto_recalculate',
                'value': 'true',
                'value_type': 'boolean',
                'category': 'scoring',
                'description': 'Auto-recalculate scores periodically'
            },
            
            # Limits
            {
                'key': 'limits.max_farms_per_farmer',
                'value': '10',
                'value_type': 'integer',
                'category': 'limits',
                'description': 'Maximum farms per farmer'
            },
            {
                'key': 'limits.max_file_upload_size',
                'value': '5242880',
                'value_type': 'integer',
                'category': 'limits',
                'description': 'Maximum file upload size in bytes (5MB)'
            },
            
            # System Settings
            {
                'key': 'system.maintenance_mode',
                'value': 'false',
                'value_type': 'boolean',
                'category': 'system',
                'description': 'Enable maintenance mode'
            },
            {
                'key': 'system.debug_mode',
                'value': 'false',
                'value_type': 'boolean',
                'category': 'system',
                'description': 'Enable debug mode'
            },
        ]
        
        for setting_data in defaults:
            GlobalSettingsService.set_setting(
                key=setting_data['key'],
                value=setting_data['value'],
                value_type=setting_data['value_type'],
                category=setting_data['category'],
                description=setting_data['description']
            )
    
    @staticmethod
    def export_settings():
        """
        Export all settings as JSON
        
        Returns:
            str: JSON string of all settings
        """
        from apps.admin_portal.models import GlobalSettings
        
        settings = []
        for setting in GlobalSettings.objects.all():
            settings.append({
                'key': setting.key,
                'value': setting.value,
                'value_type': setting.value_type,
                'category': setting.category,
                'description': setting.description,
                'is_sensitive': setting.is_sensitive,
                'is_editable': setting.is_editable
            })
        
        return json.dumps(settings, indent=2)
    
    @staticmethod
    def import_settings(json_data):
        """
        Import settings from JSON
        
        Args:
            json_data: JSON string or dict of settings
            
        Returns:
            int: Number of settings imported
        """
        if isinstance(json_data, str):
            settings = json.loads(json_data)
        else:
            settings = json_data
        
        imported_count = 0
        
        for setting_data in settings:
            GlobalSettingsService.set_setting(
                key=setting_data['key'],
                value=setting_data['value'],
                value_type=setting_data.get('value_type', 'string'),
                category=setting_data.get('category', 'system'),
                description=setting_data.get('description', ''),
                is_sensitive=setting_data.get('is_sensitive', False),
                is_editable=setting_data.get('is_editable', True)
            )
            imported_count += 1
        
        return imported_count