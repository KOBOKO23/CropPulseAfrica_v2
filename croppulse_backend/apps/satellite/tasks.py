# apps/satellite/tasks.py

from celery import shared_task
from django.utils import timezone
from datetime import datetime, timedelta
import logging
import uuid

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_satellite_scan(self, farm_id):
    """
    Process satellite scan for a farm with caching
    
    Args:
        farm_id: Farm database ID
    
    Returns:
        dict: Scan results
    """
    from apps.farms.models import Farm
    from .models import SatelliteScan, NDVIHistory
    from .services import (
        SentinelService,
        NDVICalculator,
        SARProcessor,
        CloudMaskService,
        CloudClassifier,
        ImageCacheService,
    )
    
    try:
        logger.info(f"Starting satellite scan for farm ID: {farm_id}")
        
        # Get farm
        farm = Farm.objects.select_related('farmer').get(id=farm_id)
        
        # Initialize services
        sentinel_service = SentinelService()
        ndvi_calculator = NDVICalculator()
        sar_processor = SARProcessor()
        cloud_mask_service = CloudMaskService()
        cloud_classifier = CloudClassifier()
        cache_service = ImageCacheService()
        
        # Check cache first
        cached_result = cache_service.get_cached_scan_result(farm.farm_id)
        if cached_result:
            logger.info(f"Using cached scan result for farm {farm.farm_id}")
            return cached_result
        
        # Get farm boundary as GeoJSON
        farm_boundary = {
            'type': 'Polygon',
            'coordinates': [[[point[0], point[1]] for point in farm.boundary.coords[0]]],
        }
        
        # Set date range (last 7 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        # Try to get Sentinel-2 optical data first
        logger.info("Fetching Sentinel-2 optical data...")
        optical_data = sentinel_service.get_sentinel2_data(
            farm_boundary,
            start_date,
            end_date,
        )
        
        # Get Sentinel-1 SAR data (always works, even with clouds)
        logger.info("Fetching Sentinel-1 SAR data...")
        sar_data = sentinel_service.get_sentinel1_data(
            farm_boundary,
            start_date,
            end_date,
        )
        
        if not sar_data:
            raise Exception("No satellite data available")
        
        # Process SAR data
        sar_metrics = sar_processor.process_sar_backscatter(
            sar_data.get('vh_backscatter'),
            sar_data.get('vv_backscatter'),
        )
        
        # Verify farm size
        logger.info("Verifying farm size...")
        verified_size = sentinel_service.verify_farm_size(farm_boundary)
        
        # Classify cloud coverage
        cloud_cover = optical_data.get('cloud_cover', 100) if optical_data else 100
        cloud_classification = cloud_classifier.classify_cloud_coverage(cloud_cover)
        
        # ---------------------------------------------------------------------------
        # Calculate clear-pixel percentage via CloudMaskService when optical imagery
        # is available.  The service expects an ee.Image; sentinel_service already
        # returned the raw GEE image stats so we calculate from the cloud_cover value
        # that was already extracted.  For a full per-pixel mask you would pass the
        # ee.Image object directly; here we derive the percentage from cloud_cover
        # as a consistent fallback that avoids an extra GEE round-trip.
        # ---------------------------------------------------------------------------
        clear_pixel_pct = round(100.0 - cloud_cover, 2) if optical_data else 0.0
        logger.info(f"Clear pixel percentage for farm {farm.farm_id}: {clear_pixel_pct}%")
        
        # Determine which data to use
        if optical_data and optical_data.get('cloud_cover', 100) < 50:
            # Use optical data if available and clear
            primary_data = optical_data
            satellite_type = 'sentinel2'
            ndvi = optical_data.get('ndvi')
            evi = optical_data.get('evi')
            savi = optical_data.get('savi')
            sar_penetrated = False
        else:
            # Use SAR data
            primary_data = sar_data
            satellite_type = 'sentinel1'
            ndvi = None
            evi = None
            savi = None
            sar_penetrated = True
        
        # Get soil moisture
        soil_moisture = sar_metrics.get('soil_moisture_estimate')
        
        # Interpret crop health
        if ndvi:
            health_interpretation = ndvi_calculator.interpret_ndvi(ndvi)
            crop_health_status = health_interpretation['status']
            
            # Predict crop stage
            crop_stage_info = ndvi_calculator.predict_crop_stage(
                ndvi,
                farm.farmer.primary_crop if hasattr(farm.farmer, 'primary_crop') else 'maize',
            )
            crop_stage = crop_stage_info['description']
            
            # Calculate health score
            health_score = ndvi_calculator.generate_health_score(
                ndvi,
                soil_moisture,
            )
        else:
            # Use SAR-based estimation
            crop_health_status = 'Stressed' if soil_moisture and soil_moisture < 30 else 'Healthy'
            crop_stage = 'Unknown - optical data needed'
            health_score = 50  # Default moderate score
        
        # Calculate size difference
        declared_size = float(farm.size_acres)
        size_tolerance = 0.3  # 30% tolerance
        matches_size = abs(verified_size - declared_size) / declared_size <= size_tolerance
        size_difference_pct = ((verified_size - declared_size) / declared_size) * 100
        
        # Generate quality score
        sar_quality = sar_processor.generate_sar_quality_score(
            sar_metrics.get('vh_backscatter'),
            sar_metrics.get('vv_backscatter'),
            sar_data.get('orbit_direction'),
        )
        
        # Assess scan quality using cloud_cover and clear_pixel_pct
        scan_quality = cloud_classifier.assess_scan_quality(cloud_cover, clear_pixel_pct)
        
        # Generate unique scan ID
        scan_id = f"SCAN-{farm.farm_id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create satellite scan record
        scan = SatelliteScan.objects.create(
            scan_id=scan_id,
            farm=farm,
            satellite_type=satellite_type,
            acquisition_date=datetime.fromisoformat(
                primary_data['acquisition_date'].replace('Z', '+00:00')
            ),
            processing_status='completed',
            image_url=primary_data.get('image_url', ''),
            cloud_cover_percentage=cloud_cover,
            sar_penetrated_clouds=sar_penetrated,
            clear_pixel_percentage=clear_pixel_pct,
            ndvi=ndvi,
            evi=evi,
            savi=savi,
            vh_backscatter=sar_metrics.get('vh_backscatter'),
            vv_backscatter=sar_metrics.get('vv_backscatter'),
            vh_vv_ratio=sar_metrics.get('vh_vv_ratio'),
            soil_moisture=soil_moisture,
            crop_stage=crop_stage,
            crop_health_status=crop_health_status,
            verified_farm_size=verified_size,
            matches_declared_size=matches_size,
            size_difference_percentage=round(size_difference_pct, 2),
            data_quality_score=scan_quality.get('quality_score', sar_quality.get('quality_score', health_score)),
            resolution_meters=primary_data.get('resolution_meters', 10),
            orbit_direction=sar_data.get('orbit_direction'),
            raw_satellite_data={
                'optical': optical_data,
                'sar': sar_data,
                'sar_metrics': sar_metrics,
                'cloud_classification': cloud_classification,
                'scan_quality': scan_quality,
            },
        )
        
        # Save NDVI to history if available
        if ndvi:
            NDVIHistory.objects.update_or_create(
                farm=farm,
                date=scan.acquisition_date.date(),
                defaults={
                    'ndvi_value': ndvi,
                    'evi_value': evi,
                    'savi_value': savi,
                    'soil_moisture': soil_moisture,
                    'satellite_scan': scan,
                },
            )
        
        # Update farm verification status
        farm.satellite_verified = True
        farm.last_verified = timezone.now()
        farm.verification_confidence = sar_quality.get('quality_score', 70) / 100
        farm.save(update_fields=['satellite_verified', 'last_verified', 'verification_confidence'])
        
        # Prepare result
        result = {
            'success': True,
            'scan_id': scan_id,
            'farm_id': farm.farm_id,
            'ndvi': ndvi,
            'health_status': crop_health_status,
            'verified_size': verified_size,
            'quality_score': scan_quality.get('quality_score', sar_quality.get('quality_score', health_score)),
        }
        
        # Cache result
        cache_service.cache_scan_result(farm.farm_id, result)
        
        logger.info(f"Successfully completed satellite scan: {scan_id}")
        
        return result
    
    except Exception as e:
        logger.error(f"Error processing satellite scan for farm {farm_id}: {str(e)}")
        
        # Update scan status to failed
        try:
            farm = Farm.objects.get(id=farm_id)
            scan_id = f"SCAN-{farm.farm_id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            
            SatelliteScan.objects.create(
                scan_id=scan_id,
                farm=farm,
                satellite_type='sentinel1',
                acquisition_date=timezone.now(),
                processing_status='failed',
                processing_error=str(e),
                image_url='',
                cloud_cover_percentage=100,
                verified_farm_size=float(farm.size_acres),
                crop_health_status='Unknown',  # valid: added to HEALTH_STATUS choices
                raw_satellite_data={'error': str(e)},
            )
        except Exception:
            pass
        
        # Retry with exponential backoff
        try:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for farm {farm_id}")
            return {
                'success': False,
                'error': str(e),
                'farm_id': farm_id,
            }


