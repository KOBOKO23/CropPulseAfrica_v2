# apps/climate/services/alert_generator.py
from datetime import datetime, timedelta
from django.core.cache import cache
from apps.climate.models import ClimateData, ClimateRiskAssessment


class AlertGenerator:
    """
    Generate and manage climate alerts for farmers
    """
    
    # Alert thresholds
    CRITICAL_DROUGHT_RISK = 70
    CRITICAL_FLOOD_RISK = 70
    CRITICAL_HEAT_RISK = 70
    WARNING_THRESHOLD = 40
    
    def __init__(self, farm):
        self.farm = farm
    
    def check_and_generate_alerts(self):
        """
        Check current conditions and generate appropriate alerts
        
        Returns:
            list: Active alerts
        """
        alerts = []
        
        # Get latest risk assessment
        latest_assessment = ClimateRiskAssessment.objects.filter(
            farm=self.farm
        ).order_by('-assessment_date').first()
        
        if not latest_assessment:
            return alerts
        
        # Check drought risk
        if latest_assessment.drought_risk >= self.CRITICAL_DROUGHT_RISK:
            alerts.append(self._create_drought_alert(latest_assessment, 'CRITICAL'))
        elif latest_assessment.drought_risk >= self.WARNING_THRESHOLD:
            alerts.append(self._create_drought_alert(latest_assessment, 'WARNING'))
        
        # Check flood risk
        if latest_assessment.flood_risk >= self.CRITICAL_FLOOD_RISK:
            alerts.append(self._create_flood_alert(latest_assessment, 'CRITICAL'))
        elif latest_assessment.flood_risk >= self.WARNING_THRESHOLD:
            alerts.append(self._create_flood_alert(latest_assessment, 'WARNING'))
        
        # Check heat stress risk
        if latest_assessment.heat_stress_risk >= self.CRITICAL_HEAT_RISK:
            alerts.append(self._create_heat_alert(latest_assessment, 'CRITICAL'))
        elif latest_assessment.heat_stress_risk >= self.WARNING_THRESHOLD:
            alerts.append(self._create_heat_alert(latest_assessment, 'WARNING'))
        
        # Check for sudden weather changes
        weather_change_alerts = self._check_sudden_weather_changes()
        alerts.extend(weather_change_alerts)
        
        # Cache alerts to avoid duplicate notifications
        self._cache_alerts(alerts)
        
        return alerts
    
    def _create_drought_alert(self, assessment, severity):
        """Create drought alert"""
        return {
            'id': f'drought_{self.farm.id}_{datetime.now().date()}',
            'farm_id': self.farm.id,
            'type': 'DROUGHT',
            'severity': severity,
            'risk_score': assessment.drought_risk,
            'title': f'{severity} Drought Risk Alert',
            'message': self._get_drought_message(assessment, severity),
            'recommendations': self._get_drought_recommendations(assessment, severity),
            'created_at': datetime.now(),
            'data': {
                'rainfall_deficit': assessment.rainfall_deviation_percentage,
                'current_rainfall': assessment.current_season_rainfall,
                'historical_avg': assessment.historical_rainfall_avg
            }
        }
    
    def _create_flood_alert(self, assessment, severity):
        """Create flood alert"""
        return {
            'id': f'flood_{self.farm.id}_{datetime.now().date()}',
            'farm_id': self.farm.id,
            'type': 'FLOOD',
            'severity': severity,
            'risk_score': assessment.flood_risk,
            'title': f'{severity} Flood Risk Alert',
            'message': self._get_flood_message(assessment, severity),
            'recommendations': self._get_flood_recommendations(assessment, severity),
            'created_at': datetime.now(),
            'data': {
                'flood_risk_score': assessment.flood_risk
            }
        }
    
    def _create_heat_alert(self, assessment, severity):
        """Create heat stress alert"""
        return {
            'id': f'heat_{self.farm.id}_{datetime.now().date()}',
            'farm_id': self.farm.id,
            'type': 'HEAT_STRESS',
            'severity': severity,
            'risk_score': assessment.heat_stress_risk,
            'title': f'{severity} Heat Stress Alert',
            'message': self._get_heat_message(assessment, severity),
            'recommendations': self._get_heat_recommendations(assessment, severity),
            'created_at': datetime.now(),
            'data': {
                'heat_risk_score': assessment.heat_stress_risk
            }
        }
    
    def _get_drought_message(self, assessment, severity):
        """Generate drought alert message"""
        deficit = abs(assessment.rainfall_deviation_percentage)
        
        if severity == 'CRITICAL':
            return (f"CRITICAL DROUGHT ALERT: Your farm is experiencing severe rainfall deficit "
                   f"({deficit:.1f}% below normal). Immediate action required to protect crops.")
        else:
            return (f"DROUGHT WARNING: Rainfall is {deficit:.1f}% below normal levels. "
                   f"Monitor your crops closely and prepare water conservation measures.")
    
    def _get_flood_message(self, assessment, severity):
        """Generate flood alert message"""
        if severity == 'CRITICAL':
            return ("CRITICAL FLOOD ALERT: Very high risk of flooding detected. "
                   "Excessive rainfall may cause waterlogging and crop damage. Take immediate protective measures.")
        else:
            return ("FLOOD WARNING: Elevated flood risk. Heavy rainfall expected. "
                   "Ensure drainage systems are clear and monitor low-lying areas.")
    
    def _get_heat_message(self, assessment, severity):
        """Generate heat stress alert message"""
        if severity == 'CRITICAL':
            return ("CRITICAL HEAT ALERT: Extreme temperatures detected. "
                   "Your crops are at high risk of heat stress and damage. Take immediate action.")
        else:
            return ("HEAT WARNING: Elevated temperatures may cause crop stress. "
                   "Monitor your crops for signs of heat damage and increase watering if possible.")
    
    def _get_drought_recommendations(self, assessment, severity):
        """Get drought-specific recommendations"""
        if severity == 'CRITICAL':
            return [
                "Apply mulch immediately to conserve soil moisture",
                "Reduce non-essential irrigation to preserve water",
                "Consider early harvest if crops are mature",
                "Implement emergency irrigation if available",
                "Monitor crop stress daily",
                "Contact your agricultural extension officer for support"
            ]
        else:
            return [
                "Begin water conservation practices",
                "Monitor soil moisture levels",
                "Prepare mulching materials",
                "Plan irrigation schedule carefully",
                "Consider drought-resistant varieties for next season"
            ]
    
    def _get_flood_recommendations(self, assessment, severity):
        """Get flood-specific recommendations"""
        if severity == 'CRITICAL':
            return [
                "Clear all drainage channels immediately",
                "Harvest mature crops before heavy rains",
                "Move equipment to higher ground",
                "Create temporary drainage if possible",
                "Avoid working in waterlogged fields",
                "Prepare for potential crop loss"
            ]
        else:
            return [
                "Check and clear drainage systems",
                "Monitor weather forecasts closely",
                "Prepare drainage tools and materials",
                "Avoid planting in low-lying areas",
                "Plan harvest timing around forecast"
            ]
    
    def _get_heat_recommendations(self, assessment, severity):
        """Get heat stress-specific recommendations"""
        if severity == 'CRITICAL':
            return [
                "Increase irrigation frequency immediately if water available",
                "Apply shade netting for high-value crops",
                "Irrigate during early morning or evening",
                "Monitor crops multiple times daily",
                "Apply organic matter to help retain soil moisture",
                "Avoid fertilizer application during heat stress"
            ]
        else:
            return [
                "Ensure adequate soil moisture",
                "Plan irrigation for cooler parts of day",
                "Monitor crops for wilting or stress signs",
                "Prepare shade materials for sensitive crops",
                "Avoid heavy farm work during peak heat"
            ]
    
    def _check_sudden_weather_changes(self):
        """
        Detect sudden significant weather changes
        
        Returns:
            list: Alerts for sudden changes
        """
        alerts = []
        
        # Get last 7 days of data
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        recent_data = ClimateData.objects.filter(
            farm=self.farm,
            date__gte=start_date,
            date__lte=end_date,
            is_forecast=False
        ).order_by('date')
        
        if recent_data.count() < 3:
            return alerts
        
        data_list = list(recent_data)
        
        # Check for sudden temperature drop
        for i in range(len(data_list) - 1):
            temp_drop = data_list[i].temperature_avg - data_list[i + 1].temperature_avg
            if temp_drop > 10:  # 10°C drop in one day
                alerts.append({
                    'id': f'temp_drop_{self.farm.id}_{data_list[i + 1].date}',
                    'farm_id': self.farm.id,
                    'type': 'SUDDEN_TEMP_DROP',
                    'severity': 'WARNING',
                    'title': 'Sudden Temperature Drop',
                    'message': f'Temperature dropped by {temp_drop:.1f}°C. This may stress crops.',
                    'recommendations': [
                        'Monitor crops for cold stress',
                        'Protect sensitive crops if possible',
                        'Delay planting if planned'
                    ],
                    'created_at': datetime.now()
                })
        
        # Check for sudden heavy rainfall
        for record in data_list:
            if record.rainfall > 50:  # Heavy single-day rainfall
                alerts.append({
                    'id': f'heavy_rain_{self.farm.id}_{record.date}',
                    'farm_id': self.farm.id,
                    'type': 'HEAVY_RAINFALL',
                    'severity': 'WARNING',
                    'title': 'Heavy Rainfall Event',
                    'message': f'Heavy rainfall recorded ({record.rainfall:.1f}mm). Monitor for waterlogging.',
                    'recommendations': [
                        'Check drainage systems',
                        'Monitor for standing water',
                        'Avoid field work until soil drains',
                        'Watch for signs of crop stress'
                    ],
                    'created_at': datetime.now()
                })
        
        return alerts
    
    def _cache_alerts(self, alerts):
        """
        Cache alerts to prevent duplicate notifications
        
        Args:
            alerts: list of alert dicts
        """
        for alert in alerts:
            cache_key = f"alert_{alert['id']}"
            # Cache for 24 hours
            cache.set(cache_key, alert, 86400)
    
    def get_active_alerts(self):
        """
        Get all active alerts from cache
        
        Returns:
            list: Active alerts
        """
        # This would typically query a database table
        # For now, we'll generate fresh alerts
        return self.check_and_generate_alerts()
    
    def should_notify_farmer(self, alert):
        """
        Determine if farmer should be notified about this alert
        
        Args:
            alert: dict, alert data
        
        Returns:
            bool: Whether to send notification
        """
        cache_key = f"notified_{alert['id']}"
        
        # Check if already notified about this alert
        if cache.get(cache_key):
            return False
        
        # Only notify for WARNING and CRITICAL alerts
        if alert['severity'] in ['WARNING', 'CRITICAL']:
            # Mark as notified
            cache.set(cache_key, True, 86400)  # 24 hours
            return True
        
        return False
    
    def format_alert_for_sms(self, alert):
        """
        Format alert for SMS delivery (160 characters max)
        
        Args:
            alert: dict, alert data
        
        Returns:
            str: SMS message
        """
        severity_prefix = "⚠️" if alert['severity'] == 'CRITICAL' else "ℹ️"
        
        # Keep it short and actionable
        sms = f"{severity_prefix} {alert['type']}: {alert['message'][:120]}..."
        
        return sms[:160]  # SMS character limit
    
    def get_alert_summary(self, days=7):
        """
        Get summary of alerts over specified period
        
        Args:
            days: int, period to summarize
        
        Returns:
            dict: Alert summary statistics
        """
        alerts = self.check_and_generate_alerts()
        
        summary = {
            'total_alerts': len(alerts),
            'critical_alerts': len([a for a in alerts if a['severity'] == 'CRITICAL']),
            'warning_alerts': len([a for a in alerts if a['severity'] == 'WARNING']),
            'by_type': {},
            'active_risks': []
        }
        
        for alert in alerts:
            alert_type = alert['type']
            if alert_type not in summary['by_type']:
                summary['by_type'][alert_type] = 0
            summary['by_type'][alert_type] += 1
            
            if alert['severity'] == 'CRITICAL':
                summary['active_risks'].append(alert_type)
        
        return summary