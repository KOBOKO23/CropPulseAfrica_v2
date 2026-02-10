# Logistics Intelligence Engine

from django.utils import timezone
from datetime import timedelta
from apps.climate.models import ClimateData
from apps.farms.models import Farm
import logging

logger = logging.getLogger(__name__)

class LogisticsIntelligence:
    """Optimize harvest timing and logistics"""
    
    def analyze_harvest_window(self, farm_id):
        """Determine optimal harvest timing"""
        
        try:
            farm = Farm.objects.get(id=farm_id)
            
            # Get 7-day forecast
            forecast = self._get_weather_forecast(farm, days=7)
            
            # Analyze road conditions
            road_risk = self._assess_road_conditions(farm, forecast)
            
            # Calculate optimal window
            optimal_days = self._calculate_optimal_days(forecast, road_risk)
            
            return {
                'farm_id': farm_id,
                'current_date': timezone.now().date(),
                'optimal_harvest_date': optimal_days[0] if optimal_days else None,
                'harvest_window': optimal_days,
                'road_risk': road_risk,
                'recommendations': self._generate_recommendations(optimal_days, road_risk),
                'urgency': self._calculate_urgency(optimal_days, road_risk)
            }
            
        except Exception as e:
            logger.error(f"Harvest analysis error: {e}")
            return {'error': str(e)}
    
    def _get_weather_forecast(self, farm, days=7):
        """Get weather forecast for farm location"""
        
        today = timezone.now().date()
        forecast_dates = [today + timedelta(days=i) for i in range(days)]
        
        # Get climate data (forecast or historical)
        climate_data = ClimateData.objects.filter(
            latitude=farm.latitude,
            longitude=farm.longitude,
            date__in=forecast_dates
        ).order_by('date')
        
        forecast = []
        for data in climate_data:
            forecast.append({
                'date': data.date,
                'rainfall': float(data.rainfall) if data.rainfall else 0,
                'temperature': float(data.temperature_avg) if data.temperature_avg else 25,
                'humidity': float(data.humidity) if data.humidity else 70,
                'wind_speed': float(data.wind_speed) if data.wind_speed else 10,
            })
        
        return forecast
    
    def _assess_road_conditions(self, farm, forecast):
        """Assess road accessibility based on rainfall"""
        
        # Calculate cumulative rainfall
        total_rainfall = sum(day['rainfall'] for day in forecast)
        
        # Assess risk
        if total_rainfall > 100:  # Heavy rain expected
            return {
                'risk_level': 'HIGH',
                'days_until_closure': 2,
                'reason': 'Heavy rainfall expected (>100mm)',
                'accessibility': 'Roads may close in 2-3 days'
            }
        elif total_rainfall > 50:
            return {
                'risk_level': 'MEDIUM',
                'days_until_closure': 4,
                'reason': 'Moderate rainfall expected (50-100mm)',
                'accessibility': 'Roads passable but deteriorating'
            }
        else:
            return {
                'risk_level': 'LOW',
                'days_until_closure': None,
                'reason': 'Light rainfall expected (<50mm)',
                'accessibility': 'Roads accessible'
            }
    
    def _calculate_optimal_days(self, forecast, road_risk):
        """Calculate best days for harvest"""
        
        optimal_days = []
        
        for day in forecast:
            # Good harvest conditions:
            # - Low rainfall (<5mm)
            # - Moderate temperature (20-30°C)
            # - Low humidity (<80%)
            
            if (day['rainfall'] < 5 and 
                20 <= day['temperature'] <= 30 and 
                day['humidity'] < 80):
                optimal_days.append(day['date'])
        
        # If road risk is high, prioritize earlier days
        if road_risk['risk_level'] == 'HIGH' and optimal_days:
            optimal_days = optimal_days[:2]  # Only first 2 days
        
        return optimal_days
    
    def _generate_recommendations(self, optimal_days, road_risk):
        """Generate actionable recommendations"""
        
        recommendations = []
        
        if not optimal_days:
            recommendations.append("⚠️ No optimal harvest days in next 7 days")
            recommendations.append("Consider waiting for better weather")
        else:
            recommendations.append(f"✅ Harvest on {optimal_days[0]}")
        
        if road_risk['risk_level'] == 'HIGH':
            recommendations.append(f"🚨 URGENT: Roads may close in {road_risk['days_until_closure']} days")
            recommendations.append("Arrange transport immediately")
        elif road_risk['risk_level'] == 'MEDIUM':
            recommendations.append("⚠️ Plan transport within 3-4 days")
        
        return recommendations
    
    def _calculate_urgency(self, optimal_days, road_risk):
        """Calculate urgency level"""
        
        if road_risk['risk_level'] == 'HIGH':
            return 'CRITICAL'
        elif road_risk['risk_level'] == 'MEDIUM' and optimal_days:
            return 'HIGH'
        elif optimal_days:
            return 'NORMAL'
        else:
            return 'LOW'
    
    def estimate_post_harvest_loss(self, farm_id, delay_days=0):
        """Estimate losses from harvest delay"""
        
        # Base loss rate: 2% per day after optimal harvest
        base_loss_rate = 0.02
        
        # Weather multiplier
        farm = Farm.objects.get(id=farm_id)
        forecast = self._get_weather_forecast(farm, days=delay_days)
        
        # High humidity and rain increase loss rate
        avg_humidity = sum(d['humidity'] for d in forecast) / len(forecast) if forecast else 70
        total_rain = sum(d['rainfall'] for d in forecast) if forecast else 0
        
        weather_multiplier = 1.0
        if avg_humidity > 80:
            weather_multiplier += 0.5
        if total_rain > 50:
            weather_multiplier += 0.3
        
        total_loss_rate = base_loss_rate * delay_days * weather_multiplier
        
        return {
            'delay_days': delay_days,
            'estimated_loss_percentage': min(total_loss_rate * 100, 50),  # Cap at 50%
            'weather_factor': weather_multiplier,
            'recommendation': 'Harvest immediately' if total_loss_rate > 0.1 else 'Monitor conditions'
        }
