# apps/satellite/services/cloud_classifier.py

import logging

logger = logging.getLogger(__name__)


class CloudClassifier:
    """Service for classifying cloud types and coverage"""
    
    # Cloud coverage thresholds
    CLEAR = 10
    PARTLY_CLOUDY = 30
    MOSTLY_CLOUDY = 70
    OVERCAST = 90
    
    def __init__(self):
        """Initialize cloud classifier"""
        pass
    
    def classify_cloud_coverage(self, cloud_percentage):
        """
        Classify cloud coverage level
        
        Args:
            cloud_percentage: Cloud cover percentage (0-100)
        
        Returns:
            dict: Classification results
        """
        if cloud_percentage < self.CLEAR:
            category = 'clear'
            description = 'Clear skies - excellent for optical imagery'
            recommendation = 'Proceed with optical satellite scan'
            quality = 'excellent'
        
        elif cloud_percentage < self.PARTLY_CLOUDY:
            category = 'partly_cloudy'
            description = 'Partly cloudy - good for optical imagery'
            recommendation = 'Optical scan feasible, monitor cloud movement'
            quality = 'good'
        
        elif cloud_percentage < self.MOSTLY_CLOUDY:
            category = 'mostly_cloudy'
            description = 'Mostly cloudy - limited optical visibility'
            recommendation = 'Consider using SAR instead of optical'
            quality = 'fair'
        
        elif cloud_percentage < self.OVERCAST:
            category = 'overcast'
            description = 'Overcast - poor optical visibility'
            recommendation = 'Use SAR for cloud penetration'
            quality = 'poor'
        
        else:
            category = 'completely_overcast'
            description = 'Completely overcast - no optical visibility'
            recommendation = 'SAR required for any analysis'
            quality = 'very_poor'
        
        return {
            'category': category,
            'description': description,
            'recommendation': recommendation,
            'quality': quality,
            'cloud_percentage': cloud_percentage,
            'use_sar': cloud_percentage >= self.PARTLY_CLOUDY
        }
    
    def recommend_satellite_type(self, cloud_percentage, urgency='normal'):
        """
        Recommend best satellite type based on cloud cover
        
        Args:
            cloud_percentage: Cloud cover percentage
            urgency: Urgency level (low, normal, high)
        
        Returns:
            dict: Satellite recommendation
        """
        classification = self.classify_cloud_coverage(cloud_percentage)
        
        # If clear to partly cloudy, optical is best
        if cloud_percentage < self.PARTLY_CLOUDY:
            primary = 'sentinel2'
            backup = 'sentinel1'
            reason = 'Clear conditions favor optical imagery for vegetation indices'
        
        # If mostly cloudy but not urgent, can wait
        elif cloud_percentage < self.MOSTLY_CLOUDY and urgency == 'low':
            primary = 'sentinel2'
            backup = 'sentinel1'
            reason = 'Wait for clearer conditions if not urgent'
        
        # Otherwise, use SAR
        else:
            primary = 'sentinel1'
            backup = 'sentinel2'
            reason = 'Cloud cover requires SAR for reliable data'
        
        return {
            'primary_satellite': primary,
            'backup_satellite': backup,
            'reason': reason,
            'wait_recommended': cloud_percentage >= self.MOSTLY_CLOUDY and urgency == 'low',
            'estimated_wait_days': self._estimate_wait_time(cloud_percentage)
        }
    
    def _estimate_wait_time(self, cloud_percentage):
        """Estimate days to wait for clearer conditions"""
        if cloud_percentage < self.PARTLY_CLOUDY:
            return 0
        elif cloud_percentage < self.MOSTLY_CLOUDY:
            return 2
        elif cloud_percentage < self.OVERCAST:
            return 5
        else:
            return 7
    
    def predict_optimal_scan_window(self, historical_cloud_data):
        """
        Predict optimal time window for satellite scan based on historical data
        
        Args:
            historical_cloud_data: List of dicts with {date, cloud_percentage}
        
        Returns:
            dict: Optimal scan prediction
        """
        if not historical_cloud_data:
            return {
                'optimal_months': [],
                'message': 'Insufficient historical data'
            }
        
        # Analyze cloud patterns by month
        monthly_averages = {}
        
        for entry in historical_cloud_data:
            month = entry['date'].month
            cloud_pct = entry['cloud_percentage']
            
            if month not in monthly_averages:
                monthly_averages[month] = []
            
            monthly_averages[month].append(cloud_pct)
        
        # Calculate average for each month
        month_scores = {}
        for month, values in monthly_averages.items():
            avg = sum(values) / len(values)
            month_scores[month] = avg
        
        # Find clearest months
        sorted_months = sorted(month_scores.items(), key=lambda x: x[1])
        optimal_months = [month for month, avg in sorted_months if avg < self.PARTLY_CLOUDY]
        
        month_names = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }
        
        optimal_month_names = [month_names[m] for m in optimal_months]
        
        return {
            'optimal_months': optimal_month_names,
            'clearest_month': optimal_month_names[0] if optimal_month_names else 'Unknown',
            'monthly_averages': {month_names[m]: round(avg, 1) for m, avg in month_scores.items()},
            'message': f"Best scanning window: {', '.join(optimal_month_names)}" if optimal_month_names else "No clear patterns found"
        }
    
    def assess_scan_quality(self, cloud_percentage, clear_pixel_percentage=None):
        """
        Assess overall scan quality
        
        Args:
            cloud_percentage: Cloud cover percentage
            clear_pixel_percentage: Percentage of clear pixels in AOI
        
        Returns:
            dict: Quality assessment
        """
        score = 100
        
        # Deduct points for cloud cover
        if cloud_percentage > 10:
            score -= (cloud_percentage - 10) * 0.8
        
        # Bonus for high clear pixel percentage
        if clear_pixel_percentage:
            if clear_pixel_percentage > 90:
                score += 10
            elif clear_pixel_percentage < 50:
                score -= 20
        
        score = max(0, min(100, score))
        
        if score >= 85:
            quality = 'excellent'
        elif score >= 70:
            quality = 'good'
        elif score >= 50:
            quality = 'acceptable'
        else:
            quality = 'poor'
        
        return {
            'quality_score': round(score, 1),
            'quality_level': quality,
            'cloud_percentage': cloud_percentage,
            'clear_pixel_percentage': clear_pixel_percentage,
            'usable': score >= 50
        }