@shared_task
def bulk_process_scans(farm_ids):
    """
    Process satellite scans for multiple farms
    
    Args:
        farm_ids: List of farm database IDs
    
    Returns:
        dict: Summary of results
    """
    logger.info(f"Starting bulk satellite scan for {len(farm_ids)} farms")
    
    results = {
        'total': len(farm_ids),
        'successful': 0,
        'failed': 0,
        'errors': [],
    }
    
    for farm_id in farm_ids:
        try:
            process_satellite_scan.delay(farm_id)
            results['successful'] += 1
        except Exception as e:
            results['failed'] += 1
            results['errors'].append({
                'farm_id': farm_id,
                'error': str(e),
            })
            logger.error(f"Failed to queue scan for farm {farm_id}: {str(e)}")
    
    logger.info(f"Bulk scan complete: {results['successful']} successful, {results['failed']} failed")
    return results


@shared_task
def update_ndvi_history():
    """
    Periodic task to update NDVI history for all active farms
    Run daily via Celery beat
    """
    from apps.farms.models import Farm
    
    logger.info("Starting daily NDVI history update")
    
    # Get all active farms that haven't been scanned in the last 7 days
    seven_days_ago = timezone.now() - timedelta(days=7)
    farms_to_scan = Farm.objects.filter(
        is_active=True,
        last_verified__lt=seven_days_ago,
    ) | Farm.objects.filter(
        is_active=True,
        last_verified__isnull=True,
    )
    
    count = 0
    for farm in farms_to_scan[:100]:  # Limit to 100 per run
        try:
            process_satellite_scan.delay(farm.id)
            count += 1
        except Exception as e:
            logger.error(f"Failed to queue NDVI update for farm {farm.farm_id}: {str(e)}")
    
    logger.info(f"Queued {count} farms for NDVI update")
    return {
        'farms_queued': count,
        'timestamp': timezone.now().isoformat(),
    }


