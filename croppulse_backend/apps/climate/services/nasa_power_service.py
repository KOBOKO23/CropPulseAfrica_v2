# apps/climate/services/nasa_power_service.py

import requests
from datetime import datetime, timedelta

class NASAPowerService:
    """Integration with NASA POWER API"""
    
    BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
    
    def get_climate_data(self, latitude, longitude, start_date, end_date):
        """
        Fetch climate data from NASA POWER
        
        Args:
            latitude: float
            longitude: float
            start_date: datetime
            end_date: datetime
        
        Returns:
            dict: Climate data including temp, rainfall, etc.
        """
        params = {
            'parameters': 'T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,WS2M',
            'community': 'AG',
            'longitude': longitude,
            'latitude': latitude,
            'start': start_date.strftime('%Y%m%d'),
            'end': end_date.strftime('%Y%m%d'),
            'format': 'JSON'
        }
        
        response = requests.get(self.BASE_URL, params=params)
        data = response.json()
        
        return self._parse_nasa_response(data)
    
    def _parse_nasa_response(self, data):
        """Parse NASA POWER response"""
        parameters = data['properties']['parameter']
        
        climate_data = []
        dates = list(parameters['T2M'].keys())
        
        for date_str in dates:
            climate_data.append({
                'date': datetime.strptime(date_str, '%Y%m%d').date(),
                'temperature_avg': parameters['T2M'][date_str],
                'temperature_max': parameters['T2M_MAX'][date_str],
                'temperature_min': parameters['T2M_MIN'][date_str],
                'rainfall': parameters['PRECTOTCORR'][date_str],
                'humidity': parameters['RH2M'][date_str],
                'wind_speed': parameters['WS2M'][date_str]
            })
        
        return climate_data