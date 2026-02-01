# apps/satellite/services/ndvi_calculator.py

import logging
from datetime import datetime, timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class NDVICalculator:
    """Service for NDVI calculation and interpretation"""
    
    # NDVI thresholds for different crop stages
    NDVI_THRESHOLDS = {
        'excellent': 0.75,
        'good': 0.60,
        'moderate': 0.40,
        'poor': 0.20
    }
    
    # Crop-specific NDVI ranges
    CROP_NDVI_RANGES = {
        'maize': {'healthy_min': 0.65, 'healthy_max': 0.85},
        'coffee': {'healthy_min': 0.70, 'healthy_max': 0.90},
        'tea': {'healthy_min': 0.75, 'healthy_max': 0.95},
        'beans': {'healthy_min': 0.60, 'healthy_max': 0.80},
        'vegetables': {'healthy_min': 0.55, 'healthy_max': 0.75}
    }
    
    def __init__(self):
        """Initialize NDVI calculator"""
        pass
    
    def interpret_ndvi(self, ndvi_value):
        """
        Interpret NDVI value and return health status
        
        Args:
            ndvi_value: NDVI value (-1 to 1)
        
        Returns:
            dict: Interpretation with status, category, and description
        """
        if ndvi_value is None:
            return {
                'status': 'Unknown',
                'category': 'no_data',
                'description': 'No NDVI data available',
                'recommendation': 'Schedule satellite scan'
            }
        
        # Determine category
        if ndvi_value >= self.NDVI_THRESHOLDS['excellent']:
            category = 'excellent'
            status = 'Healthy'
            description = 'Excellent vegetation health - dense, healthy crops'
            recommendation = 'Continue current farming practices'
        
        elif ndvi_value >= self.NDVI_THRESHOLDS['good']:
            category = 'good'
            status = 'Healthy'
            description = 'Good vegetation health - crops are growing well'
            recommendation = 'Monitor regularly and maintain current practices'
        
        elif ndvi_value >= self.NDVI_THRESHOLDS['moderate']:
            category = 'moderate'
            status = 'Stressed'
            description = 'Moderate vegetation - some stress visible'
            recommendation = 'Check for water stress, nutrient deficiency, or pests'
        
        elif ndvi_value >= self.NDVI_THRESHOLDS['poor']:
            category = 'poor'
            status = 'Stressed'
            description = 'Poor vegetation health - significant stress'
            recommendation = 'Immediate action needed - investigate and treat issues'
        
        else:
            category = 'critical'
            status = 'Poor'
            description = 'Critical - very little vegetation detected'
            recommendation = 'Urgent intervention required - consult agricultural expert'
        
        return {
            'status': status,
            'category': category,
            'description': description,
            'recommendation': recommendation,
            'ndvi_value': round(ndvi_value, 3)
        }
    
    def compare_with_crop_baseline(self, ndvi_value, crop_type):
        """
        Compare NDVI with crop-specific healthy ranges
        
        Args:
            ndvi_value: Current NDVI value
            crop_type: Type of crop (maize, coffee, etc.)
        
        Returns:
            dict: Comparison with crop baseline
        """
        crop_type_lower = crop_type.lower() if crop_type else 'maize'
        
        # Get crop range or use maize as default
        crop_range = self.CROP_NDVI_RANGES.get(
            crop_type_lower,
            self.CROP_NDVI_RANGES['maize']
        )
        
        healthy_min = crop_range['healthy_min']
        healthy_max = crop_range['healthy_max']
        
        if ndvi_value >= healthy_min and ndvi_value <= healthy_max:
            status = 'Within healthy range'
            performance = 'optimal'
        elif ndvi_value > healthy_max:
            status = 'Above typical range'
            performance = 'excellent'
        elif ndvi_value >= healthy_min - 0.10:
            status = 'Slightly below healthy range'
            performance = 'acceptable'
        else:
            status = 'Below healthy range'
            performance = 'concerning'
        
        deviation = ndvi_value - healthy_min
        deviation_percentage = (deviation / healthy_min) * 100
        
        return {
            'crop_type': crop_type,
            'ndvi_value': round(ndvi_value, 3),
            'healthy_range': {
                'min': healthy_min,
                'max': healthy_max
            },
            'status': status,
            'performance': performance,
            'deviation': round(deviation, 3),
            'deviation_percentage': round(deviation_percentage, 1)
        }
    
    def calculate_trend(self, ndvi_history):
        """
        Calculate NDVI trend from historical data
        
        Args:
            ndvi_history: QuerySet or list of NDVIHistory objects
        
        Returns:
            dict: Trend analysis
        """
        if not ndvi_history or len(ndvi_history) < 2:
            return {
                'trend': 'insufficient_data',
                'direction': 'unknown',
                'change_rate': 0,
                'interpretation': 'Not enough data for trend analysis'
            }
        
        # Convert to list if QuerySet
        history_list = list(ndvi_history)
        
        # Sort by date
        history_list.sort(key=lambda x: x.date)
        
        # Get first and last values
        first_value = history_list[0].ndvi_value
        last_value = history_list[-1].ndvi_value
        
        # Calculate change
        change = last_value - first_value
        change_percentage = (change / first_value) * 100 if first_value != 0 else 0
        
        # Calculate average rate of change per day
        days_diff = (history_list[-1].date - history_list[0].date).days
        if days_diff > 0:
            change_rate = change / days_diff
        else:
            change_rate = 0
        
        # Determine trend
        if change_percentage > 10:
            trend = 'strongly_improving'
            direction = 'up'
            interpretation = 'NDVI is significantly improving - crops are thriving'
        elif change_percentage > 5:
            trend = 'improving'
            direction = 'up'
            interpretation = 'NDVI is improving - positive crop development'
        elif change_percentage > -5:
            trend = 'stable'
            direction = 'stable'
            interpretation = 'NDVI is stable - consistent crop health'
        elif change_percentage > -10:
            trend = 'declining'
            direction = 'down'
            interpretation = 'NDVI is declining - investigate potential issues'
        else:
            trend = 'strongly_declining'
            direction = 'down'
            interpretation = 'NDVI is significantly declining - urgent attention needed'
        
        return {
            'trend': trend,
            'direction': direction,
            'change': round(change, 3),
            'change_percentage': round(change_percentage, 2),
            'change_rate': round(change_rate, 4),
            'interpretation': interpretation,
            'data_points': len(history_list),
            'period_days': days_diff
        }
    
    def predict_crop_stage(self, ndvi_value, crop_type, planting_date=None):
        """
        Predict crop growth stage based on NDVI
        
        Args:
            ndvi_value: Current NDVI value
            crop_type: Type of crop
            planting_date: Optional planting date for more accurate prediction
        
        Returns:
            dict: Predicted crop stage
        """
        if planting_date:
            days_since_planting = (timezone.now().date() - planting_date).days
        else:
            days_since_planting = None
        
        # NDVI-based stage estimation (simplified)
        if ndvi_value < 0.20:
            stage = 'bare_soil_or_emergence'
            description = 'Bare soil or early emergence'
        elif ndvi_value < 0.40:
            stage = 'early_vegetative'
            description = 'Early vegetative growth'
        elif ndvi_value < 0.60:
            stage = 'active_vegetative'
            description = 'Active vegetative growth'
        elif ndvi_value < 0.75:
            stage = 'peak_vegetative_or_flowering'
            description = 'Peak vegetative growth or flowering'
        else:
            stage = 'reproductive_or_mature'
            description = 'Reproductive stage or mature crop'
        
        # Refine with days since planting if available
        if days_since_planting and crop_type.lower() == 'maize':
            if days_since_planting < 20:
                stage = 'emergence'
                description = 'Seedling emergence (0-20 days)'
            elif days_since_planting < 40:
                stage = 'vegetative'
                description = 'Vegetative growth (20-40 days)'
            elif days_since_planting < 60:
                stage = 'tasseling'
                description = 'Tasseling stage (40-60 days)'
            elif days_since_planting < 80:
                stage = 'silking_and_pollination'
                description = 'Silking and pollination (60-80 days)'
            elif days_since_planting < 120:
                stage = 'grain_filling'
                description = 'Grain filling (80-120 days)'
            else:
                stage = 'maturity'
                description = 'Physiological maturity (120+ days)'
        
        return {
            'stage': stage,
            'description': description,
            'days_since_planting': days_since_planting,
            'ndvi_value': round(ndvi_value, 3),
            'confidence': 'medium' if days_since_planting else 'low'
        }
    
    def generate_health_score(self, ndvi_value, soil_moisture=None, rainfall_data=None):
        """
        Generate comprehensive health score (0-100)
        
        Args:
            ndvi_value: NDVI value
            soil_moisture: Soil moisture percentage (optional)
            rainfall_data: Recent rainfall data (optional)
        
        Returns:
            int: Health score from 0-100
        """
        score = 0
        
        # NDVI contribution (60 points)
        if ndvi_value >= 0.75:
            score += 60
        elif ndvi_value >= 0.60:
            score += 50
        elif ndvi_value >= 0.40:
            score += 35
        elif ndvi_value >= 0.20:
            score += 20
        else:
            score += 10
        
        # Soil moisture contribution (25 points)
        if soil_moisture is not None:
            if soil_moisture >= 60:
                score += 25
            elif soil_moisture >= 40:
                score += 18
            elif soil_moisture >= 20:
                score += 10
            else:
                score += 5
        else:
            score += 15  # Default moderate score if no data
        
        # Rainfall contribution (15 points)
        if rainfall_data is not None:
            # Assume rainfall_data is recent 30-day total in mm
            if rainfall_data >= 100:
                score += 15
            elif rainfall_data >= 50:
                score += 10
            elif rainfall_data >= 20:
                score += 5
            else:
                score += 2
        else:
            score += 10  # Default moderate score if no data
        
        return min(score, 100)  # Cap at 100
    
    def get_seasonal_baseline(self, month, crop_type='maize'):
        """
        Get expected NDVI baseline for a given month and crop
        
        Args:
            month: Month number (1-12)
            crop_type: Type of crop
        
        Returns:
            dict: Seasonal baseline expectations
        """
        # Kenya has two main growing seasons:
        # Long rains: March-May
        # Short rains: October-December
        
        if crop_type.lower() == 'maize':
            if month in [4, 5, 11, 12]:  # Peak growing months
                expected_min = 0.65
                expected_max = 0.85
                season = 'peak_growth'
            elif month in [3, 10]:  # Early season
                expected_min = 0.40
                expected_max = 0.65
                season = 'early_season'
            elif month in [6, 7, 1, 2]:  # Post-harvest/dry
                expected_min = 0.20
                expected_max = 0.40
                season = 'post_harvest'
            else:  # Mid-season
                expected_min = 0.50
                expected_max = 0.70
                season = 'mid_season'
        
        else:  # Default for perennial crops
            expected_min = 0.60
            expected_max = 0.80
            season = 'year_round'
        
        return {
            'month': month,
            'crop_type': crop_type,
            'expected_range': {
                'min': expected_min,
                'max': expected_max
            },
            'season': season
        }