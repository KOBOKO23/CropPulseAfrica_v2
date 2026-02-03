# apps/satellite/services/cloud_mask.py

import ee
import logging

logger = logging.getLogger(__name__)


class CloudMaskService:
    """Service for cloud masking in satellite imagery"""
    
    def __init__(self):
        """Initialize cloud mask service"""
        pass
    
    def mask_clouds_sentinel2(self, image):
        """
        Mask clouds in Sentinel-2 imagery using QA band
        
        Args:
            image: Earth Engine Image object
        
        Returns:
            image: Cloud-masked image
        """
        try:
            # Select the QA60 band for cloud masking
            qa = image.select('QA60')
            
            # Bits 10 and 11 are clouds and cirrus
            cloud_bit_mask = 1 << 10
            cirrus_bit_mask = 1 << 11
            
            # Both bits should be zero for clear conditions
            mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
                qa.bitwiseAnd(cirrus_bit_mask).eq(0)
            )
            
            return image.updateMask(mask)
        
        except Exception as e:
            logger.error(f"Error masking clouds: {str(e)}")
            return image
    
    def calculate_cloud_score(self, image):
        """
        Calculate cloud score for Sentinel-2 image
        
        Args:
            image: Earth Engine Image object
        
        Returns:
            image: Image with cloud score band
        """
        try:
            # Use simple cloud score algorithm
            # Clouds are typically bright and have high blue reflectance
            
            # Calculate brightness
            brightness = image.select(['B4', 'B3', 'B2']).reduce(ee.Reducer.sum())
            
            # Clouds are bright
            bright = brightness.gt(0.3)
            
            # Clouds typically have high blue reflectance
            blue_bright = image.select('B2').gt(0.15)
            
            # Combine criteria
            cloud_score = bright.And(blue_bright).rename('cloud_score')
            
            return image.addBands(cloud_score)
        
        except Exception as e:
            logger.error(f"Error calculating cloud score: {str(e)}")
            return image
    
    def get_cloud_free_composite(self, collection, geometry, start_date, end_date):
        """
        Create cloud-free composite from image collection
        
        Args:
            collection: ImageCollection ID
            geometry: Area of interest
            start_date: Start date
            end_date: End date
        
        Returns:
            image: Cloud-free composite
        """
        try:
            # Get collection
            images = ee.ImageCollection(collection) \
                .filterBounds(geometry) \
                .filterDate(start_date, end_date) \
                .map(self.mask_clouds_sentinel2)
            
            # Create median composite (removes clouds)
            composite = images.median()
            
            return composite
        
        except Exception as e:
            logger.error(f"Error creating cloud-free composite: {str(e)}")
            return None
    
    def calculate_clear_pixel_percentage(self, image, geometry):
        """
        Calculate percentage of clear (non-cloud) pixels
        
        Args:
            image: Earth Engine Image
            geometry: Area of interest
        
        Returns:
            float: Percentage of clear pixels
        """
        try:
            # Get cloud mask
            masked_image = self.mask_clouds_sentinel2(image)
            
            # Count total pixels
            total_pixels = ee.Image.constant(1).reduceRegion(
                reducer=ee.Reducer.count(),
                geometry=geometry,
                scale=10,
                maxPixels=1e9
            ).get('constant')
            
            # Count clear pixels
            clear_pixels = masked_image.select('B4').reduceRegion(
                reducer=ee.Reducer.count(),
                geometry=geometry,
                scale=10,
                maxPixels=1e9
            ).get('B4')
            
            # Calculate percentage
            total = total_pixels.getInfo()
            clear = clear_pixels.getInfo()
            
            if total == 0:
                return 0
            
            percentage = (clear / total) * 100
            
            return round(percentage, 2)
        
        except Exception as e:
            logger.error(f"Error calculating clear pixel percentage: {str(e)}")
            return 0
    
    def generate_cloud_mask_url(self, image, geometry):
        """
        Generate visualization URL for cloud mask
        
        Args:
            image: Earth Engine Image
            geometry: Area of interest
        
        Returns:
            str: Thumbnail URL showing cloud mask
        """
        try:
            # Calculate cloud score
            cloud_image = self.calculate_cloud_score(image)
            
            # Visualize cloud score
            url = cloud_image.select('cloud_score').getThumbURL({
                'region': geometry.bounds().getInfo()['coordinates'],
                'dimensions': 512,
                'min': 0,
                'max': 1,
                'palette': ['white', 'gray', 'black']
            })
            
            return url
        
        except Exception as e:
            logger.error(f"Error generating cloud mask URL: {str(e)}")
            return None
    
    def detect_cloud_shadows(self, image):
        """
        Detect cloud shadows in Sentinel-2 imagery
        
        Args:
            image: Earth Engine Image
        
        Returns:
            image: Image with cloud shadow mask
        """
        try:
            # Cloud shadows are typically dark
            # Calculate darkness score using NIR band
            nir = image.select('B8')
            dark = nir.lt(0.15).rename('cloud_shadow')
            
            return image.addBands(dark)
        
        except Exception as e:
            logger.error(f"Error detecting cloud shadows: {str(e)}")
            return image
    
    def mask_clouds_and_shadows(self, image):
        """
        Mask both clouds and cloud shadows
        
        Args:
            image: Earth Engine Image
        
        Returns:
            image: Masked image
        """
        try:
            # Mask clouds
            cloud_masked = self.mask_clouds_sentinel2(image)
            
            # Detect shadows
            shadow_image = self.detect_cloud_shadows(cloud_masked)
            shadow_mask = shadow_image.select('cloud_shadow').Not()
            
            # Apply shadow mask
            final_masked = cloud_masked.updateMask(shadow_mask)
            
            return final_masked
        
        except Exception as e:
            logger.error(f"Error masking clouds and shadows: {str(e)}")
            return image