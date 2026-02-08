"""
Scoring App Celery Tasks
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta, date


@shared_task(name='scoring.recalculate_scores')
def recalculate_scores():
    """
    Recalculate scores for farmers with expiring scores.
    
    Run daily to ensure scores stay fresh.
    """
    from apps.scoring.models import PulseScore
    from apps.scoring.algorithms import PulseScoreEngine
    
    # Find scores expiring in next 7 days
    expiring_soon = PulseScore.objects.filter(
        is_current=True,
        is_frozen=False,
        valid_until__lte=timezone.now() + timedelta(days=7)
    ).select_related('farmer', 'farm')
    
    engine = PulseScoreEngine()
    count = 0
    
    for old_score in expiring_soon:
        try:
            # Calculate new score
            result = engine.calculate_score(old_score.farmer, old_score.farm)
            
            # Mark old as non-current
            old_score.is_current = False
            old_score.save()
            
            # Create new
            PulseScore.objects.create(
                farmer=old_score.farmer,
                farm=old_score.farm,
                score=result['score'],
                confidence_level=result['confidence'],
                farm_size_score=result['breakdown']['farm_size'],
                crop_health_score=result['breakdown']['crop_health'],
                climate_risk_score=result['breakdown']['climate_risk'],
                deforestation_score=result['breakdown']['deforestation'],
                payment_history_score=result['breakdown']['payment_history'],
                max_loan_amount=result['max_loan_amount'],
                recommended_interest_rate_min=result['recommended_interest_rate'][0],
                recommended_interest_rate_max=result['recommended_interest_rate'][1],
                default_probability=result['default_probability'],
                calculation_method='v1.0',
                factors_used=result['factors_used'],
                satellite_data_date=result['factors_used'].get('satellite_data_date'),
                climate_data_date=result['factors_used'].get('climate_data_date'),
                valid_until=result['valid_until'],
                is_current=True
            )
            
            count += 1
        except Exception as e:
            print(f"Error recalculating score for {old_score.farmer.full_name}: {e}")
    
    return {'scores_recalculated': count}


@shared_task(name='scoring.update_score_history')
def update_score_history():
    """
    Update daily score history for all farmers.
    
    Run once per day.
    """
    from apps.scoring.models import PulseScore, ScoreHistory
    
    current_scores = PulseScore.objects.filter(is_current=True)
    count = 0
    
    for score in current_scores:
        # Get yesterday's score
        yesterday = date.today() - timedelta(days=1)
        prev_history = ScoreHistory.objects.filter(
            farmer=score.farmer,
            date=yesterday
        ).first()
        
        change = score.score - (prev_history.score if prev_history else score.score)
        
        # Create today's history
        ScoreHistory.objects.get_or_create(
            farmer=score.farmer,
            date=date.today(),
            defaults={
                'score': score.score,
                'change_from_previous': change,
                'farm_size_score': score.farm_size_score,
                'crop_health_score': score.crop_health_score,
                'climate_risk_score': score.climate_risk_score,
                'payment_history_score': score.payment_history_score
            }
        )
        count += 1
    
    return {'history_entries_created': count}


@shared_task(name='scoring.run_fraud_checks')
def run_fraud_checks():
    """
    Run fraud detection on all active farms.
    
    Run daily.
    """
    from apps.farms.models import Farm
    from apps.scoring.algorithms import FraudDetector
    
    farms = Farm.objects.filter(is_active=True).select_related('farmer')
    alerts_created = 0
    
    for farm in farms:
        alerts = FraudDetector.run_all_checks(farm.farmer, farm)
        alerts_created += len(alerts)
    
    return {'fraud_alerts_created': alerts_created}