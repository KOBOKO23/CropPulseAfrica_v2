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
    Process satellite scan for a farm
    
    Args:
        farm_id: Farm database ID
    
    Returns:
        dict: Scan results
    """
    from apps.farms.models import Farm
    from .models import SatelliteScan, NDVIHistory
    from .services.sentinel_service import SentinelService
    from .services.ndvi_calculator import NDVICalculator
    
    try:
        logger.info(f"Starting satellite scan for farm ID: {farm_id}")
        
        # Get farm
        farm = Farm.objects.select_related('farmer').get(id=farm_id)
        
        # Initialize services
        sentinel_service = SentinelService()
        ndvi_calculator = NDVICalculator()
        
        # Get farm boundary as GeoJSON
        farm_boundary = {
            'type': 'Polygon',
            'coordinates': [[[point.x, point.y] for point in farm.boundary.coords[0]]]
        }
        
        # Set date range (last 7 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        # Try to get Sentinel-2 optical data first (for NDVI)
        logger.info("Fetching Sentinel-2 optical data...")
        optical_data = sentinel_service.get_sentinel2_data(
            farm_boundary,
            start_date,
            end_date
        )
        
        # Get Sentinel-1 SAR data (always works, even with clouds)
        logger.info("Fetching Sentinel-1 SAR data...")
        sar_data = sentinel_service.get_sentinel1_data(
            farm_boundary,
            start_date,
            end_date
        )
        
        if not sar_data:
            raise Exception("No satellite data available")
        
        # Verify farm size
        logger.info("Verifying farm size...")
        verified_size = sentinel_service.verify_farm_size(farm_boundary)
        
        # Determine which data to use
        if optical_data and optical_data.get('cloud_cover', 100) < 50:
            # Use optical data if available and clear
            primary_data = optical_data
            satellite_type = 'sentinel2'
            ndvi = optical_data.get('ndvi')
            evi = optical_data.get('evi')
            savi = optical_data.get('savi')
            cloud_cover = optical_data.get('cloud_cover', 0)
            sar_penetrated = False
        else:
            # Use SAR data
            primary_data = sar_data
            satellite_type = 'sentinel1'
            # NDVI not available from SAR, will be None
            ndvi = None
            evi = None
            savi = None
            cloud_cover = 100  # Assume full cloud cover if using SAR
            sar_penetrated = True
        
        # Get soil moisture from SAR
        soil_moisture = sar_data.get('soil_moisture_estimate')
        
        # Interpret crop health
        if ndvi:
            health_interpretation = ndvi_calculator.interpret_ndvi(ndvi)
            crop_health_status = health_interpretation['status']
            
            # Predict crop stage
            crop_stage_info = ndvi_calculator.predict_crop_stage(
                ndvi,
                farm.farmer.primary_crop if hasattr(farm.farmer, 'primary_crop') else 'maize'
            )
            crop_stage = crop_stage_info['description']
        else:
            # Use SAR-based estimation
            crop_health_status = 'Stressed' if soil_moisture and soil_moisture < 30 else 'Healthy'
            crop_stage = 'Unknown - optical data needed'
        
        # Check if farm size matches
        declared_size = float(farm.size_acres)
        size_tolerance = 0.3  # 30% tolerance
        matches_size = abs(verified_size - declared_size) / declared_size <= size_tolerance
        
        # Generate unique scan ID
        scan_id = f"SCAN-{farm.farm_id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create satellite scan record
        scan = SatelliteScan.objects.create(
            scan_id=scan_id,
            farm=farm,
            satellite_type=satellite_type,
            acquisition_date=datetime.fromisoformat(primary_data['acquisition_date'].replace('Z', '+00:00')),
            image_url=primary_data.get('image_url', ''),
            cloud_cover_percentage=cloud_cover,
            sar_penetrated_clouds=sar_penetrated,
            ndvi=ndvi,
            evi=evi,
            savi=savi,
            soil_moisture=soil_moisture,
            crop_stage=crop_stage,
            crop_health_status=crop_health_status,
            verified_farm_size=verified_size,
            matches_declared_size=matches_size,
            raw_satellite_data={
                'optical': optical_data,
                'sar': sar_data
            }
        )
        
        # Save NDVI to history if available
        if ndvi:
            NDVIHistory.objects.create(
                farm=farm,
                date=scan.acquisition_date.date(),
                ndvi_value=ndvi,
                satellite_scan=scan
            )
        
        # Update farm verification status
        farm.satellite_verified = True
        farm.last_verified = timezone.now()
        farm.save(update_fields=['satellite_verified', 'last_verified'])
        
        logger.info(f"Successfully completed satellite scan: {scan_id}")
        
        return {
            'success': True,
            'scan_id': scan_id,
            'farm_id': farm.farm_id,
            'ndvi': ndvi,
            'health_status': crop_health_status,
            'verified_size': verified_size
        }
    
    except Exception as e:
        logger.error(f"Error processing satellite scan for farm {farm_id}: {str(e)}")
        
        # Retry with exponential backoff
        try:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for farm {farm_id}")
            return {
                'success': False,
                'error': str(e),
                'farm_id': farm_id
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
        'errors': []
    }
    
    for farm_id in farm_ids:
        try:
            result = process_satellite_scan.delay(farm_id)
            results['successful'] += 1
        except Exception as e:
            results['failed'] += 1
            results['errors'].append({
                'farm_id': farm_id,
                'error': str(e)
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
        last_verified__lt=seven_days_ago
    ) | Farm.objects.filter(
        is_active=True,
        last_verified__isnull=True
    )
    
    count = 0
    for farm in farms_to_scan:
        try:
            process_satellite_scan.delay(farm.id)
            count += 1
        except Exception as e:
            logger.error(f"Failed to queue NDVI update for farm {farm.farm_id}: {str(e)}")
    
    logger.info(f"Queued {count} farms for NDVI update")
    return {
        'farms_queued': count,
        'timestamp': timezone.now().isoformat()
    }


@shared_task
def cleanup_old_scans():
    """
    Clean up satellite scans older than 1 year
    Keep only the most recent scan per month for historical data
    Run monthly via Celery beat
    """
    from .models import SatelliteScan
    from django.db.models import Count, Min
    
    logger.info("Starting cleanup of old satellite scans")
    
    one_year_ago = timezone.now() - timedelta(days=365)
    
    # Get old scans grouped by farm and month
    old_scans = SatelliteScan.objects.filter(
        acquisition_date__lt=one_year_ago
    )
    
    deleted_count = 0
    
    # For each farm, keep only one scan per month
    farms_with_old_scans = old_scans.values('farm').distinct()
    
    for farm_data in farms_with_old_scans:
        farm_id = farm_data['farm']
        
        # Group by year-month
        farm_scans = old_scans.filter(farm_id=farm_id).extra(
            select={'month': "DATE_TRUNC('month', acquisition_date)"}
        ).values('month').annotate(
            count=Count('id'),
            oldest_id=Min('id')
        )
        
        for month_data in farm_scans:
            if month_data['count'] > 1:
                # Keep the oldest (first) scan of the month, delete others
                scans_to_delete = old_scans.filter(
                    farm_id=farm_id,
                    acquisition_date__gte=month_data['month']
                ).exclude(
                    id=month_data['oldest_id']
                )
                
                count = scans_to_delete.count()
                scans_to_delete.delete()
                deleted_count += count
    
    logger.info(f"Cleaned up {deleted_count} old satellite scans")
    return {
        'deleted_count': deleted_count,
        'timestamp': timezone.now().isoformat()
    }


@shared_task
def generate_health_alerts():
    """
    Generate health alerts for farms with declining NDVI
    Run daily via Celery beat
    """
    from .models import NDVIHistory, SatelliteScan
    from apps.notifications.models import Notification
    
    logger.info("Generating health alerts based on NDVI trends")
    
    alerts_created = 0
    
    # Get farms with recent scans
    recent_scans = SatelliteScan.objects.filter(
        acquisition_date__gte=timezone.now() - timedelta(days=7)
    ).select_related('farm', 'farm__farmer', 'farm__farmer__user')
    
    for scan in recent_scans:
        farm = scan.farm
        
        # Get NDVI history for last 30 days
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        history = NDVIHistory.objects.filter(
            farm=farm,
            date__gte=thirty_days_ago
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
            Notification.objects.create(
                user=farm.farmer.user,
                notification_type='farm_alert',
                title='Crop Health Alert',
                message=f'NDVI has declined by {decline_percentage:.1f}% on your farm {farm.farm_id}. '
                       f'Current health status: {scan.crop_health_status}. Please investigate.',
                action_url=f'/farms/{farm.farm_id}/monitor'
            )
            alerts_created += 1
            logger.info(f"Created health alert for farm {farm.farm_id}")
    
    logger.info(f"Created {alerts_created} health alerts")
    return {
        'alerts_created': alerts_created,
        'timestamp': timezone.now().isoformat()
    }