@shared_task
def cleanup_old_scans():
    """
    Clean up satellite scans older than 1 year
    Keep only the most recent scan per month for historical data
    """
    from .models import SatelliteScan
    from django.db.models import Count, Min
    
    logger.info("Starting cleanup of old satellite scans")
    
    one_year_ago = timezone.now() - timedelta(days=365)
    
    deleted_count = 0
    
    # Get old scans
    old_scans = SatelliteScan.objects.filter(
        acquisition_date__lt=one_year_ago,
    )
    
    # For each farm, keep only one scan per month
    farms_with_old_scans = old_scans.values('farm').distinct()
    
    for farm_data in farms_with_old_scans:
        farm_id = farm_data['farm']
        
        # Group by year-month
        from django.db.models.functions import TruncMonth
        
        monthly_scans = old_scans.filter(
            farm_id=farm_id,
        ).annotate(
            month=TruncMonth('acquisition_date'),
        ).values('month').annotate(
            count=Count('id'),
            first_scan_id=Min('id'),
        )
        
        for month_data in monthly_scans:
            if month_data['count'] > 1:
                # Keep the first scan, delete others
                scans_to_delete = old_scans.filter(
                    farm_id=farm_id,
                    acquisition_date__year=month_data['month'].year,
                    acquisition_date__month=month_data['month'].month,
                ).exclude(
                    id=month_data['first_scan_id'],
                )
                
                count = scans_to_delete.count()
                scans_to_delete.delete()
                deleted_count += count
    
    logger.info(f"Cleaned up {deleted_count} old satellite scans")
    return {
        'deleted_count': deleted_count,
        'timestamp': timezone.now().isoformat(),
    }


