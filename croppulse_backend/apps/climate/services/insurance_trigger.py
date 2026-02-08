# apps/climate/services/insurance_trigger.py
from datetime import datetime, timedelta
from django.db.models import Sum, Avg
from apps.climate.models import ClimateData, ClimateRiskAssessment


class InsuranceTriggerService:
    """
    Calculate insurance triggers based on climate data
    Used for parametric/index-based agricultural insurance
    """
    
    def __init__(self, farm):
        self.farm = farm
    
    def check_drought_trigger(self, coverage_period_days=90, threshold_percentage=30):
        """
        Check if drought insurance should be triggered
        
        Args:
            coverage_period_days: int, insurance coverage period
            threshold_percentage: float, rainfall deficit % to trigger payout
        
        Returns:
            dict: Trigger status and payout calculation
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=coverage_period_days)
        
        # Get actual rainfall
        climate_data = ClimateData.objects.filter(
            farm=self.farm,
            date__gte=start_date,
            date__lte=end_date,
            is_forecast=False
        )
        
        if not climate_data.exists():
            return {
                'triggered': False,
                'reason': 'Insufficient data',
                'payout_percentage': 0
            }
        
        actual_rainfall = climate_data.aggregate(
            total=Sum('rainfall')
        )['total'] or 0.0
        
        # Expected rainfall (simplified: 100mm per 30 days)
        expected_rainfall = (coverage_period_days / 30) * 100
        
        # Calculate deficit
        rainfall_deficit_mm = expected_rainfall - actual_rainfall
        rainfall_deficit_percentage = (rainfall_deficit_mm / expected_rainfall * 100) if expected_rainfall > 0 else 0
        
        # Trigger if deficit exceeds threshold
        triggered = rainfall_deficit_percentage >= threshold_percentage
        
        # Calculate payout percentage (progressive scale)
        payout_percentage = 0
        if triggered:
            if rainfall_deficit_percentage >= 50:
                payout_percentage = 100  # Full payout
            elif rainfall_deficit_percentage >= 40:
                payout_percentage = 75
            elif rainfall_deficit_percentage >= threshold_percentage:
                payout_percentage = 50
        
        return {
            'triggered': triggered,
            'trigger_type': 'DROUGHT',
            'trigger_date': end_date,
            'coverage_period_days': coverage_period_days,
            'actual_rainfall_mm': round(actual_rainfall, 2),
            'expected_rainfall_mm': round(expected_rainfall, 2),
            'deficit_mm': round(rainfall_deficit_mm, 2),
            'deficit_percentage': round(rainfall_deficit_percentage, 2),
            'threshold_percentage': threshold_percentage,
            'payout_percentage': payout_percentage,
            'reason': f'Rainfall deficit of {rainfall_deficit_percentage:.1f}% exceeds {threshold_percentage}% threshold' if triggered else 'No trigger',
            'confidence': self._calculate_data_confidence(climate_data)
        }
    
    def check_excess_rainfall_trigger(self, coverage_period_days=30, threshold_mm=200):
        """
        Check if excess rainfall/flood insurance should be triggered
        
        Args:
            coverage_period_days: int, period to evaluate
            threshold_mm: float, total rainfall threshold
        
        Returns:
            dict: Trigger status and payout calculation
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=coverage_period_days)
        
        climate_data = ClimateData.objects.filter(
            farm=self.farm,
            date__gte=start_date,
            date__lte=end_date,
            is_forecast=False
        )
        
        if not climate_data.exists():
            return {
                'triggered': False,
                'reason': 'Insufficient data',
                'payout_percentage': 0
            }
        
        total_rainfall = climate_data.aggregate(
            total=Sum('rainfall')
        )['total'] or 0.0
        
        # Count heavy rainfall days
        heavy_rain_days = climate_data.filter(rainfall__gte=50).count()
        
        # Trigger if total rainfall exceeds threshold
        triggered = total_rainfall >= threshold_mm
        
        # Calculate payout (progressive)
        payout_percentage = 0
        if triggered:
            excess_percentage = ((total_rainfall - threshold_mm) / threshold_mm * 100)
            if excess_percentage >= 50:
                payout_percentage = 100
            elif excess_percentage >= 30:
                payout_percentage = 75
            else:
                payout_percentage = 50
        
        return {
            'triggered': triggered,
            'trigger_type': 'EXCESS_RAINFALL',
            'trigger_date': end_date,
            'coverage_period_days': coverage_period_days,
            'total_rainfall_mm': round(total_rainfall, 2),
            'threshold_mm': threshold_mm,
            'excess_mm': round(max(0, total_rainfall - threshold_mm), 2),
            'heavy_rain_days': heavy_rain_days,
            'payout_percentage': payout_percentage,
            'reason': f'Total rainfall ({total_rainfall:.1f}mm) exceeds {threshold_mm}mm threshold' if triggered else 'No trigger',
            'confidence': self._calculate_data_confidence(climate_data)
        }
    
    def check_heat_stress_trigger(self, coverage_period_days=30, threshold_temp=35, min_days=5):
        """
        Check if heat stress insurance should be triggered
        
        Args:
            coverage_period_days: int, period to evaluate
            threshold_temp: float, temperature threshold in Celsius
            min_days: int, minimum number of extreme heat days
        
        Returns:
            dict: Trigger status and payout calculation
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=coverage_period_days)
        
        climate_data = ClimateData.objects.filter(
            farm=self.farm,
            date__gte=start_date,
            date__lte=end_date,
            is_forecast=False
        )
        
        if not climate_data.exists():
            return {
                'triggered': False,
                'reason': 'Insufficient data',
                'payout_percentage': 0
            }
        
        # Count extreme heat days
        extreme_heat_days = climate_data.filter(
            temperature_max__gte=threshold_temp
        ).count()
        
        # Get average maximum temperature
        avg_max_temp = climate_data.aggregate(
            avg=Avg('temperature_max')
        )['avg'] or 0.0
        
        # Trigger if extreme heat days exceed minimum
        triggered = extreme_heat_days >= min_days
        
        # Calculate payout (based on number of extreme days)
        payout_percentage = 0
        if triggered:
            if extreme_heat_days >= 15:
                payout_percentage = 100
            elif extreme_heat_days >= 10:
                payout_percentage = 75
            else:
                payout_percentage = 50
        
        return {
            'triggered': triggered,
            'trigger_type': 'HEAT_STRESS',
            'trigger_date': end_date,
            'coverage_period_days': coverage_period_days,
            'extreme_heat_days': extreme_heat_days,
            'threshold_temperature': threshold_temp,
            'min_trigger_days': min_days,
            'average_max_temperature': round(avg_max_temp, 2),
            'payout_percentage': payout_percentage,
            'reason': f'{extreme_heat_days} extreme heat days exceeds {min_days} day threshold' if triggered else 'No trigger',
            'confidence': self._calculate_data_confidence(climate_data)
        }
    
    def check_all_triggers(self):
        """
        Check all insurance triggers
        
        Returns:
            dict: All trigger results
        """
        return {
            'farm_id': self.farm.id,
            'evaluation_date': datetime.now().date(),
            'drought_trigger': self.check_drought_trigger(),
            'excess_rainfall_trigger': self.check_excess_rainfall_trigger(),
            'heat_stress_trigger': self.check_heat_stress_trigger(),
            'overall_triggered': False  # Will be set below
        }
    
    def calculate_total_payout(self, policy_sum_insured):
        """
        Calculate total insurance payout based on all triggers
        
        Args:
            policy_sum_insured: float, total insured amount
        
        Returns:
            dict: Payout calculation
        """
        triggers = self.check_all_triggers()
        
        # Determine which trigger has the highest payout
        max_payout_percentage = 0
        triggered_perils = []
        
        for trigger_name in ['drought_trigger', 'excess_rainfall_trigger', 'heat_stress_trigger']:
            trigger = triggers[trigger_name]
            if trigger['triggered']:
                triggered_perils.append(trigger['trigger_type'])
                max_payout_percentage = max(max_payout_percentage, trigger['payout_percentage'])
        
        # Calculate payout amount
        payout_amount = (policy_sum_insured * max_payout_percentage / 100) if max_payout_percentage > 0 else 0
        
        return {
            'policy_sum_insured': policy_sum_insured,
            'triggered_perils': triggered_perils,
            'max_payout_percentage': max_payout_percentage,
            'payout_amount': round(payout_amount, 2),
            'currency': 'KES',  # Kenyan Shillings
            'triggers': triggers,
            'payout_eligible': len(triggered_perils) > 0
        }
    
    def generate_insurance_report(self, policy_details):
        """
        Generate comprehensive insurance trigger report
        
        Args:
            policy_details: dict with policy information
        
        Returns:
            dict: Detailed report
        """
        payout_calc = self.calculate_total_payout(policy_details.get('sum_insured', 0))
        
        # Get latest risk assessment
        latest_assessment = ClimateRiskAssessment.objects.filter(
            farm=self.farm
        ).order_by('-assessment_date').first()
        
        report = {
            'report_date': datetime.now(),
            'farm_id': self.farm.id,
            'policy_number': policy_details.get('policy_number', 'N/A'),
            'policy_period': policy_details.get('period', 'N/A'),
            'sum_insured': policy_details.get('sum_insured', 0),
            'payout_calculation': payout_calc,
            'risk_assessment': {
                'drought_risk': latest_assessment.drought_risk if latest_assessment else 0,
                'flood_risk': latest_assessment.flood_risk if latest_assessment else 0,
                'heat_stress_risk': latest_assessment.heat_stress_risk if latest_assessment else 0,
                'overall_climate_risk': latest_assessment.overall_climate_risk if latest_assessment else 0
            } if latest_assessment else None,
            'verification_status': 'VERIFIED' if payout_calc['payout_eligible'] else 'NO_CLAIM',
            'next_evaluation_date': datetime.now().date() + timedelta(days=7)
        }
        
        return report
    
    def _calculate_data_confidence(self, climate_data):
        """
        Calculate confidence level in the data
        
        Args:
            climate_data: QuerySet of ClimateData
        
        Returns:
            str: Confidence level
        """
        data_count = climate_data.count()
        
        if data_count == 0:
            return 'NO_DATA'
        elif data_count < 30:
            return 'LOW'
        elif data_count < 60:
            return 'MEDIUM'
        else:
            return 'HIGH'
    
    def get_trigger_thresholds_for_crop(self, crop_type='maize'):
        """
        Get insurance trigger thresholds specific to crop type
        
        Args:
            crop_type: str, type of crop
        
        Returns:
            dict: Recommended thresholds
        """
        # Crop-specific thresholds (simplified)
        thresholds = {
            'maize': {
                'drought_threshold_percentage': 30,
                'excess_rainfall_threshold_mm': 250,
                'heat_stress_threshold_temp': 35,
                'heat_stress_min_days': 5,
                'critical_growth_stages': ['flowering', 'grain_filling']
            },
            'wheat': {
                'drought_threshold_percentage': 25,
                'excess_rainfall_threshold_mm': 200,
                'heat_stress_threshold_temp': 32,
                'heat_stress_min_days': 7,
                'critical_growth_stages': ['tillering', 'grain_filling']
            },
            'rice': {
                'drought_threshold_percentage': 35,
                'excess_rainfall_threshold_mm': 300,
                'heat_stress_threshold_temp': 35,
                'heat_stress_min_days': 5,
                'critical_growth_stages': ['flowering', 'grain_filling']
            }
        }
        
        return thresholds.get(crop_type, thresholds['maize'])