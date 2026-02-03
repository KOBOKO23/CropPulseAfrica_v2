"""
Repayment Scheduler Service

Handles:
- Generate repayment schedule when loan is disbursed
- Regenerate schedule when loan is restructured
- Create LoanRepayment records for tracking
"""

from decimal import Decimal
from datetime import date
from django.db import transaction
from django.utils import timezone

from apps.loans.models import (
    LoanApplication,
    LoanRepayment,
    RepaymentSchedule,
    LoanAuditLog
)
from apps.loans.services.loan_calculator import LoanCalculator


class RepaymentScheduler:
    """
    Service for creating and managing loan repayment schedules.
    """
    
    @staticmethod
    @transaction.atomic
    def generate(loan: LoanApplication, start_date: date = None) -> RepaymentSchedule:
        """
        Generate initial repayment schedule when loan is disbursed.
        
        Args:
            loan: LoanApplication instance (must be 'approved' or 'disbursed')
            start_date: Optional start date (defaults to today + 1 month)
        
        Returns:
            RepaymentSchedule instance
        
        Raises:
            ValueError: If loan is not in correct status or schedule already exists
        """
        if loan.status not in ['approved', 'disbursed']:
            raise ValueError(
                f"Cannot generate schedule for loan in '{loan.status}' status"
            )
        
        # Check if schedule already exists
        existing = RepaymentSchedule.objects.filter(
            loan=loan,
            is_current=True
        ).exists()
        
        if existing:
            raise ValueError(
                f"Active repayment schedule already exists for loan {loan.application_id}"
            )
        
        # Default start date: first of next month
        if not start_date:
            today = date.today()
            start_date = date(today.year, today.month, 1)
            if start_date <= today:
                # Move to next month
                from dateutil.relativedelta import relativedelta
                start_date = start_date + relativedelta(months=1)
        
        # Generate amortisation table
        schedule_data = LoanCalculator.generate_amortisation_schedule(
            principal=loan.approved_amount,
            annual_interest_rate=loan.interest_rate,
            months=loan.repayment_period_months,
            start_date=start_date
        )
        
        # Create RepaymentSchedule summary
        schedule = RepaymentSchedule.objects.create(
            loan=loan,
            total_instalments=loan.repayment_period_months,
            monthly_payment=schedule_data['monthly_payment'],
            total_interest=schedule_data['total_interest'],
            total_repayment=schedule_data['total_repayment'],
            start_date=schedule_data['start_date'],
            end_date=schedule_data['end_date'],
            interest_rate_used=loan.interest_rate,
            is_current=True
        )
        
        # Create individual LoanRepayment records
        repayment_records = []
        for row in schedule_data['rows']:
            repayment_records.append(
                LoanRepayment(
                    loan=loan,
                    payment_number=row['payment_number'],
                    due_date=row['due_date'],
                    amount_due=row['emi']
                )
            )
        
        LoanRepayment.objects.bulk_create(repayment_records)
        
        # Create audit log
        LoanAuditLog.objects.create(
            loan=loan,
            action='status_change',
            old_value=None,
            new_value={
                'schedule_created': True,
                'monthly_payment': str(schedule.monthly_payment),
                'total_instalments': schedule.total_instalments,
                'start_date': str(schedule.start_date),
                'end_date': str(schedule.end_date)
            },
            details=f"Repayment schedule generated: {schedule.total_instalments} payments of KES {schedule.monthly_payment}",
            triggered_by_system=True
        )
        
        return schedule
    
    @staticmethod
    @transaction.atomic
    def regenerate(
        loan: LoanApplication,
        new_interest_rate: float,
        new_repayment_period_months: int,
        outstanding_balance: Decimal = None,
        start_date: date = None
    ) -> RepaymentSchedule:
        """
        Regenerate schedule for restructured loan.
        
        Used when:
        - Climate event triggers rate reduction + tenor extension
        - Loan is rescheduled due to default risk
        - Manual restructure by bank
        
        Process:
        1. Mark old schedule as is_current=False
        2. Delete unpaid LoanRepayment records
        3. Generate new schedule based on outstanding balance
        4. Create new LoanRepayment records
        
        Args:
            loan: LoanApplication instance
            new_interest_rate: New rate to apply
            new_repayment_period_months: New tenor
            outstanding_balance: Remaining balance (defaults to loan.outstanding_balance)
            start_date: When new schedule starts (defaults to next month)
        
        Returns:
            New RepaymentSchedule instance
        """
        if loan.status != 'disbursed':
            raise ValueError(
                f"Cannot regenerate schedule for loan in '{loan.status}' status"
            )
        
        # Calculate outstanding balance if not provided
        if outstanding_balance is None:
            outstanding_balance = loan.outstanding_balance
        
        if outstanding_balance <= Decimal('0'):
            raise ValueError("No outstanding balance to reschedule")
        
        # Mark old schedule as superseded
        old_schedules = RepaymentSchedule.objects.filter(
            loan=loan,
            is_current=True
        )
        old_schedule = old_schedules.first()
        
        old_schedules.update(is_current=False)
        
        # Delete unpaid repayment records (paid ones stay for audit trail)
        LoanRepayment.objects.filter(
            loan=loan,
            is_paid=False
        ).delete()
        
        # Default start date: next month
        if not start_date:
            today = date.today()
            start_date = date(today.year, today.month, 1)
            from dateutil.relativedelta import relativedelta
            start_date = start_date + relativedelta(months=1)
        
        # Generate new amortisation schedule
        schedule_data = LoanCalculator.reschedule_remaining_balance(
            outstanding_balance=outstanding_balance,
            new_annual_interest_rate=new_interest_rate,
            new_months=new_repayment_period_months,
            start_date=start_date
        )
        
        # Create new RepaymentSchedule
        new_schedule = RepaymentSchedule.objects.create(
            loan=loan,
            total_instalments=new_repayment_period_months,
            monthly_payment=schedule_data['monthly_payment'],
            total_interest=schedule_data['total_interest'],
            total_repayment=schedule_data['total_repayment'],
            start_date=schedule_data['start_date'],
            end_date=schedule_data['end_date'],
            interest_rate_used=new_interest_rate,
            is_current=True
        )
        
        # Create new LoanRepayment records
        repayment_records = []
        for row in schedule_data['rows']:
            repayment_records.append(
                LoanRepayment(
                    loan=loan,
                    payment_number=row['payment_number'],
                    due_date=row['due_date'],
                    amount_due=row['emi']
                )
            )
        
        LoanRepayment.objects.bulk_create(repayment_records)
        
        # Update loan's interest rate and tenor
        loan.interest_rate = new_interest_rate
        loan.repayment_period_months = new_repayment_period_months
        loan.save()
        
        # Create audit log
        LoanAuditLog.objects.create(
            loan=loan,
            action='restructure',
            old_value={
                'interest_rate': old_schedule.interest_rate_used if old_schedule else None,
                'monthly_payment': str(old_schedule.monthly_payment) if old_schedule else None,
                'outstanding_balance': str(outstanding_balance)
            },
            new_value={
                'interest_rate': new_interest_rate,
                'repayment_period_months': new_repayment_period_months,
                'monthly_payment': str(new_schedule.monthly_payment),
                'start_date': str(new_schedule.start_date),
                'end_date': str(new_schedule.end_date)
            },
            details=f"Schedule regenerated: {new_repayment_period_months} payments of KES {new_schedule.monthly_payment} at {new_interest_rate}%",
            triggered_by_system=True
        )
        
        return new_schedule
    
    @staticmethod
    def get_current_schedule(loan: LoanApplication) -> RepaymentSchedule:
        """
        Get the active repayment schedule for a loan.
        
        Args:
            loan: LoanApplication instance
        
        Returns:
            RepaymentSchedule or None
        """
        return RepaymentSchedule.objects.filter(
            loan=loan,
            is_current=True
        ).first()
    
    @staticmethod
    def get_unpaid_instalments(loan: LoanApplication):
        """
        Get all unpaid instalments for a loan.
        
        Args:
            loan: LoanApplication instance
        
        Returns:
            QuerySet of LoanRepayment
        """
        return LoanRepayment.objects.filter(
            loan=loan,
            is_paid=False
        ).order_by('payment_number')
    
    @staticmethod
    def get_overdue_instalments(loan: LoanApplication):
        """
        Get overdue instalments (unpaid and past due date).
        
        Args:
            loan: LoanApplication instance
        
        Returns:
            QuerySet of LoanRepayment
        """
        from datetime import date
        return LoanRepayment.objects.filter(
            loan=loan,
            is_paid=False,
            due_date__lt=date.today()
        ).order_by('due_date')