@shared_task
def generate_health_alerts():
    """
    Generate health alerts for farms with declining NDVI
    Run daily via Celery beat
    """
    from .models import NDVIHistory, SatelliteScan
    
    logger.info("Generating health alerts based on NDVI trends")
    
    alerts_created = 0
    
    # Get farms with recent scans
    recent_scans = SatelliteScan.objects.filter(
        acquisition_date__gte=timezone.now() - timedelta(days=7),
        processing_status='completed',
    ).select_related('farm', 'farm__farmer', 'farm__farmer__user')
    
    for scan in recent_scans:
        farm = scan.farm
        
        # Get NDVI history for last 30 days
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        history = NDVIHistory.objects.filter(
            farm=farm,
            date__gte=thirty_days_ago,
        ).order_by('date')
        
        if history.count() < 2:
            continue  # Not enough data
        
        # Check for declining trend
        values = [h.ndvi_value for h in history]
        first_value = values[0]
        last_value = values[-1]
        
        decline = first_value - last_value
        decline_percentage = (decline / first_value) * 100 if first_value > 0 else 0
        
        # Create alert if significant decline
        if decline_percentage > 10:  # More than 10% decline
            try:
                from apps.notifications.models import Notification
                
                Notification.objects.create(
                    user=farm.farmer.user,
                    notification_type='farm_alert',
                    title='Crop Health Alert',
                    message=(
                        f'NDVI has declined by {decline_percentage:.1f}% on your farm {farm.farm_id}. '
                        f'Current health status: {scan.crop_health_status}. Please investigate.'
                    ),
                    action_url=f'/farms/{farm.farm_id}/monitor',
                )
                alerts_created += 1
                logger.info(f"Created health alert for farm {farm.farm_id}")
            except Exception as e:
                logger.error(f"Failed to create alert for farm {farm.farm_id}: {str(e)}")
    
    logger.info(f"Created {alerts_created} health alerts")
    return {
        'alerts_created': alerts_created,
        'timestamp': timezone.now().isoformat(),
    }


@shared_task
def warm_satellite_cache():
    """
    Pre-warm cache for frequently accessed farms
    Run every hour
    """
    from apps.farms.models import Farm
    from .services import ImageCacheService
    
    logger.info("Warming satellite data cache")
    
    cache_service = ImageCacheService()
    
    # Get recently active farms
    recent_farms = Farm.objects.filter(
        is_active=True,
        last_verified__gte=timezone.now() - timedelta(days=30),
    ).order_by('-last_verified')[:50]
    
    warmed = 0
    
    for farm in recent_farms:
        try:
            result = cache_service.warm_cache_for_farm(farm)
            if result.get('scan_cached') or result.get('ndvi_cached'):
                warmed += 1
        except Exception as e:
            logger.error(f"Failed to warm cache for farm {farm.farm_id}: {str(e)}")
    
    logger.info(f"Warmed cache for {warmed} farms")
    return {
        'farms_warmed': warmed,
        'timestamp': timezone.now().isoformat(),
    }