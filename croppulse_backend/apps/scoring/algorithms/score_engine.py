"""
Pulse Score Engine

Core scoring algorithm that calculates credit scores for farmers.

Scoring Components (weighted):
- Farm size: 20%
- Crop health (NDVI): 25%
- Climate risk: 20%
- Deforestation: 17%
- Payment history: 18%

Score Range: 0-1000 (note: different from component scores which are 0-100)
"""

from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


class PulseScoreEngine:
    """Calculate Pulse Score based on multiple factors"""
    
    # Component weights (must sum to 1.0)
    WEIGHTS = {
        'farm_size': 0.20,
        'crop_health': 0.25,
        'climate_risk': 0.20,
        'deforestation': 0.17,
        'payment_history': 0.18
    }
    
    # Score validity period
    SCORE_VALIDITY_DAYS = 30
    
    def calculate_score(self, farmer, farm):
        """
        Calculate comprehensive Pulse Score.
        
        Args:
            farmer: Farmer model instance
            farm: Farm model instance
        
        Returns:
            dict: Score breakdown, confidence, and credit recommendations
        """
        from apps.satellite.models import NDVIHistory
        from apps.climate.models import ClimateRiskAssessment
        from apps.compliance.models import DeforestationCheck
        
        # Get latest satellite data
        latest_scan = NDVIHistory.objects.filter(
            farm=farm
        ).order_by('-acquisition_date').first()
        
        # Get climate risk
        climate_risk = ClimateRiskAssessment.objects.filter(
            location=farm.location
        ).order_by('-assessment_date').first()
        
        # Get deforestation status
        deforestation = DeforestationCheck.objects.filter(
            farm=farm
        ).order_by('-check_date').first()
        
        # Calculate component scores (each 0-100)
        farm_size_score = self._score_farm_size(farm.size_acres)
        crop_health_score = self._score_crop_health(
            latest_scan.ndvi_mean if latest_scan else None
        )
        climate_risk_score = self._score_climate_risk(
            climate_risk.overall_risk_score if climate_risk else 50.0
        )
        deforestation_score = self._score_deforestation(
            deforestation.deforestation_detected if deforestation else False
        )
        payment_history_score = self._score_payment_history(farmer)
        
        # Check for active fraud alerts
        fraud_penalty = self._check_fraud_alerts(farmer)
        
        # Calculate weighted total (scale to 0-1000)
        base_score = (
            farm_size_score * self.WEIGHTS['farm_size'] +
            crop_health_score * self.WEIGHTS['crop_health'] +
            climate_risk_score * self.WEIGHTS['climate_risk'] +
            deforestation_score * self.WEIGHTS['deforestation'] +
            payment_history_score * self.WEIGHTS['payment_history']
        ) * 10  # Scale from 0-100 to 0-1000
        
        # Apply fraud penalty
        total_score = int(max(0, base_score - fraud_penalty))
        
        # Calculate credit recommendations
        max_loan, interest_range, default_prob = self._calculate_credit_terms(total_score)
        
        # Calculate confidence level
        confidence = self._calculate_confidence(latest_scan, climate_risk, deforestation)
        
        # Determine score validity
        valid_until = timezone.now() + timedelta(days=self.SCORE_VALIDITY_DAYS)
        
        return {
            'score': total_score,
            'confidence': confidence,
            'breakdown': {
                'farm_size': farm_size_score,
                'crop_health': crop_health_score,
                'climate_risk': climate_risk_score,
                'deforestation': deforestation_score,
                'payment_history': payment_history_score
            },
            'fraud_penalty': fraud_penalty,
            'max_loan_amount': max_loan,
            'recommended_interest_rate': interest_range,
            'default_probability': default_prob,
            'valid_until': valid_until,
            'factors_used': {
                'satellite_data_date': latest_scan.acquisition_date if latest_scan else None,
                'climate_data_date': climate_risk.assessment_date if climate_risk else None,
                'deforestation_check_date': deforestation.check_date if deforestation else None,
                'farm_size_acres': float(farm.size_acres),
                'ndvi': float(latest_scan.ndvi_mean) if latest_scan else None,
                'climate_risk': float(climate_risk.overall_risk_score) if climate_risk else None
            }
        }
    
    def _score_farm_size(self, acres):
        """
        Score based on farm size (max 100 points).
        
        Larger farms generally indicate more established operations.
        
        Args:
            acres: Farm size in acres
        
        Returns:
            int: Score 0-100
        """
        if acres >= 10.0:
            return 100
        elif acres >= 5.0:
            return 90
        elif acres >= 2.5:
            return 80
        elif acres >= 1.5:
            return 70
        elif acres >= 1.0:
            return 60
        elif acres >= 0.5:
            return 50
        else:
            return 40
    
    def _score_crop_health(self, ndvi):
        """
        Score based on NDVI (Normalized Difference Vegetation Index).
        
        NDVI ranges from -1 to 1:
        - 0.75-1.0: Dense, healthy vegetation
        - 0.60-0.75: Moderate vegetation
        - 0.40-0.60: Sparse vegetation
        - Below 0.40: Stressed or no vegetation
        
        Args:
            ndvi: NDVI value (-1 to 1) or None
        
        Returns:
            int: Score 0-100
        """
        if ndvi is None:
            return 50  # Default if no data (neutral)
        
        if ndvi >= 0.80:
            return 100
        elif ndvi >= 0.75:
            return 95
        elif ndvi >= 0.70:
            return 90
        elif ndvi >= 0.65:
            return 85
        elif ndvi >= 0.60:
            return 80
        elif ndvi >= 0.55:
            return 75
        elif ndvi >= 0.50:
            return 70
        elif ndvi >= 0.45:
            return 65
        elif ndvi >= 0.40:
            return 60
        elif ndvi >= 0.35:
            return 55
        else:
            return 50
    
    def _score_climate_risk(self, risk_score):
        """
        Score based on climate risk assessment.
        
        Lower climate risk = higher credit score.
        
        Args:
            risk_score: Climate risk (0-100, where 100 is highest risk)
        
        Returns:
            int: Score 0-100
        """
        # Invert the risk score (high risk = low score)
        return int(100 - risk_score)
    
    def _score_deforestation(self, detected):
        """
        Score based on deforestation status.
        
        Deforestation is a binary disqualifier - it severely impacts score.
        
        Args:
            detected: Boolean indicating if deforestation was detected
        
        Returns:
            int: 0 if detected, 100 if clear
        """
        return 0 if detected else 100
    
    def _score_payment_history(self, farmer):
        """
        Score based on loan repayment history.
        
        Perfect repayment history = 100
        No history (new farmer) = 50 (neutral)
        Poor history = Lower score
        
        Args:
            farmer: Farmer model instance
        
        Returns:
            int: Score 0-100
        """
        from apps.loans.models import LoanRepayment
        
        # Count total payments for this farmer
        total_payments = LoanRepayment.objects.filter(
            loan__farmer=farmer
        ).count()
        
        if total_payments == 0:
            return 50  # New farmer, neutral score
        
        # Count on-time payments
        on_time_payments = LoanRepayment.objects.filter(
            loan__farmer=farmer,
            is_paid=True,
            is_late=False
        ).count()
        
        # Count late but paid payments (partial credit)
        late_paid_payments = LoanRepayment.objects.filter(
            loan__farmer=farmer,
            is_paid=True,
            is_late=True
        ).count()
        
        # Calculate weighted score
        # On-time: 100% credit
        # Late but paid: 70% credit
        # Unpaid: 0% credit
        weighted_payments = on_time_payments + (late_paid_payments * 0.7)
        
        return int(min(100, (weighted_payments / total_payments) * 100))
    
    def _check_fraud_alerts(self, farmer):
        """
        Check for active fraud alerts and calculate score penalty.
        
        Args:
            farmer: Farmer model instance
        
        Returns:
            int: Score penalty (0 if no alerts)
        """
        from apps.scoring.models import FraudAlert
        
        # Get unresolved fraud alerts
        active_alerts = FraudAlert.objects.filter(
            farmer=farmer,
            status__in=['pending', 'investigating', 'confirmed']
        )
        
        total_penalty = 0
        for alert in active_alerts:
            if alert.severity == 'critical':
                total_penalty += 300  # Major penalty
            elif alert.severity == 'high':
                total_penalty += 200
            elif alert.severity == 'medium':
                total_penalty += 100
            else:  # low
                total_penalty += 50
        
        return total_penalty
    
    def _calculate_credit_terms(self, score):
        """
        Calculate recommended loan terms based on score.
        
        Returns:
            tuple: (max_loan_amount, (min_rate, max_rate), default_probability)
        """
        if score >= 850:
            return Decimal('100000.00'), (8.0, 10.0), 3.0
        elif score >= 800:
            return Decimal('85000.00'), (9.0, 11.0), 4.0
        elif score >= 750:
            return Decimal('75000.00'), (10.0, 12.0), 5.0
        elif score >= 700:
            return Decimal('65000.00'), (11.0, 13.0), 6.0
        elif score >= 650:
            return Decimal('55000.00'), (12.0, 14.0), 8.0
        elif score >= 600:
            return Decimal('45000.00'), (13.0, 15.0), 10.0
        elif score >= 550:
            return Decimal('35000.00'), (14.0, 16.0), 12.0
        elif score >= 500:
            return Decimal('30000.00'), (15.0, 17.0), 15.0
        elif score >= 450:
            return Decimal('25000.00'), (16.0, 18.0), 18.0
        elif score >= 400:
            return Decimal('20000.00'), (17.0, 19.0), 22.0
        else:
            return Decimal('15000.00'), (18.0, 20.0), 28.0
    
    def _calculate_confidence(self, satellite_scan, climate_risk, deforestation):
        """
        Calculate confidence level in the score.
        
        Confidence decreases as data gets older.
        
        Args:
            satellite_scan: Latest NDVIHistory instance or None
            climate_risk: Latest ClimateRiskAssessment or None
            deforestation: Latest DeforestationCheck or None
        
        Returns:
            float: Confidence level (0.0-1.0)
        """
        confidence = 0.3  # Base confidence
        
        # Satellite data freshness
        if satellite_scan:
            days_old = (timezone.now().date() - satellite_scan.acquisition_date).days
            if days_old <= 7:
                confidence += 0.25
            elif days_old <= 14:
                confidence += 0.20
            elif days_old <= 30:
                confidence += 0.15
            else:
                confidence += 0.10
        
        # Climate data freshness
        if climate_risk:
            days_old = (timezone.now().date() - climate_risk.assessment_date).days
            if days_old <= 30:
                confidence += 0.20
            elif days_old <= 60:
                confidence += 0.15
            else:
                confidence += 0.10
        
        # Deforestation check freshness
        if deforestation:
            days_old = (timezone.now().date() - deforestation.check_date).days
            if days_old <= 90:
                confidence += 0.15
            else:
                confidence += 0.10
        
        return min(confidence, 0.95)  # Cap at 95%