# apps/climate/services/risk_calculator.py
from datetime import datetime, timedelta
from django.db.models import Avg, Sum, Max, Min
from apps.climate.models import ClimateData, ClimateRiskAssessment


class RiskCalculator:
    """Calculate climate-related risks for farms"""
    
    # Risk thresholds
    DROUGHT_RAINFALL_THRESHOLD = 50  # mm per month
    FLOOD_DAILY_RAINFALL_THRESHOLD = 50  # mm per day
    HEAT_STRESS_TEMPERATURE = 35  # Celsius
    EXTREME_COLD_TEMPERATURE = 10  # Celsius
    
    def __init__(self, farm):
        self.farm = farm
    
    def calculate_drought_risk(self, days=90):
        """
        Calculate drought risk based on rainfall deficit
        
        Args:
            days: int, period to analyze
        
        Returns:
            float: Risk score (0-100)
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        climate_data = ClimateData.objects.filter(
            farm=self.farm,
            date__gte=start_date,
            date__lte=end_date,
            is_forecast=False
        )
        
        if not climate_data.exists():
            return 0.0
        
        # Calculate total rainfall
        total_rainfall = climate_data.aggregate(
            total=Sum('rainfall')
        )['total'] or 0.0
        
        # Expected rainfall (approximation: 100mm per 30 days)
        expected_rainfall = (days / 30) * 100
        
        # Calculate deficit
        rainfall_deficit = max(0, expected_rainfall - total_rainfall)
        deficit_percentage = (rainfall_deficit / expected_rainfall * 100) if expected_rainfall > 0 else 0
        
        # Count consecutive dry days
        dry_spell_days = self._count_longest_dry_spell(climate_data)
        
        # Risk scoring
        rainfall_risk = min(100, deficit_percentage)
        dry_spell_risk = min(100, (dry_spell_days / 21) * 100)  # 21 days = max risk
        
        # Weighted average
        drought_risk = (rainfall_risk * 0.7) + (dry_spell_risk * 0.3)
        
        return round(drought_risk, 2)
    
    def calculate_flood_risk(self, days=30):
        """
        Calculate flood risk based on excessive rainfall
        
        Args:
            days: int, period to analyze
        
        Returns:
            float: Risk score (0-100)
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        climate_data = ClimateData.objects.filter(
            farm=self.farm,
            date__gte=start_date,
            date__lte=end_date,
            is_forecast=False
        )
        
        if not climate_data.exists():
            return 0.0
        
        # Count heavy rainfall days
        heavy_rain_days = climate_data.filter(
            rainfall__gte=self.FLOOD_DAILY_RAINFALL_THRESHOLD
        ).count()
        
        # Get maximum single-day rainfall
        max_rainfall = climate_data.aggregate(
            max_rain=Max('rainfall')
        )['max_rain'] or 0.0
        
        # Calculate total rainfall
        total_rainfall = climate_data.aggregate(
            total=Sum('rainfall')
        )['total'] or 0.0
        
        # Risk factors
        heavy_rain_risk = min(100, (heavy_rain_days / 5) * 100)  # 5+ days = high risk
        extreme_rainfall_risk = min(100, (max_rainfall / 100) * 100)  # 100mm+ = max risk
        total_rainfall_risk = min(100, (total_rainfall / 300) * 100)  # 300mm+ in 30 days = max risk
        
        # Weighted average
        flood_risk = (heavy_rain_risk * 0.4) + (extreme_rainfall_risk * 0.4) + (total_rainfall_risk * 0.2)
        
        return round(flood_risk, 2)
    
    def calculate_heat_stress_risk(self, days=30):
        """
        Calculate heat stress risk for crops
        
        Args:
            days: int, period to analyze
        
        Returns:
            float: Risk score (0-100)
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        climate_data = ClimateData.objects.filter(
            farm=self.farm,
            date__gte=start_date,
            date__lte=end_date,
            is_forecast=False
        )
        
        if not climate_data.exists():
            return 0.0
        
        # Count extreme heat days
        extreme_heat_days = climate_data.filter(
            temperature_max__gte=self.HEAT_STRESS_TEMPERATURE
        ).count()
        
        # Get average maximum temperature
        avg_max_temp = climate_data.aggregate(
            avg=Avg('temperature_max')
        )['avg'] or 0.0
        
        # Get maximum temperature
        max_temp = climate_data.aggregate(
            max=Max('temperature_max')
        )['max'] or 0.0
        
        # Risk factors
        extreme_days_risk = min(100, (extreme_heat_days / 10) * 100)  # 10+ days = max risk
        avg_temp_risk = min(100, max(0, (avg_max_temp - 30) / 10 * 100))  # Above 30°C increases risk
        max_temp_risk = min(100, max(0, (max_temp - 35) / 10 * 100))  # Above 35°C is critical
        
        # Weighted average
        heat_stress_risk = (extreme_days_risk * 0.5) + (avg_temp_risk * 0.3) + (max_temp_risk * 0.2)
        
        return round(heat_stress_risk, 2)
    
    def calculate_overall_risk(self, drought_risk, flood_risk, heat_stress_risk):
        """
        Calculate overall climate risk score
        
        Args:
            drought_risk: float
            flood_risk: float
            heat_stress_risk: float
        
        Returns:
            float: Overall risk score (0-100)
        """
        # Weighted average based on regional importance
        # Adjust weights based on local climate patterns
        overall_risk = (
            drought_risk * 0.4 +
            flood_risk * 0.3 +
            heat_stress_risk * 0.3
        )
        
        return round(overall_risk, 2)
    
    def generate_recommendations(self, drought_risk, flood_risk, heat_stress_risk):
        """
        Generate actionable recommendations based on risk levels
        
        Returns:
            list: List of recommendation strings
        """
        recommendations = []
        
        # Drought recommendations
        if drought_risk >= 70:
            recommendations.append({
                'type': 'CRITICAL',
                'category': 'drought',
                'message': 'Critical drought risk detected. Consider drought-resistant crop varieties and implement water conservation measures immediately.',
                'actions': [
                    'Apply mulching to retain soil moisture',
                    'Consider supplementary irrigation if available',
                    'Monitor crop stress daily',
                    'Prepare for potential crop failure'
                ]
            })
        elif drought_risk >= 40:
            recommendations.append({
                'type': 'WARNING',
                'category': 'drought',
                'message': 'Moderate drought risk. Monitor water availability closely.',
                'actions': [
                    'Implement water conservation practices',
                    'Monitor soil moisture levels',
                    'Consider early harvesting if conditions worsen'
                ]
            })
        
        # Flood recommendations
        if flood_risk >= 70:
            recommendations.append({
                'type': 'CRITICAL',
                'category': 'flood',
                'message': 'High flood risk detected. Take immediate protective measures.',
                'actions': [
                    'Ensure proper drainage systems are clear',
                    'Avoid planting in low-lying areas',
                    'Harvest mature crops before heavy rains',
                    'Prepare for potential waterlogging'
                ]
            })
        elif flood_risk >= 40:
            recommendations.append({
                'type': 'WARNING',
                'category': 'flood',
                'message': 'Moderate flood risk. Monitor rainfall patterns.',
                'actions': [
                    'Check drainage systems',
                    'Monitor weather forecasts',
                    'Prepare flood mitigation measures'
                ]
            })
        
        # Heat stress recommendations
        if heat_stress_risk >= 70:
            recommendations.append({
                'type': 'CRITICAL',
                'category': 'heat_stress',
                'message': 'Extreme heat stress risk. Crops may suffer severe damage.',
                'actions': [
                    'Increase irrigation frequency if possible',
                    'Apply shade netting for sensitive crops',
                    'Monitor crop health daily',
                    'Consider heat-tolerant varieties for next season'
                ]
            })
        elif heat_stress_risk >= 40:
            recommendations.append({
                'type': 'WARNING',
                'category': 'heat_stress',
                'message': 'Moderate heat stress risk. Monitor crop condition.',
                'actions': [
                    'Ensure adequate soil moisture',
                    'Monitor for signs of heat stress',
                    'Adjust irrigation schedule'
                ]
            })
        
        # General low-risk recommendations
        if drought_risk < 40 and flood_risk < 40 and heat_stress_risk < 40:
            recommendations.append({
                'type': 'INFO',
                'category': 'general',
                'message': 'Climate conditions are currently favorable for crop growth.',
                'actions': [
                    'Maintain regular farming practices',
                    'Continue monitoring weather patterns',
                    'Plan for optimal planting/harvesting windows'
                ]
            })
        
        return recommendations
    
    def create_risk_assessment(self, analysis_period_days=90):
        """
        Create a comprehensive risk assessment
        
        Args:
            analysis_period_days: int, period to analyze
        
        Returns:
            ClimateRiskAssessment: Saved assessment object
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=analysis_period_days)
        
        # Calculate individual risks
        drought_risk = self.calculate_drought_risk(analysis_period_days)
        flood_risk = self.calculate_flood_risk(min(analysis_period_days, 30))
        heat_stress_risk = self.calculate_heat_stress_risk(min(analysis_period_days, 30))
        overall_risk = self.calculate_overall_risk(drought_risk, flood_risk, heat_stress_risk)
        
        # Generate recommendations
        recommendations = self.generate_recommendations(drought_risk, flood_risk, heat_stress_risk)
        
        # Get rainfall statistics
        from apps.climate.services.historical_analysis import HistoricalAnalysisService
        historical_service = HistoricalAnalysisService(self.farm)
        rainfall_anomaly = historical_service.calculate_rainfall_anomaly(start_date, end_date)
        
        # Create assessment
        assessment = ClimateRiskAssessment.objects.create(
            farm=self.farm,
            drought_risk=drought_risk,
            flood_risk=flood_risk,
            heat_stress_risk=heat_stress_risk,
            overall_climate_risk=overall_risk,
            analysis_start_date=start_date,
            analysis_end_date=end_date,
            historical_rainfall_avg=rainfall_anomaly['historical_average'],
            current_season_rainfall=rainfall_anomaly['current_rainfall'],
            rainfall_deviation_percentage=rainfall_anomaly['deviation_percentage'],
            recommendations=recommendations
        )
        
        return assessment
    
    def _count_longest_dry_spell(self, climate_data):
        """
        Count the longest consecutive dry period
        
        Args:
            climate_data: QuerySet of ClimateData
        
        Returns:
            int: Longest dry spell in days
        """
        max_dry_spell = 0
        current_dry_spell = 0
        
        for record in climate_data.order_by('date'):
            if record.rainfall < 1.0:
                current_dry_spell += 1
                max_dry_spell = max(max_dry_spell, current_dry_spell)
            else:
                current_dry_spell = 0
        
        return max_dry_spell
    
    def get_risk_level_label(self, risk_score):
        """
        Convert risk score to human-readable label
        
        Args:
            risk_score: float (0-100)
        
        Returns:
            str: Risk level label
        """
        if risk_score >= 70:
            return 'CRITICAL'
        elif risk_score >= 40:
            return 'HIGH'
        elif risk_score >= 20:
            return 'MODERATE'
        else:
            return 'LOW'