# apps/climate/services/historical_analysis.py
from datetime import datetime, timedelta
from django.db.models import Avg, Max, Min, Sum
from apps.climate.models import ClimateData


class HistoricalAnalysisService:
    """Analyze historical climate patterns for farms"""
    
    def __init__(self, farm):
        self.farm = farm
    
    def get_40_year_average_rainfall(self, start_month, end_month):
        """
        Calculate 40-year average rainfall for a specific period
        Using NASA POWER historical data as baseline
        
        Args:
            start_month: int (1-12)
            end_month: int (1-12)
        
        Returns:
            float: Average rainfall in mm
        """
        # This would ideally fetch from a 40-year dataset
        # For now, we'll use available historical data
        historical_data = ClimateData.objects.filter(
            farm=self.farm,
            is_forecast=False,
            date__month__gte=start_month,
            date__month__lte=end_month
        )
        
        if not historical_data.exists():
            return 0.0
        
        avg_rainfall = historical_data.aggregate(
            avg=Avg('rainfall')
        )['avg']
        
        return avg_rainfall or 0.0
    
    def calculate_rainfall_anomaly(self, current_period_start, current_period_end):
        """
        Calculate deviation from historical average
        
        Args:
            current_period_start: date
            current_period_end: date
        
        Returns:
            dict: {
                'current_rainfall': float,
                'historical_average': float,
                'deviation_mm': float,
                'deviation_percentage': float,
                'status': str  # 'below_normal', 'normal', 'above_normal'
            }
        """
        # Get current period rainfall
        current_data = ClimateData.objects.filter(
            farm=self.farm,
            date__gte=current_period_start,
            date__lte=current_period_end,
            is_forecast=False
        )
        
        current_rainfall = current_data.aggregate(
            total=Sum('rainfall')
        )['total'] or 0.0
        
        # Get historical average for same months
        start_month = current_period_start.month
        end_month = current_period_end.month
        historical_avg = self.get_40_year_average_rainfall(start_month, end_month)
        
        # Calculate deviation
        deviation_mm = current_rainfall - historical_avg
        deviation_percentage = (deviation_mm / historical_avg * 100) if historical_avg > 0 else 0
        
        # Determine status
        if deviation_percentage < -20:
            status = 'below_normal'
        elif deviation_percentage > 20:
            status = 'above_normal'
        else:
            status = 'normal'
        
        return {
            'current_rainfall': round(current_rainfall, 2),
            'historical_average': round(historical_avg, 2),
            'deviation_mm': round(deviation_mm, 2),
            'deviation_percentage': round(deviation_percentage, 2),
            'status': status
        }
    
    def get_temperature_trends(self, days=30):
        """
        Analyze temperature trends over specified period
        
        Args:
            days: int, number of days to analyze
        
        Returns:
            dict: Temperature statistics and trends
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        climate_data = ClimateData.objects.filter(
            farm=self.farm,
            date__gte=start_date,
            date__lte=end_date,
            is_forecast=False
        ).order_by('date')
        
        if not climate_data.exists():
            return None
        
        stats = climate_data.aggregate(
            avg_temp=Avg('temperature_avg'),
            max_temp=Max('temperature_max'),
            min_temp=Min('temperature_min'),
            avg_max_temp=Avg('temperature_max'),
            avg_min_temp=Avg('temperature_min')
        )
        
        # Count extreme temperature days
        extreme_heat_days = climate_data.filter(temperature_max__gte=35).count()
        extreme_cold_days = climate_data.filter(temperature_min__lte=10).count()
        
        return {
            'period_days': days,
            'average_temperature': round(stats['avg_temp'], 2),
            'maximum_temperature': round(stats['max_temp'], 2),
            'minimum_temperature': round(stats['min_temp'], 2),
            'average_daily_max': round(stats['avg_max_temp'], 2),
            'average_daily_min': round(stats['avg_min_temp'], 2),
            'extreme_heat_days': extreme_heat_days,
            'extreme_cold_days': extreme_cold_days
        }
    
    def get_rainfall_distribution(self, start_date, end_date):
        """
        Get rainfall distribution across the period
        
        Returns:
            dict: Rainfall statistics
        """
        climate_data = ClimateData.objects.filter(
            farm=self.farm,
            date__gte=start_date,
            date__lte=end_date,
            is_forecast=False
        )
        
        if not climate_data.exists():
            return None
        
        total_rainfall = climate_data.aggregate(
            total=Sum('rainfall')
        )['total'] or 0.0
        
        rainy_days = climate_data.filter(rainfall__gt=1.0).count()
        heavy_rain_days = climate_data.filter(rainfall__gt=20.0).count()
        
        total_days = (end_date - start_date).days + 1
        
        return {
            'total_rainfall_mm': round(total_rainfall, 2),
            'total_days': total_days,
            'rainy_days': rainy_days,
            'heavy_rain_days': heavy_rain_days,
            'average_daily_rainfall': round(total_rainfall / total_days, 2),
            'dry_spell_days': total_days - rainy_days
        }
    
    def identify_dry_spells(self, days=90):
        """
        Identify consecutive days without significant rainfall
        
        Args:
            days: int, period to analyze
        
        Returns:
            list: Dry spell periods
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        climate_data = ClimateData.objects.filter(
            farm=self.farm,
            date__gte=start_date,
            date__lte=end_date,
            is_forecast=False
        ).order_by('date')
        
        dry_spells = []
        current_dry_spell = []
        
        for record in climate_data:
            if record.rainfall < 1.0:  # Less than 1mm considered dry
                current_dry_spell.append(record.date)
            else:
                if len(current_dry_spell) >= 7:  # 7+ consecutive dry days
                    dry_spells.append({
                        'start_date': current_dry_spell[0],
                        'end_date': current_dry_spell[-1],
                        'duration_days': len(current_dry_spell)
                    })
                current_dry_spell = []
        
        # Check if we're currently in a dry spell
        if len(current_dry_spell) >= 7:
            dry_spells.append({
                'start_date': current_dry_spell[0],
                'end_date': current_dry_spell[-1],
                'duration_days': len(current_dry_spell),
                'ongoing': True
            })
        
        return dry_spells
    
    def get_growing_season_suitability(self, crop_type='maize'):
        """
        Assess current growing season suitability
        
        Args:
            crop_type: str, type of crop
        
        Returns:
            dict: Suitability assessment
        """
        # Last 30 days analysis
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        
        climate_data = ClimateData.objects.filter(
            farm=self.farm,
            date__gte=start_date,
            date__lte=end_date,
            is_forecast=False
        )
        
        if not climate_data.exists():
            return None
        
        stats = climate_data.aggregate(
            avg_temp=Avg('temperature_avg'),
            total_rainfall=Sum('rainfall'),
            avg_humidity=Avg('humidity')
        )
        
        # Crop-specific thresholds (simplified)
        crop_requirements = {
            'maize': {
                'optimal_temp_min': 18,
                'optimal_temp_max': 32,
                'min_monthly_rainfall': 50,
                'optimal_monthly_rainfall': 100
            },
            'wheat': {
                'optimal_temp_min': 12,
                'optimal_temp_max': 25,
                'min_monthly_rainfall': 30,
                'optimal_monthly_rainfall': 75
            }
        }
        
        requirements = crop_requirements.get(crop_type, crop_requirements['maize'])
        
        # Assess suitability
        temp_suitable = (requirements['optimal_temp_min'] <= 
                        stats['avg_temp'] <= 
                        requirements['optimal_temp_max'])
        
        rainfall_suitable = stats['total_rainfall'] >= requirements['min_monthly_rainfall']
        
        if temp_suitable and rainfall_suitable:
            suitability = 'optimal'
        elif temp_suitable or rainfall_suitable:
            suitability = 'moderate'
        else:
            suitability = 'poor'
        
        return {
            'crop_type': crop_type,
            'suitability': suitability,
            'average_temperature': round(stats['avg_temp'], 2),
            'total_rainfall': round(stats['total_rainfall'], 2),
            'average_humidity': round(stats['avg_humidity'], 2),
            'temperature_suitable': temp_suitable,
            'rainfall_suitable': rainfall_suitable
        }