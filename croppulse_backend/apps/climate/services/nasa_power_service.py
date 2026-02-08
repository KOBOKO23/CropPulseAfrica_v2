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
            start_date: datetime or string (YYYYMMDD)
            end_date: datetime or string (YYYYMMDD)
        
        Returns:
            dict: Climate data including temp, rainfall, etc.
        """
        # Handle both datetime and string inputs
        if isinstance(start_date, datetime):
            start_date = start_date.strftime('%Y%m%d')
        if isinstance(end_date, datetime):
            end_date = end_date.strftime('%Y%m%d')
            
        params = {
            'parameters': 'T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,WS2M',
            'community': 'AG',
            'longitude': longitude,
            'latitude': latitude,
            'start': start_date,
            'end': end_date,
            'format': 'JSON'
        }
        
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            return self._parse_nasa_response(data)
        except Exception as e:
            print(f"NASA POWER API Error: {str(e)}")
            return {'error': str(e)}
    
    def _parse_nasa_response(self, data):
        """Parse NASA POWER response"""
        parameters = data['properties']['parameter']
        
        climate_data = []
        dates = list(parameters['T2M'].keys())
        
        for date_str in dates:
            # NASA uses -999 for missing data, skip or use None
            temp_avg = parameters['T2M'][date_str]
            temp_max = parameters['T2M_MAX'][date_str]
            temp_min = parameters['T2M_MIN'][date_str]
            precip = parameters['PRECTOTCORR'][date_str]
            humidity = parameters['RH2M'][date_str]
            wind = parameters['WS2M'][date_str]
            
            climate_data.append({
                'date': datetime.strptime(date_str, '%Y%m%d').date(),
                'temperature_avg': None if temp_avg == -999 else temp_avg,
                'temperature_max': None if temp_max == -999 else temp_max,
                'temperature_min': None if temp_min == -999 else temp_min,
                'precipitation': None if precip == -999 else precip,
                'humidity': None if humidity == -999 else humidity,
                'wind_speed': None if wind == -999 else wind
            })
        
        return climate_data