# Insurance Fraud Detection Engine

from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from apps.farmers.models import Farmer
from apps.farms.models import Farm
from apps.farmers.models_verification import GroundTruthReport
from apps.satellite.models import SatelliteScan
import logging

logger = logging.getLogger(__name__)

class InsuranceFraudDetector:
    """Detect fraudulent insurance claims"""
    
    def verify_claim(self, farmer, claim_data):
        """Verify insurance claim against multiple data sources"""
        
        farm_id = claim_data.get('farm_id')
        claim_date = claim_data.get('date')
        claim_type = claim_data.get('type')  # drought, flood, pest, etc.
        
        verification = {
            'farmer_id': farmer.id,
            'claim_type': claim_type,
            'verified': False,
            'confidence': 0,
            'evidence': []
        }
        
        # 1. Check satellite data
        satellite_evidence = self._check_satellite_evidence(farm_id, claim_date, claim_type)
        if satellite_evidence['supports_claim']:
            verification['confidence'] += 30
            verification['evidence'].append(satellite_evidence)
        
        # 2. Check neighbor reports
        neighbor_evidence = self._check_neighbor_reports(farm_id, claim_date, claim_type)
        if neighbor_evidence['supports_claim']:
            verification['confidence'] += 40
            verification['evidence'].append(neighbor_evidence)
        
        # 3. Check farmer's own reports
        farmer_evidence = self._check_farmer_reports(farmer, claim_date, claim_type)
        if farmer_evidence['supports_claim']:
            verification['confidence'] += 30
            verification['evidence'].append(farmer_evidence)
        
        # Verdict
        verification['verified'] = verification['confidence'] >= 60
        verification['recommendation'] = self._get_recommendation(verification['confidence'])
        
        return verification
    
    def _check_satellite_evidence(self, farm_id, claim_date, claim_type):
        """Check satellite data for claim evidence"""
        
        try:
            # Get scans around claim date (±7 days)
            start_date = claim_date - timedelta(days=7)
            end_date = claim_date + timedelta(days=7)
            
            scans = SatelliteScan.objects.filter(
                farm_id=farm_id,
                scan_date__range=[start_date, end_date],
                status='completed'
            ).order_by('-scan_date')
            
            if not scans.exists():
                return {'supports_claim': False, 'reason': 'No satellite data available'}
            
            latest_scan = scans.first()
            
            # Check based on claim type
            if claim_type == 'drought':
                # Low NDVI indicates drought stress
                supports = latest_scan.ndvi_mean < 0.3
                return {
                    'supports_claim': supports,
                    'source': 'satellite',
                    'ndvi': latest_scan.ndvi_mean,
                    'health_status': latest_scan.health_status
                }
            
            elif claim_type == 'flood':
                # SAR data shows flooding
                supports = latest_scan.sar_vv_mean and latest_scan.sar_vv_mean < -15
                return {
                    'supports_claim': supports,
                    'source': 'satellite',
                    'sar_data': latest_scan.sar_vv_mean
                }
            
            return {'supports_claim': False, 'reason': 'Claim type not supported'}
            
        except Exception as e:
            logger.error(f"Satellite check error: {e}")
            return {'supports_claim': False, 'error': str(e)}
    
    def _check_neighbor_reports(self, farm_id, claim_date, claim_type):
        """Cross-verify with neighboring farmers' reports"""
        
        try:
            farm = Farm.objects.get(id=farm_id)
            
            # Find nearby farms (within 5km)
            nearby_farms = Farm.objects.filter(
                county=farm.county
            ).exclude(id=farm_id)[:10]
            
            if not nearby_farms:
                return {'supports_claim': False, 'reason': 'No neighbors found'}
            
            # Check their weather reports around claim date
            start_date = claim_date - timedelta(days=3)
            end_date = claim_date + timedelta(days=3)
            
            neighbor_reports = GroundTruthReport.objects.filter(
                farm__in=nearby_farms,
                weather_time__range=[start_date, end_date],
                verified=True
            )
            
            if not neighbor_reports.exists():
                return {'supports_claim': False, 'reason': 'No neighbor reports'}
            
            # Count matching conditions
            matching_conditions = self._map_claim_to_weather(claim_type)
            matching_count = neighbor_reports.filter(
                weather_condition__in=matching_conditions
            ).count()
            
            total_reports = neighbor_reports.count()
            agreement_rate = matching_count / total_reports if total_reports > 0 else 0
            
            return {
                'supports_claim': agreement_rate >= 0.5,  # 50% agreement
                'source': 'neighbors',
                'agreement_rate': agreement_rate,
                'matching_reports': matching_count,
                'total_reports': total_reports
            }
            
        except Exception as e:
            logger.error(f"Neighbor check error: {e}")
            return {'supports_claim': False, 'error': str(e)}
    
    def _check_farmer_reports(self, farmer, claim_date, claim_type):
        """Check farmer's own historical reports"""
        
        try:
            # Check reports around claim date
            start_date = claim_date - timedelta(days=7)
            end_date = claim_date + timedelta(days=7)
            
            reports = GroundTruthReport.objects.filter(
                farmer=farmer,
                weather_time__range=[start_date, end_date]
            )
            
            if not reports.exists():
                return {'supports_claim': False, 'reason': 'No farmer reports'}
            
            matching_conditions = self._map_claim_to_weather(claim_type)
            matching_count = reports.filter(
                weather_condition__in=matching_conditions
            ).count()
            
            return {
                'supports_claim': matching_count > 0,
                'source': 'farmer_reports',
                'matching_reports': matching_count
            }
            
        except Exception as e:
            logger.error(f"Farmer report check error: {e}")
            return {'supports_claim': False, 'error': str(e)}
    
    def _map_claim_to_weather(self, claim_type):
        """Map claim type to weather conditions"""
        mapping = {
            'drought': ['clear', 'cloudy'],
            'flood': ['heavy_rain', 'storm'],
            'storm': ['storm', 'windy'],
            'frost': ['very_cold'],
        }
        return mapping.get(claim_type, [])
    
    def _get_recommendation(self, confidence):
        """Get claim recommendation based on confidence"""
        if confidence >= 80:
            return 'APPROVE - Strong evidence'
        elif confidence >= 60:
            return 'APPROVE - Sufficient evidence'
        elif confidence >= 40:
            return 'INVESTIGATE - Weak evidence'
        else:
            return 'REJECT - Insufficient evidence'
