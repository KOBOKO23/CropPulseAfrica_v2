# apps/satellite/services/sentinel_service.py

import ee
from datetime import datetime, timedelta
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class SentinelService:
    """Service for Sentinel-1 SAR satellite data"""
    
    def __init__(self):
        """Initialize Earth Engine"""
        try:
            # Initialize Earth Engine with service account
            credentials = ee.ServiceAccountCredentials(
                email=settings.GEE_SERVICE_ACCOUNT,
                key_file=settings.GEE_PRIVATE_KEY
            )
            ee.Initialize(credentials)
            logger.info("Google Earth Engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Earth Engine: {str(e)}")
            raise
    
    def get_sentinel1_data(self, farm_boundary, start_date=None, end_date=None):
        """
        Fetch Sentinel-1 SAR data for a farm
        
        Args:
            farm_boundary: GeoJSON polygon coordinates
            start_date: Start date for imagery (defaults to 7 days ago)
            end_date: End date for imagery (defaults to today)
        
        Returns:
            dict: Satellite data including backscatter values and image URL
        """
        try:
            # Default date range if not provided
            if not end_date:
                end_date = datetime.now()
            if not start_date:
                start_date = end_date - timedelta(days=7)
            
            # Convert farm boundary to Earth Engine geometry
            geometry = self._create_geometry(farm_boundary)
            
            # Get Sentinel-1 SAR imagery
            sentinel1 = ee.ImageCollection('COPERNICUS/S1_GRD') \
                .filterBounds(geometry) \
                .filterDate(start_date.isoformat(), end_date.isoformat()) \
                .filter(ee.Filter.eq('instrumentMode', 'IW')) \
                .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')) \
                .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
            
            # Check if any images are available
            count = sentinel1.size().getInfo()
            if count == 0:
                logger.warning(f"No Sentinel-1 images found for date range {start_date} to {end_date}")
                return self._get_fallback_data(geometry, start_date, end_date)
            
            # Get most recent image
            image = sentinel1.sort('system:time_start', False).first()
            
            # Get image metadata
            acquisition_date = ee.Date(image.get('system:time_start')).format().getInfo()
            orbit_direction = image.get('orbitProperties_pass').getInfo()
            
            # Calculate metrics for VH and VV polarizations
            vh = image.select('VH')
            vv = image.select('VV')
            
            # Calculate additional metrics
            # VH/VV ratio (useful for crop type discrimination)
            vh_vv_ratio = vh.divide(vv).rename('VH_VV_RATIO')
            
            # Get mean values for the farm area
            stats = image.addBands(vh_vv_ratio).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=10,  # 10 meter resolution
                maxPixels=1e9
            ).getInfo()
            
            # Generate thumbnail URL
            image_url = image.select(['VH', 'VV']).getThumbURL({
                'region': geometry.bounds().getInfo()['coordinates'],
                'dimensions': 512,
                'min': [-25, -20],
                'max': [-5, 0],
                'palette': ['blue', 'white', 'green']
            })
            
            # Estimate soil moisture from VH backscatter
            # Lower VH values indicate drier soil
            soil_moisture = self._estimate_soil_moisture(stats.get('VH', -15))
            
            return {
                'acquisition_date': acquisition_date,
                'vh_backscatter': stats.get('VH'),
                'vv_backscatter': stats.get('VV'),
                'vh_vv_ratio': stats.get('VH_VV_RATIO'),
                'orbit_direction': orbit_direction,
                'image_url': image_url,
                'soil_moisture_estimate': soil_moisture,
                'cloud_penetration': True,  # SAR always penetrates clouds
                'resolution_meters': 10,
                'satellite_type': 'sentinel1'
            }
        
        except Exception as e:
            logger.error(f"Error fetching Sentinel-1 data: {str(e)}")
            raise
    
    def get_sentinel2_data(self, farm_boundary, start_date=None, end_date=None):
        """
        Fetch Sentinel-2 optical data for a farm
        
        Args:
            farm_boundary: GeoJSON polygon coordinates
            start_date: Start date for imagery
            end_date: End date for imagery
        
        Returns:
            dict: Optical satellite data including NDVI
        """
        try:
            if not end_date:
                end_date = datetime.now()
            if not start_date:
                start_date = end_date - timedelta(days=30)  # Longer range for optical
            
            geometry = self._create_geometry(farm_boundary)
            
            # Get Sentinel-2 imagery with low cloud cover
            sentinel2 = ee.ImageCollection('COPERNICUS/S2_SR') \
                .filterBounds(geometry) \
                .filterDate(start_date.isoformat(), end_date.isoformat()) \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
            
            count = sentinel2.size().getInfo()
            if count == 0:
                logger.warning("No clear Sentinel-2 images found")
                return None
            
            # Get image with least cloud cover
            image = sentinel2.sort('CLOUDY_PIXEL_PERCENTAGE').first()
            
            # Get cloud cover percentage
            cloud_cover = image.get('CLOUDY_PIXEL_PERCENTAGE').getInfo()
            acquisition_date = ee.Date(image.get('system:time_start')).format().getInfo()
            
            # Calculate vegetation indices
            ndvi = self._calculate_ndvi(image)
            evi = self._calculate_evi(image)
            savi = self._calculate_savi(image)
            
            # Get mean values
            stats = image.addBands([ndvi, evi, savi]).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=10,
                maxPixels=1e9
            ).getInfo()
            
            # Generate true color thumbnail
            image_url = image.select(['B4', 'B3', 'B2']).getThumbURL({
                'region': geometry.bounds().getInfo()['coordinates'],
                'dimensions': 512,
                'min': 0,
                'max': 3000
            })
            
            return {
                'acquisition_date': acquisition_date,
                'cloud_cover': cloud_cover,
                'ndvi': stats.get('NDVI'),
                'evi': stats.get('EVI'),
                'savi': stats.get('SAVI'),
                'image_url': image_url,
                'satellite_type': 'sentinel2'
            }
        
        except Exception as e:
            logger.error(f"Error fetching Sentinel-2 data: {str(e)}")
            return None
    
    def _create_geometry(self, farm_boundary):
        """Create Earth Engine geometry from farm boundary"""
        if isinstance(farm_boundary, dict):
            # GeoJSON format
            if 'coordinates' in farm_boundary:
                coords = farm_boundary['coordinates']
            else:
                coords = farm_boundary
        else:
            # Assume it's already coordinates
            coords = farm_boundary
        
        # Ensure coordinates are in correct format
        if isinstance(coords[0][0], (int, float)):
            # Single polygon
            coords = [coords]
        
        return ee.Geometry.Polygon(coords)
    
    def _calculate_ndvi(self, image):
        """Calculate NDVI: (NIR - Red) / (NIR + Red)"""
        nir = image.select('B8')
        red = image.select('B4')
        ndvi = nir.subtract(red).divide(nir.add(red)).rename('NDVI')
        return ndvi
    
    def _calculate_evi(self, image):
        """Calculate Enhanced Vegetation Index"""
        nir = image.select('B8')
        red = image.select('B4')
        blue = image.select('B2')
        
        evi = image.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
            {
                'NIR': nir,
                'RED': red,
                'BLUE': blue
            }
        ).rename('EVI')
        
        return evi
    
    def _calculate_savi(self, image):
        """Calculate Soil Adjusted Vegetation Index"""
        nir = image.select('B8')
        red = image.select('B4')
        L = 0.5  # Soil brightness correction factor
        
        savi = image.expression(
            '((NIR - RED) / (NIR + RED + L)) * (1 + L)',
            {
                'NIR': nir,
                'RED': red,
                'L': L
            }
        ).rename('SAVI')
        
        return savi
    
    def _estimate_soil_moisture(self, vh_backscatter):
        """
        Estimate soil moisture from VH backscatter
        
        Lower backscatter values indicate drier soil
        This is a simplified estimation
        """
        if vh_backscatter is None:
            return None
        
        # Normalize backscatter to 0-100% moisture scale
        # Typical VH range: -25 dB (dry) to -5 dB (wet)
        min_vh = -25  # Very dry
        max_vh = -5   # Very wet
        
        # Clamp values
        vh_clamped = max(min_vh, min(vh_backscatter, max_vh))
        
        # Linear interpolation
        moisture = ((vh_clamped - min_vh) / (max_vh - min_vh)) * 100
        
        return round(moisture, 1)
    
    def _get_fallback_data(self, geometry, start_date, end_date):
        """
        Get fallback data when no recent imagery is available
        Try older dates
        """
        try:
            # Extend date range backwards
            extended_start = start_date - timedelta(days=14)
            
            sentinel1 = ee.ImageCollection('COPERNICUS/S1_GRD') \
                .filterBounds(geometry) \
                .filterDate(extended_start.isoformat(), end_date.isoformat()) \
                .filter(ee.Filter.eq('instrumentMode', 'IW')) \
                .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
            
            count = sentinel1.size().getInfo()
            
            if count == 0:
                logger.error("No Sentinel-1 imagery available even with extended date range")
                return None
            
            image = sentinel1.sort('system:time_start', False).first()
            acquisition_date = ee.Date(image.get('system:time_start')).format().getInfo()
            
            logger.info(f"Using older imagery from {acquisition_date}")
            
            # Get basic stats
            stats = image.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=10
            ).getInfo()
            
            return {
                'acquisition_date': acquisition_date,
                'vh_backscatter': stats.get('VH'),
                'vv_backscatter': stats.get('VV'),
                'image_url': image.getThumbURL({'region': geometry, 'dimensions': 512}),
                'note': 'Using older imagery due to lack of recent data',
                'satellite_type': 'sentinel1'
            }
        
        except Exception as e:
            logger.error(f"Fallback data retrieval failed: {str(e)}")
            return None
    
    def verify_farm_size(self, farm_boundary):
        """
        Verify farm size using satellite imagery
        
        Args:
            farm_boundary: GeoJSON polygon
        
        Returns:
            float: Calculated area in acres
        """
        try:
            geometry = self._create_geometry(farm_boundary)
            area_square_meters = geometry.area().getInfo()
            
            # Convert to acres (1 acre = 4046.86 square meters)
            area_acres = area_square_meters / 4046.86
            
            return round(area_acres, 2)
        
        except Exception as e:
            logger.error(f"Error verifying farm size: {str(e)}")
            return None