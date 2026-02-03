# apps/satellite/services/image_cache.py

from django.core.cache import cache
from django.conf import settings
import hashlib
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


class ImageCacheService:
    """Service for caching satellite imagery and results"""
    
    # Cache timeouts (in seconds)
    SCAN_RESULT_TIMEOUT = 60 * 60 * 24 * 7  # 7 days
    IMAGE_URL_TIMEOUT = 60 * 60 * 24 * 30  # 30 days
    NDVI_HISTORY_TIMEOUT = 60 * 60 * 24  # 24 hours
    FARM_HEALTH_TIMEOUT = 60 * 60  # 1 hour
    
    def __init__(self):
        """Initialize cache service"""
        pass
    
    def generate_cache_key(self, prefix, *args):
        """
        Generate consistent cache key
        
        Args:
            prefix: Key prefix (e.g., 'scan', 'ndvi', 'health')
            *args: Additional key components
        
        Returns:
            str: Cache key
        """
        # Combine all arguments
        key_parts = [str(arg) for arg in args]
        key_string = ':'.join(key_parts)
        
        # Hash for consistent length
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        
        return f"satellite:{prefix}:{key_hash}"
    
    def cache_scan_result(self, farm_id, scan_data):
        """
        Cache satellite scan result
        
        Args:
            farm_id: Farm ID
            scan_data: Scan data dictionary
        
        Returns:
            bool: Success
        """
        key = self.generate_cache_key('scan_result', farm_id)
        
        try:
            cache.set(key, scan_data, self.SCAN_RESULT_TIMEOUT)
            logger.info(f"Cached scan result for farm {farm_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cache scan result: {str(e)}")
            return False
    
    def get_cached_scan_result(self, farm_id):
        """
        Retrieve cached scan result
        
        Args:
            farm_id: Farm ID
        
        Returns:
            dict or None: Cached scan data
        """
        key = self.generate_cache_key('scan_result', farm_id)
        
        try:
            data = cache.get(key)
            if data:
                logger.info(f"Cache hit for scan result: {farm_id}")
            return data
        except Exception as e:
            logger.error(f"Failed to retrieve cached scan: {str(e)}")
            return None
    
    def cache_image_url(self, farm_id, date, image_url, satellite_type='sentinel2'):
        """
        Cache satellite image URL
        
        Args:
            farm_id: Farm ID
            date: Image date
            image_url: Image URL
            satellite_type: Type of satellite
        
        Returns:
            bool: Success
        """
        key = self.generate_cache_key('image_url', farm_id, date, satellite_type)
        
        try:
            cache.set(key, image_url, self.IMAGE_URL_TIMEOUT)
            logger.info(f"Cached image URL for farm {farm_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cache image URL: {str(e)}")
            return False
    
    def get_cached_image_url(self, farm_id, date, satellite_type='sentinel2'):
        """
        Retrieve cached image URL
        
        Args:
            farm_id: Farm ID
            date: Image date
            satellite_type: Type of satellite
        
        Returns:
            str or None: Cached image URL
        """
        key = self.generate_cache_key('image_url', farm_id, date, satellite_type)
        
        try:
            url = cache.get(key)
            if url:
                logger.info(f"Cache hit for image URL: {farm_id}")
            return url
        except Exception as e:
            logger.error(f"Failed to retrieve cached image URL: {str(e)}")
            return None
    
    def cache_ndvi_history(self, farm_id, ndvi_data):
        """
        Cache NDVI history for a farm
        
        Args:
            farm_id: Farm ID
            ndvi_data: List of NDVI history entries
        
        Returns:
            bool: Success
        """
        key = self.generate_cache_key('ndvi_history', farm_id)
        
        try:
            cache.set(key, ndvi_data, self.NDVI_HISTORY_TIMEOUT)
            logger.info(f"Cached NDVI history for farm {farm_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cache NDVI history: {str(e)}")
            return False
    
    def get_cached_ndvi_history(self, farm_id):
        """
        Retrieve cached NDVI history
        
        Args:
            farm_id: Farm ID
        
        Returns:
            list or None: Cached NDVI data
        """
        key = self.generate_cache_key('ndvi_history', farm_id)
        
        try:
            data = cache.get(key)
            if data:
                logger.info(f"Cache hit for NDVI history: {farm_id}")
            return data
        except Exception as e:
            logger.error(f"Failed to retrieve cached NDVI history: {str(e)}")
            return None
    
    def cache_farm_health_summary(self, farm_id, health_data):
        """
        Cache farm health summary
        
        Args:
            farm_id: Farm ID
            health_data: Health summary data
        
        Returns:
            bool: Success
        """
        key = self.generate_cache_key('farm_health', farm_id)
        
        try:
            cache.set(key, health_data, self.FARM_HEALTH_TIMEOUT)
            logger.info(f"Cached health summary for farm {farm_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cache health summary: {str(e)}")
            return False
    
    def get_cached_farm_health_summary(self, farm_id):
        """
        Retrieve cached farm health summary
        
        Args:
            farm_id: Farm ID
        
        Returns:
            dict or None: Cached health data
        """
        key = self.generate_cache_key('farm_health', farm_id)
        
        try:
            data = cache.get(key)
            if data:
                logger.info(f"Cache hit for health summary: {farm_id}")
            return data
        except Exception as e:
            logger.error(f"Failed to retrieve cached health summary: {str(e)}")
            return None
    
    def invalidate_farm_cache(self, farm_id):
        """
        Invalidate all cache entries for a farm
        
        Args:
            farm_id: Farm ID
        
        Returns:
            bool: Success
        """
        try:
            # Delete all related cache keys
            keys_to_delete = [
                self.generate_cache_key('scan_result', farm_id),
                self.generate_cache_key('ndvi_history', farm_id),
                self.generate_cache_key('farm_health', farm_id),
            ]
            
            for key in keys_to_delete:
                cache.delete(key)
            
            logger.info(f"Invalidated cache for farm {farm_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {str(e)}")
            return False
    
    def cache_gee_computation(self, computation_id, result):
        """
        Cache Google Earth Engine computation result
        
        Args:
            computation_id: Unique computation identifier
            result: Computation result
        
        Returns:
            bool: Success
        """
        key = self.generate_cache_key('gee_computation', computation_id)
        
        try:
            # Cache for 24 hours
            cache.set(key, result, 60 * 60 * 24)
            logger.info(f"Cached GEE computation: {computation_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cache GEE computation: {str(e)}")
            return False
    
    def get_cached_gee_computation(self, computation_id):
        """
        Retrieve cached GEE computation result
        
        Args:
            computation_id: Unique computation identifier
        
        Returns:
            dict or None: Cached result
        """
        key = self.generate_cache_key('gee_computation', computation_id)
        
        try:
            result = cache.get(key)
            if result:
                logger.info(f"Cache hit for GEE computation: {computation_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to retrieve cached GEE computation: {str(e)}")
            return None
    
    def get_cache_stats(self):
        """
        Get cache statistics
        
        Returns:
            dict: Cache statistics
        """
        try:
            # This is a simplified version
            # In production, you'd want more detailed stats from Redis
            return {
                'cache_backend': 'redis' if 'redis' in settings.CACHES.get('default', {}).get('BACKEND', '') else 'locmem',
                'scan_result_timeout': self.SCAN_RESULT_TIMEOUT,
                'image_url_timeout': self.IMAGE_URL_TIMEOUT,
                'ndvi_history_timeout': self.NDVI_HISTORY_TIMEOUT,
                'farm_health_timeout': self.FARM_HEALTH_TIMEOUT,
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {str(e)}")
            return {}
    
    def warm_cache_for_farm(self, farm):
        """
        Pre-warm cache with farm data
        
        Args:
            farm: Farm instance
        
        Returns:
            dict: Warming results
        """
        from apps.satellite.models import SatelliteScan, NDVIHistory
        
        results = {
            'farm_id': farm.farm_id,
            'scan_cached': False,
            'ndvi_cached': False,
            'health_cached': False
        }
        
        try:
            # Cache latest scan
            latest_scan = SatelliteScan.objects.filter(
                farm=farm
            ).order_by('-acquisition_date').first()
            
            if latest_scan:
                scan_data = {
                    'scan_id': latest_scan.scan_id,
                    'ndvi': latest_scan.ndvi,
                    'health_status': latest_scan.crop_health_status,
                    'acquisition_date': latest_scan.acquisition_date.isoformat()
                }
                results['scan_cached'] = self.cache_scan_result(farm.farm_id, scan_data)
            
            # Cache NDVI history
            ndvi_history = list(
                NDVIHistory.objects.filter(farm=farm).order_by('-date')[:30].values()
            )
            
            if ndvi_history:
                results['ndvi_cached'] = self.cache_ndvi_history(farm.farm_id, ndvi_history)
            
            logger.info(f"Warmed cache for farm {farm.farm_id}")
            
        except Exception as e:
            logger.error(f"Failed to warm cache for farm {farm.farm_id}: {str(e)}")
        
        return results