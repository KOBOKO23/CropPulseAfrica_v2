# apps/scoring/algorithms/score_engine.py

from django.utils import timezone
from datetime import timedelta

class PulseScoreEngine:
    """Calculate Pulse Score based on multiple factors"""
    
    # Score weights
    WEIGHTS = {
        'farm_size': 0.20,
        'crop_health': 0.25,
        'climate_risk': 0.20,
        'deforestation': 0.17,
        'payment_history': 0.18
    }
    
    def calculate_score(self, farmer, farm):
        """
        Calculate comprehensive Pulse Score
        
        Returns:
            dict: Score breakdown and recommendations
        """
        # Get latest satellite data
        latest_scan = farm.satellite_scans.order_by('-acquisition_date').first()
        
        # Get climate risk
        climate_risk = farm.risk_assessments.order_by('-assessment_date').first()
        
        # Get deforestation status
        deforestation = farm.deforestation_checks.order_by('-check_date').first()
        
        # Calculate component scores
        farm_size_score = self._score_farm_size(farm.size_acres)
        crop_health_score = self._score_crop_health(latest_scan.ndvi if latest_scan else None)
        climate_risk_score = self._score_climate_risk(climate_risk.overall_climate_risk if climate_risk else 50)
        deforestation_score = self._score_deforestation(deforestation.deforestation_detected if deforestation else False)
        payment_history_score = self._score_payment_history(farmer)
        
        # Calculate weighted total
        total_score = int(
            farm_size_score * self.WEIGHTS['farm_size'] +
            crop_health_score * self.WEIGHTS['crop_health'] +
            climate_risk_score * self.WEIGHTS['climate_risk'] +
            deforestation_score * self.WEIGHTS['deforestation'] +
            payment_history_score * self.WEIGHTS['payment_history']
        )
        
        # Calculate credit recommendations
        max_loan, interest_range, default_prob = self._calculate_credit_terms(total_score)
        
        return {
            'score': total_score,
            'confidence': self._calculate_confidence(latest_scan, climate_risk),
            'breakdown': {
                'farm_size': farm_size_score,
                'crop_health': crop_health_score,
                'climate_risk': climate_risk_score,
                'deforestation': deforestation_score,
                'payment_history': payment_history_score
            },
            'max_loan_amount': max_loan,
            'recommended_interest_rate': interest_range,
            'default_probability': default_prob
        }
    
    def _score_farm_size(self, acres):
        """Score based on farm size (max 100 points)"""
        if acres >= 5.0:
            return 100
        elif acres >= 2.0:
            return 80
        elif acres >= 1.0:
            return 60
        else:
            return 40
    
    def _score_crop_health(self, ndvi):
        """Score based on NDVI (max 100 points)"""
        if ndvi is None:
            return 50  # Default if no data
        
        if ndvi >= 0.75:
            return 100
        elif ndvi >= 0.60:
            return 85
        elif ndvi >= 0.40:
            return 70
        else:
            return 50
    
    def _score_climate_risk(self, risk):
        """Score based on climate risk (max 100 points)"""
        # Lower risk = higher score
        return int(100 - risk)
    
    def _score_deforestation(self, detected):
        """Score based on deforestation status (max 100 points)"""
        return 0 if detected else 100
    
    def _score_payment_history(self, farmer):
        """Score based on loan repayment history (max 100 points)"""
        from apps.loans.models import LoanRepayment
        
        total_payments = LoanRepayment.objects.filter(
            loan__farmer=farmer
        ).count()
        
        if total_payments == 0:
            return 50  # New farmer, neutral score
        
        on_time_payments = LoanRepayment.objects.filter(
            loan__farmer=farmer,
            is_paid=True,
            is_late=False
        ).count()
        
        return int((on_time_payments / total_payments) * 100)
    
    def _calculate_credit_terms(self, score):
        """Calculate loan terms based on score"""
        if score >= 80:
            return 65000, (11.0, 13.0), 6.0
        elif score >= 70:
            return 50000, (12.0, 14.0), 8.0
        elif score >= 60:
            return 35000, (13.0, 15.0), 12.0
        else:
            return 20000, (14.0, 16.0), 18.0
    
    def _calculate_confidence(self, satellite_scan, climate_risk):
        """Calculate confidence in the score"""
        confidence = 0.5  # Base confidence
        
        if satellite_scan:
            days_old = (timezone.now() - satellite_scan.processing_date).days
            if days_old <= 7:
                confidence += 0.3
            elif days_old <= 14:
                confidence += 0.2
        
        if climate_risk:
            days_old = (timezone.now().date() - climate_risk.assessment_date).days
            if days_old <= 30:
                confidence += 0.2
        
        return min(confidence, 0.95)