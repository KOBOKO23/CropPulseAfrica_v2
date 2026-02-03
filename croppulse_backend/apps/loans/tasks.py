"""
Loans App Celery Tasks

Scheduled tasks for:
- Flagging defaulted loans
- Marking overdue instalments
- Processing climate events
"""

from celery import shared_task
from datetime import date, timedelta
from django.db import transaction

from apps.loans.models import LoanRepayment
from apps.loans.services import MpesaIntegration, RestructureService


@shared_task(name='loans.flag_defaulted_loans')
def flag_defaulted_loans(days_overdue: int = 90) -> dict:
    """
    Flag loans as defaulted if any instalment is overdue beyond threshold.
    
    Scheduled to run daily at 3:00 AM UTC.
    
    Args:
        days_overdue: Number of days overdue to trigger default (default: 90)
    
    Returns:
        {
            'count': int,
            'status': 'success'
        }
    """
    count = MpesaIntegration.flag_defaults(days_overdue=days_overdue)
    
    return {
        'count': count,
        'status': 'success',
        'message': f'Flagged {count} loans as defaulted'
    }


@shared_task(name='loans.mark_overdue_instalments')
def mark_overdue_instalments() -> dict:
    """
    Mark instalments as overdue if past due date.
    
    Updates is_late and days_late fields for unpaid instalments.
    
    Scheduled to run daily at 3:30 AM UTC.
    
    Returns:
        {
            'count': int,
            'status': 'success'
        }
    """
    today = date.today()
    
    # Find all unpaid instalments past due date
    overdue = LoanRepayment.objects.filter(
        is_paid=False,
        due_date__lt=today
    )
    
    count = 0
    for instalment in overdue:
        days_late = (today - instalment.due_date).days
        
        instalment.is_late = True
        instalment.days_late = days_late
        instalment.save(update_fields=['is_late', 'days_late'])
        
        count += 1
    
    return {
        'count': count,
        'status': 'success',
        'message': f'Marked {count} instalments as overdue'
    }


@shared_task(name='loans.process_climate_event')
def process_climate_event(
    event_id: str,
    severity: str,
    region: str,
    description: str = ''
) -> dict:
    """
    Process a climate event and create rate adjustments for affected loans.
    
    Called by climate app when severe weather event is detected.
    
    Args:
        event_id: Unique climate event ID
        severity: 'low', 'moderate', 'high', or 'critical'
        region: Geographic region affected
        description: Event description
    
    Returns:
        {
            'adjustments_created': int,
            'adjustments_auto_applied': int,
            'status': 'success'
        }
    """
    adjustments = RestructureService.on_climate_event(
        event_id=event_id,
        severity=severity,
        region=region,
        description=description
    )
    
    auto_applied = sum(1 for adj in adjustments if adj.status == 'applied')
    
    return {
        'adjustments_created': len(adjustments),
        'adjustments_auto_applied': auto_applied,
        'status': 'success',
        'message': f'Created {len(adjustments)} adjustments ({auto_applied} auto-applied)'
    }


# Schedule configuration (add to settings/base.py):
"""
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'flag-defaulted-loans': {
        'task': 'loans.flag_defaulted_loans',
        'schedule': crontab(hour=3, minute=0),  # 3:00 AM UTC daily
        'kwargs': {'days_overdue': 90}
    },
    'mark-overdue-instalments': {
        'task': 'loans.mark_overdue_instalments',
        'schedule': crontab(hour=3, minute=30),  # 3:30 AM UTC daily
    },
}
"""