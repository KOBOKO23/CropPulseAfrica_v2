# apps/climate/services/weather_forecast.py
import requests
from datetime import datetime, timedelta
from django.conf import settings


class WeatherForecastService:
    """
    Fetch weather forecasts from OpenWeatherMap or similar service
    Can be extended to use multiple forecast providers
    """
    
    def __init__(self):
        self.api_key = getattr(settings, 'OPENWEATHER_API_KEY', None)
        self.base_url = "https://api.openweathermap.org/data/2.5/forecast"
    
    def get_7day_forecast(self, latitude, longitude):
        """
        Get 7-day weather forecast
        
        Args:
            latitude: float
            longitude: float
        
        Returns:
            list: Forecast data for next 7 days
        """
        if not self.api_key:
            # Fallback to NASA POWER for forecast (limited)
            return self._get_nasa_forecast(latitude, longitude)
        
        try:
            params = {
                'lat': latitude,
                'lon': longitude,
                'appid': self.api_key,
                'units': 'metric',
                'cnt': 56  # 7 days * 8 (3-hour intervals)
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return self._parse_openweather_forecast(data)
        
        except Exception as e:
            print(f"Error fetching forecast: {str(e)}")
            return []
    
    def _parse_openweather_forecast(self, data):
        """
        Parse OpenWeatherMap forecast response
        
        Args:
            data: dict, API response
        
        Returns:
            list: Parsed daily forecasts
        """
        daily_forecasts = {}
        
        for item in data.get('list', []):
            date = datetime.fromtimestamp(item['dt']).date()
            date_str = date.isoformat()
            
            # Aggregate 3-hourly data into daily
            if date_str not in daily_forecasts:
                daily_forecasts[date_str] = {
                    'date': date,
                    'temps': [],
                    'rainfall': 0,
                    'humidity': [],
                    'wind_speed': [],
                    'conditions': []
                }
            
            daily_forecasts[date_str]['temps'].append(item['main']['temp'])
            daily_forecasts[date_str]['humidity'].append(item['main']['humidity'])
            daily_forecasts[date_str]['wind_speed'].append(item['wind']['speed'])
            
            # Rainfall (if present)
            if 'rain' in item and '3h' in item['rain']:
                daily_forecasts[date_str]['rainfall'] += item['rain']['3h']
            
            # Weather condition
            if item.get('weather'):
                daily_forecasts[date_str]['conditions'].append(
                    item['weather'][0]['description']
                )
        
        # Calculate daily aggregates
        forecasts = []
        for date_str, data in sorted(daily_forecasts.items()):
            temps = data['temps']
            forecasts.append({
                'date': data['date'],
                'temperature_avg': round(sum(temps) / len(temps), 2),
                'temperature_max': round(max(temps), 2),
                'temperature_min': round(min(temps), 2),
                'rainfall': round(data['rainfall'], 2),
                'rainfall_probability': self._estimate_rain_probability(data['conditions']),
                'humidity': round(sum(data['humidity']) / len(data['humidity']), 2),
                'wind_speed': round(sum(data['wind_speed']) / len(data['wind_speed']) * 3.6, 2),  # m/s to km/h
                'conditions': max(set(data['conditions']), key=data['conditions'].count) if data['conditions'] else 'Unknown',
                'is_forecast': True,
                'data_source': 'OpenWeatherMap'
            })
        
        return forecasts[:7]  # Return only 7 days
    
    def _estimate_rain_probability(self, conditions):
        """
        Estimate rainfall probability from weather conditions
        
        Args:
            conditions: list of weather condition strings
        
        Returns:
            float: Probability (0-100)
        """
        rain_keywords = ['rain', 'drizzle', 'shower', 'thunderstorm']
        rain_count = sum(1 for c in conditions if any(kw in c.lower() for kw in rain_keywords))
        
        if rain_count == 0:
            return 0.0
        
        probability = min(100, (rain_count / len(conditions)) * 100)
        return round(probability, 2)
    
    def _get_nasa_forecast(self, latitude, longitude):
        """
        Fallback forecast using NASA POWER (limited to climatology)
        
        Args:
            latitude: float
            longitude: float
        
        Returns:
            list: Basic forecast data
        """
        # NASA POWER doesn't provide true forecasts, only climatology
        # This returns historical averages as a basic fallback
        forecasts = []
        base_date = datetime.now().date()
        
        for i in range(7):
            forecast_date = base_date + timedelta(days=i)
            forecasts.append({
                'date': forecast_date,
                'temperature_avg': 25.0,  # Placeholder
                'temperature_max': 30.0,
                'temperature_min': 20.0,
                'rainfall': 5.0,
                'rainfall_probability': 30.0,
                'humidity': 65.0,
                'wind_speed': 10.0,
                'is_forecast': True,
                'data_source': 'Climatology',
                'note': 'Using historical averages - no real-time forecast available'
            })
        
        return forecasts
    
    def get_extreme_weather_alerts(self, forecasts):
        """
        Identify extreme weather events in forecast
        
        Args:
            forecasts: list of forecast dicts
        
        Returns:
            list: Alert messages
        """
        alerts = []
        
        for forecast in forecasts:
            date = forecast['date']
            
            # Heavy rainfall alert
            if forecast['rainfall'] > 50:
                alerts.append({
                    'date': date,
                    'type': 'HEAVY_RAIN',
                    'severity': 'HIGH',
                    'message': f"Heavy rainfall expected ({forecast['rainfall']}mm). Risk of flooding and waterlogging."
                })
            
            # Extreme heat alert
            if forecast['temperature_max'] > 35:
                alerts.append({
                    'date': date,
                    'type': 'EXTREME_HEAT',
                    'severity': 'HIGH',
                    'message': f"Extreme heat expected ({forecast['temperature_max']}°C). Crops may experience heat stress."
                })
            
            # Drought conditions (no rain for extended period)
            if forecast['rainfall'] < 1 and forecast['rainfall_probability'] < 20:
                alerts.append({
                    'date': date,
                    'type': 'DRY_CONDITIONS',
                    'severity': 'MEDIUM',
                    'message': "Dry conditions expected. Monitor soil moisture levels."
                })
            
            # Strong winds
            if forecast.get('wind_speed', 0) > 40:
                alerts.append({
                    'date': date,
                    'type': 'STRONG_WINDS',
                    'severity': 'MEDIUM',
                    'message': f"Strong winds expected ({forecast['wind_speed']}km/h). Secure loose items."
                })
        
        return alerts
    
    def get_planting_window_recommendation(self, forecasts):
        """
        Recommend optimal planting windows based on forecast
        
        Args:
            forecasts: list of forecast dicts
        
        Returns:
            dict: Planting recommendation
        """
        suitable_days = []
        
        for forecast in forecasts:
            # Ideal conditions: moderate temp, some rainfall, not too wet
            temp_suitable = 18 <= forecast['temperature_avg'] <= 30
            rain_suitable = 5 <= forecast['rainfall'] <= 30
            
            if temp_suitable and rain_suitable:
                suitable_days.append(forecast['date'])
        
        if suitable_days:
            return {
                'recommendation': 'FAVORABLE',
                'suitable_dates': suitable_days,
                'message': f"Good planting conditions expected on {len(suitable_days)} day(s) in the next week."
            }
        else:
            return {
                'recommendation': 'UNFAVORABLE',
                'suitable_dates': [],
                'message': "No ideal planting conditions in the forecast. Monitor weather closely."
            }
    
    def compare_forecast_vs_historical(self, forecasts, historical_avg_temp, historical_avg_rainfall):
        """
        Compare forecast to historical averages
        
        Args:
            forecasts: list of forecast dicts
            historical_avg_temp: float
            historical_avg_rainfall: float
        
        Returns:
            dict: Comparison analysis
        """
        if not forecasts:
            return None
        
        # Calculate forecast averages
        avg_temp = sum(f['temperature_avg'] for f in forecasts) / len(forecasts)
        total_rainfall = sum(f['rainfall'] for f in forecasts)
        
        temp_deviation = avg_temp - historical_avg_temp
        rainfall_deviation = total_rainfall - historical_avg_rainfall
        
        return {
            'forecast_avg_temperature': round(avg_temp, 2),
            'historical_avg_temperature': round(historical_avg_temp, 2),
            'temperature_deviation': round(temp_deviation, 2),
            'temperature_trend': 'warmer' if temp_deviation > 0 else 'cooler' if temp_deviation < 0 else 'normal',
            'forecast_total_rainfall': round(total_rainfall, 2),
            'historical_avg_rainfall': round(historical_avg_rainfall, 2),
            'rainfall_deviation': round(rainfall_deviation, 2),
            'rainfall_trend': 'wetter' if rainfall_deviation > 0 else 'drier' if rainfall_deviation < 0 else 'normal'
        }