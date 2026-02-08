# compliance/services/deforestation.py
from django.utils import timezone
from datetime import datetime, timedelta
import logging
from ..models import DeforestationCheck, ExportPassport

logger = logging.getLogger(__name__)


class DeforestationAnalyzer:
    """Analyze satellite data for deforestation detection"""
    
    def __init__(self):
        self.baseline_date = datetime(2020, 12, 31).date()
        self.ndvi_threshold = 0.3  # Threshold for vegetation
        self.change_threshold = -0.1  # Significant change threshold
    
    def analyze_farm(self, farm, start_date=None, end_date=None, check_type='PERIODIC'):
        """
        Perform deforestation analysis on a farm
        
        Args:
            farm: Farm instance
            start_date: Analysis start date (default: baseline)
            end_date: Analysis end date (default: today)
            check_type: Type of check
        
        Returns:
            DeforestationCheck instance
        """
        if not start_date:
            start_date = self.baseline_date
        
        if not end_date:
            end_date = timezone.now().date()
        
        # Create deforestation check record
        check = DeforestationCheck.objects.create(
            farm=farm,
            check_type=check_type,
            analysis_start_date=start_date,
            analysis_end_date=end_date,
            baseline_date=self.baseline_date,
            status='IN_PROGRESS'
        )
        
        try:
            # Get satellite data from satellite app
            from apps.satellite.services.ndvi_calculator import NDVICalculator
            from apps.satellite.services.sentinel_service import SentinelService
            
            ndvi_calculator = NDVICalculator()
            sentinel_service = SentinelService()
            
            # Get farm boundary
            boundary = farm.get_boundary_geojson()
            
            # Get baseline NDVI
            baseline_ndvi = ndvi_calculator.calculate_for_period(
                boundary,
                self.baseline_date - timedelta(days=30),
                self.baseline_date
            )
            
            # Get current NDVI
            current_ndvi = ndvi_calculator.calculate_for_period(
                boundary,
                end_date - timedelta(days=30),
                end_date
            )
            
            # Calculate forest cover
            baseline_forest_cover = self._calculate_forest_cover(baseline_ndvi)
            current_forest_cover = self._calculate_forest_cover(current_ndvi)
            
            # Calculate change
            forest_change = current_forest_cover - baseline_forest_cover
            ndvi_change = current_ndvi['mean'] - baseline_ndvi['mean']
            
            # Estimate forest loss in hectares
            if forest_change < 0:
                forest_loss_hectares = abs(forest_change / 100 * float(farm.area_hectares))
            else:
                forest_loss_hectares = 0
            
            # Determine if deforestation detected
            deforestation_detected = (
                forest_change < -5  # More than 5% forest loss
                or ndvi_change < self.change_threshold
            )
            
            # Get satellite imagery URLs
            imagery_urls = sentinel_service.get_imagery_urls(
                boundary,
                start_date,
                end_date
            )
            
            # Get cloud cover info
            cloud_cover = sentinel_service.get_cloud_cover(
                boundary,
                end_date - timedelta(days=7),
                end_date
            )
            
            # Update check record
            check.deforestation_detected = deforestation_detected
            check.forest_cover_percentage = current_forest_cover
            check.baseline_forest_cover = baseline_forest_cover
            check.change_in_forest_cover = forest_change
            check.forest_loss_hectares = forest_loss_hectares
            check.ndvi_baseline = baseline_ndvi['mean']
            check.ndvi_current = current_ndvi['mean']
            check.ndvi_change = ndvi_change
            check.satellite_provider = 'SENTINEL2'
            check.satellite_imagery_urls = imagery_urls
            check.cloud_cover_percentage = cloud_cover
            check.confidence_score = self._calculate_confidence(cloud_cover, current_ndvi)
            check.status = 'COMPLETED'
            
            # Determine result
            if deforestation_detected:
                if forest_change < -10:
                    check.result = 'VIOLATION'
                else:
                    check.result = 'WARNING'
            else:
                check.result = 'CLEAR'
            
            # Calculate risk score
            check.calculate_risk_score()
            
            # Add risk factors
            risk_factors = self._identify_risk_factors(check)
            check.risk_factors = risk_factors
            
            # Save
            check.save()
            
            # Update associated passport if exists
            self._update_passport_status(farm, check)
            
            logger.info(
                f"Deforestation analysis completed for farm {farm.id}: "
                f"Result={check.result}, Risk={check.risk_score}"
            )
            
            return check
            
        except Exception as e:
            logger.error(f"Deforestation analysis failed for farm {farm.id}: {str(e)}")
            check.status = 'FAILED'
            check.analysis_metadata = {'error': str(e)}
            check.save()
            raise
    
    def _calculate_forest_cover(self, ndvi_data):
        """
        Estimate forest cover percentage from NDVI
        
        Args:
            ndvi_data: Dict with NDVI statistics
        
        Returns:
            float: Estimated forest cover percentage
        """
        mean_ndvi = ndvi_data.get('mean', 0)
        
        # Simple linear mapping (can be refined with ML)
        # NDVI > 0.6: Dense forest (100%)
        # NDVI 0.3-0.6: Partial forest (linear scale)
        # NDVI < 0.3: No forest (0%)
        
        if mean_ndvi >= 0.6:
            return 100.0
        elif mean_ndvi >= 0.3:
            # Linear interpolation
            return ((mean_ndvi - 0.3) / 0.3) * 100
        else:
            return 0.0
    
    def _calculate_confidence(self, cloud_cover, ndvi_data):
        """
        Calculate confidence score for analysis
        
        Args:
            cloud_cover: Cloud cover percentage
            ndvi_data: NDVI statistics
        
        Returns:
            float: Confidence score (0-1)
        """
        confidence = 1.0
        
        # Reduce confidence based on cloud cover
        if cloud_cover:
            if cloud_cover > 50:
                confidence *= 0.5
            elif cloud_cover > 30:
                confidence *= 0.7
            elif cloud_cover > 10:
                confidence *= 0.9
        
        # Reduce confidence if NDVI variance is high (inconsistent data)
        ndvi_std = ndvi_data.get('std', 0)
        if ndvi_std > 0.2:
            confidence *= 0.8
        elif ndvi_std > 0.15:
            confidence *= 0.9
        
        return confidence
    
    def _identify_risk_factors(self, check):
        """
        Identify specific risk factors
        
        Args:
            check: DeforestationCheck instance
        
        Returns:
            list: List of risk factor descriptions
        """
        risk_factors = []
        
        if check.change_in_forest_cover < -10:
            risk_factors.append("Severe forest cover loss detected (>10%)")
        elif check.change_in_forest_cover < -5:
            risk_factors.append("Moderate forest cover loss detected (5-10%)")
        
        if check.ndvi_change and check.ndvi_change < -0.2:
            risk_factors.append("Significant vegetation decline (NDVI drop >0.2)")
        
        if check.deforestation_detected:
            risk_factors.append("Deforestation alert triggered")
        
        if check.confidence_score and check.confidence_score < 0.7:
            risk_factors.append("Low confidence due to data quality issues")
        
        if check.cloud_cover_percentage and check.cloud_cover_percentage > 30:
            risk_factors.append(f"High cloud cover ({check.cloud_cover_percentage:.1f}%)")
        
        if not risk_factors:
            risk_factors.append("No significant risk factors identified")
        
        return risk_factors
    
    def _update_passport_status(self, farm, check):
        """
        Update export passport status based on deforestation check
        
        Args:
            farm: Farm instance
            check: DeforestationCheck instance
        """
        try:
            # Get active passports for this farm
            passports = ExportPassport.objects.filter(
                farm=farm,
                is_active=True
            )
            
            for passport in passports:
                # Link check to passport
                check.export_passport = passport
                check.save()
                
                # Update passport status based on result
                if check.result == 'VIOLATION':
                    passport.deforestation_status = 'FLAGGED'
                    passport.risk_level = 'HIGH'
                elif check.result == 'WARNING':
                    passport.deforestation_status = 'UNDER_REVIEW'
                    if check.risk_score > 50:
                        passport.risk_level = 'HIGH'
                    else:
                        passport.risk_level = 'STANDARD'
                elif check.result == 'CLEAR':
                    passport.deforestation_status = 'CLEAR'
                    passport.risk_level = 'LOW'
                
                passport.satellite_analysis_date = check.check_date
                passport.save(update_fields=[
                    'deforestation_status',
                    'risk_level',
                    'satellite_analysis_date'
                ])
                
                # Add audit entry
                passport.add_audit_entry(
                    action='DEFORESTATION_CHECK',
                    user='system',
                    details={
                        'check_id': str(check.id),
                        'result': check.result,
                        'risk_score': check.risk_score,
                        'forest_change': float(check.change_in_forest_cover)
                    }
                )
        
        except Exception as e:
            logger.error(f"Failed to update passport status: {str(e)}")
    
    def batch_analyze(self, farms, start_date=None, end_date=None):
        """
        Perform batch deforestation analysis
        
        Args:
            farms: QuerySet or list of Farm instances
            start_date: Analysis start date
            end_date: Analysis end date
        
        Returns:
            list: Results for each farm
        """
        results = []
        
        for farm in farms:
            try:
                check = self.analyze_farm(farm, start_date, end_date)
                results.append({
                    'farm_id': str(farm.id),
                    'farm_name': farm.farm_name,
                    'success': True,
                    'check_id': str(check.id),
                    'result': check.result,
                    'risk_score': check.risk_score
                })
            except Exception as e:
                results.append({
                    'farm_id': str(farm.id),
                    'farm_name': farm.farm_name,
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    def get_high_risk_farms(self, threshold=70):
        """
        Get farms with high deforestation risk
        
        Args:
            threshold: Risk score threshold (0-100)
        
        Returns:
            QuerySet: High-risk deforestation checks
        """
        return DeforestationCheck.objects.filter(
            risk_score__gte=threshold,
            status='COMPLETED'
        ).select_related('farm', 'farm__farmer').order_by('-risk_score')
    
    def get_flagged_farms(self):
        """Get farms with deforestation violations"""
        return DeforestationCheck.objects.filter(
            result='VIOLATION',
            status='COMPLETED'
        ).select_related('farm', 'farm__farmer')
    
    def generate_summary_report(self, start_date, end_date):
        """
        Generate summary report for deforestation checks
        
        Args:
            start_date: Report start date
            end_date: Report end date
        
        Returns:
            dict: Summary statistics
        """
        checks = DeforestationCheck.objects.filter(
            check_date__gte=start_date,
            check_date__lte=end_date,
            status='COMPLETED'
        )
        
        total_checks = checks.count()
        
        if total_checks == 0:
            return {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'total_checks': 0,
                'message': 'No checks performed in this period'
            }
        
        clear_count = checks.filter(result='CLEAR').count()
        warning_count = checks.filter(result='WARNING').count()
        violation_count = checks.filter(result='VIOLATION').count()
        
        avg_risk_score = checks.aggregate(
            models.Avg('risk_score')
        )['risk_score__avg'] or 0
        
        avg_forest_cover = checks.aggregate(
            models.Avg('forest_cover_percentage')
        )['forest_cover_percentage__avg'] or 0
        
        avg_change = checks.aggregate(
            models.Avg('change_in_forest_cover')
        )['change_in_forest_cover__avg'] or 0
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_checks': total_checks,
            'results': {
                'clear': clear_count,
                'warning': warning_count,
                'violation': violation_count
            },
            'percentages': {
                'clear': (clear_count / total_checks) * 100,
                'warning': (warning_count / total_checks) * 100,
                'violation': (violation_count / total_checks) * 100
            },
            'averages': {
                'risk_score': round(avg_risk_score, 2),
                'forest_cover': round(avg_forest_cover, 2),
                'forest_change': round(avg_change, 2)
            }
        }