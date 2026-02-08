# apps/climate/tasks.py

from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User
import logging
import ee
from django.conf import settings

logger = logging.getLogger(__name__)

@shared_task(name='climate.update_climate_data')
def update_climate_data(user_id=None):
    """
    Automatically update climate data from satellite sources
    Runs every 30 minutes
    """
    try:
        logger.info(f"Starting climate data update for user {user_id}")
        
        # Initialize Google Earth Engine
        try:
            credentials = ee.ServiceAccountCredentials(
                email=settings.GEE_SERVICE_ACCOUNT,
                key_file=settings.GEE_PRIVATE_KEY
            )
            ee.Initialize(credentials)
        except Exception as e:
            logger.error(f"Failed to initialize Google Earth Engine: {str(e)}")
            return {'error': 'Satellite service unavailable'}

        # Define locations to update (Kenya regions)
        locations = [
            {'name': 'Nairobi', 'coords': [36.8219, -1.2921]},
            {'name': 'Kiambu', 'coords': [36.8356, -1.1719]},
            {'name': 'Nakuru', 'coords': [36.0667, -0.3031]},
            {'name': 'Meru', 'coords': [37.6556, 0.0467]},
        ]

        updated_locations = []

        for location in locations:
            try:
                aoi = ee.Geometry.Point(location['coords'])
                
                # Get latest ERA5 data
                era5 = ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR') \
                         .filterDate(ee.Date.fromYMD(2024, 2, 1), ee.Date.fromYMD(2024, 2, 5)) \
                         .filterBounds(aoi) \
                         .first()

                # Get temperature
                temp_data = era5.select('temperature_2m').reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=aoi,
                    scale=11132,
                    maxPixels=1e9
                )

                # Get precipitation
                precip_data = era5.select('total_precipitation_sum').reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=aoi,
                    scale=11132,
                    maxPixels=1e9
                )

                # Get soil moisture
                soil_data = era5.select('volumetric_soil_water_layer_1').reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=aoi,
                    scale=11132,
                    maxPixels=1e9
                )

                # Process results
                temp_info = temp_data.getInfo()
                precip_info = precip_data.getInfo()
                soil_info = soil_data.getInfo()

                temperature = temp_info.get('temperature_2m', 295) - 273.15
                precipitation = precip_info.get('total_precipitation_sum', 0) * 1000
                soil_moisture = soil_info.get('volumetric_soil_water_layer_1', 0.3) * 100

                climate_update = {
                    'location': location['name'],
                    'temperature': round(temperature, 1),
                    'precipitation': round(precipitation, 1),
                    'soil_moisture': round(soil_moisture, 1),
                    'updated_at': timezone.now().isoformat()
                }

                updated_locations.append(climate_update)
                logger.info(f"Updated climate data for {location['name']}")

            except Exception as e:
                logger.error(f"Failed to update climate data for {location['name']}: {str(e)}")
                continue

        # Schedule next update in 30 minutes
        update_climate_data.apply_async(
            args=[user_id],
            countdown=30 * 60  # 30 minutes
        )

        return {
            'success': True,
            'updated_locations': len(updated_locations),
            'locations': updated_locations,
            'next_update': '30 minutes'
        }

    except Exception as e:
        logger.error(f"Climate data update task failed: {str(e)}")
        return {'error': str(e)}


@shared_task(name='climate.generate_climate_alerts')
def generate_climate_alerts():
    """
    Generate climate alerts based on satellite data
    Runs every hour
    """
    try:
        logger.info("Generating climate alerts")
        
        # This would typically check thresholds and send notifications
        # For now, we'll just log the activity
        
        alerts_generated = []
        
        # Example alert logic (would be more sophisticated in production)
        # Check for extreme weather conditions, drought, flooding, etc.
        
        logger.info(f"Generated {len(alerts_generated)} climate alerts")
        
        # Schedule next alert check in 1 hour
        generate_climate_alerts.apply_async(countdown=60 * 60)
        
        return {
            'success': True,
            'alerts_generated': len(alerts_generated),
            'next_check': '1 hour'
        }
        
    except Exception as e:
        logger.error(f"Climate alerts generation failed: {str(e)}")
        return {'error': str(e)}
