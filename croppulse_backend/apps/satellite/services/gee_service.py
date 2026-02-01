# apps/satellite/services/gee_service.py

import ee
from datetime import datetime, timedelta
from django.conf import settings


class GoogleEarthEngineService:
    """Integration with Google Earth Engine"""
    
    def __init__(self):
        # Initialize Earth Engine with service account
        credentials = ee.ServiceAccountCredentials(
            email=settings.GEE_SERVICE_ACCOUNT,
            key_file=settings.GEE_PRIVATE_KEY
        )
        ee.Initialize(credentials)
    
    def get_sentinel1_data(self, farm_boundary, start_date, end_date):
        """
        Fetch Sentinel-1 SAR data for a farm
        
        Args:
            farm_boundary: GeoJSON polygon
            start_date: datetime
            end_date: datetime
        
        Returns:
            dict: Satellite data including NDVI, soil moisture, etc.
        """
        # Convert farm boundary to Earth Engine geometry
        geometry = ee.Geometry.Polygon(farm_boundary['coordinates'])
        
        # Get Sentinel-1 SAR imagery
        sentinel1 = ee.ImageCollection('COPERNICUS/S1_GRD') \
            .filterBounds(geometry) \
            .filterDate(start_date.isoformat(), end_date.isoformat()) \
            .filter(ee.Filter.eq('instrumentMode', 'IW')) \
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
        
        # Get most recent image
        image = sentinel1.sort('system:time_start', False).first()
        
        # Calculate metrics
        vh = image.select('VH')
        vv = image.select('VV')
        
        # Get mean values for the farm area
        stats = image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=10
        ).getInfo()
        
        return {
            'acquisition_date': ee.Date(image.get('system:time_start')).format().getInfo(),
            'vh_backscatter': stats.get('VH'),
            'vv_backscatter': stats.get('VV'),
            'image_url': image.getThumbURL({'region': geometry, 'dimensions': 512})
        }
    
    def calculate_ndvi(self, farm_boundary, date):
        """Calculate NDVI using Sentinel-2 optical imagery"""
        geometry = ee.Geometry.Polygon(farm_boundary['coordinates'])
        
        # Get Sentinel-2 imagery
        sentinel2 = ee.ImageCollection('COPERNICUS/S2_SR') \
            .filterBounds(geometry) \
            .filterDate(date, date + timedelta(days=7)) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
        
        image = sentinel2.sort('CLOUDY_PIXEL_PERCENTAGE').first()
        
        # Calculate NDVI: (NIR - Red) / (NIR + Red)
        nir = image.select('B8')
        red = image.select('B4')
        ndvi = nir.subtract(red).divide(nir.add(red)).rename('NDVI')
        
        # Get mean NDVI for farm
        ndvi_value = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=10
        ).get('NDVI').getInfo()
        
        return {
            'ndvi': round(ndvi_value, 3),
            'cloud_cover': image.get('CLOUDY_PIXEL_PERCENTAGE').getInfo(),
            'date': ee.Date(image.get('system:time_start')).format().getInfo()
        }