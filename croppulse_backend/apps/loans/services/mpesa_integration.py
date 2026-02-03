"""
M-Pesa Integration Service

Handles:
- Loan disbursement via M-Pesa B2C (Business to Customer)
- Repayment callback processing
- Default flagging based on missed payments
"""

from decimal import Decimal
from datetime import date, datetime
from django.db import transaction
from django.utils import timezone

from apps.loans.models import (
    LoanApplication,
    LoanRepayment,
    LoanAuditLog
)
from apps.loans.services.repayment_scheduler import RepaymentScheduler
from integrations.mpsa.daraja import DarajaAPI


class MpesaIntegration:
    """
    M-Pesa integration for loan disbursement and repayment tracking.
    """
    
    @staticmethod
    @transaction.atomic
    def disburse(loan: LoanApplication) -> dict:
        """
        Disburse loan to farmer via M-Pesa B2C.
        
        Process:
        1. Validate loan is approved
        2. Call M-Pesa B2C API to send funds
        3. Update loan status to 'disbursed'
        4. Generate repayment schedule
        5. Log disbursement
        
        Args:
            loan: LoanApplication in 'approved' status
        
        Returns:
            {
                'success': bool,
                'transaction_id': str,
                'message': str
            }
        """
        if loan.status != 'approved':
            raise ValueError(
                f"Cannot disburse loan in '{loan.status}' status"
            )
        
        # Get farmer's phone number
        phone_number = loan.farmer.phone_number
        amount = loan.approved_amount
        
        # Call M-Pesa B2C
        daraja = DarajaAPI()
        
        try:
            response = daraja.b2c_payment(
                phone_number=phone_number,
                amount=float(amount),
                occasion=f"Loan Disbursement - {loan.application_id}",
                remarks=f"CropPulse Loan: {loan.loan_purpose}"
            )
            
            if response.get('ResponseCode') == '0':
                # Success
                transaction_id = response.get('ConversationID')
                
                # Update loan status
                loan.status = 'disbursed'
                loan.disbursed_at = timezone.now()
                loan.save()
                
                # Generate repayment schedule
                RepaymentScheduler.generate(loan)
                
                # Create audit log
                LoanAuditLog.objects.create(
                    loan=loan,
                    action='disbursement',
                    old_value={'status': 'approved'},
                    new_value={
                        'status': 'disbursed',
                        'amount': str(amount),
                        'transaction_id': transaction_id,
                        'disbursed_at': str(loan.disbursed_at)
                    },
                    details=f"Loan disbursed via M-Pesa to {phone_number}",
                    triggered_by_system=True
                )
                
                return {
                    'success': True,
                    'transaction_id': transaction_id,
                    'message': f'Successfully disbursed KES {amount} to {phone_number}'
                }
            else:
                # M-Pesa error
                return {
                    'success': False,
                    'transaction_id': None,
                    'message': response.get('ResponseDescription', 'M-Pesa transaction failed')
                }
        
        except Exception as e:
            return {
                'success': False,
                'transaction_id': None,
                'message': f'Error: {str(e)}'
            }
    
    @staticmethod
    @transaction.atomic
    def on_repayment_callback(payload: dict) -> dict:
        """
        Process M-Pesa C2B (Customer to Business) callback for loan repayment.
        
        Called by M-Pesa when farmer makes a payment.
        
        Payload structure (example):
        {
            'TransactionType': 'Pay Bill',
            'TransID': 'OEI2AK4Q16',
            'TransTime': '20230615143021',
            'TransAmount': '5000.00',
            'BusinessShortCode': '174379',
            'BillRefNumber': 'LN-2026-001234',  # loan.application_id
            'InvoiceNumber': '',
            'OrgAccountBalance': '49200.00',
            'ThirdPartyTransID': '',
            'MSISDN': '254712345678',
            'FirstName': 'John',
            'MiddleName': 'Doe',
            'LastName': ''
        }
        
        Args:
            payload: M-Pesa callback data
        
        Returns:
            {
                'success': bool,
                'message': str,
                'loan_id': str,
                'amount_processed': Decimal
            }
        """
        # Extract fields
        transaction_id = payload.get('TransID')
        amount = Decimal(str(payload.get('TransAmount', '0')))
        loan_ref = payload.get('BillRefNumber')  # This should be loan.application_id
        
        if not loan_ref:
            return {
                'success': False,
                'message': 'Missing BillRefNumber (loan ID)',
                'loan_id': None,
                'amount_processed': Decimal('0.00')
            }
        
        # Find loan
        try:
            loan = LoanApplication.objects.get(
                application_id=loan_ref,
                status='disbursed'
            )
        except LoanApplication.DoesNotExist:
            return {
                'success': False,
                'message': f'Loan {loan_ref} not found or not disbursed',
                'loan_id': loan_ref,
                'amount_processed': Decimal('0.00')
            }
        
        # Find earliest unpaid instalment
        unpaid_instalments = RepaymentScheduler.get_unpaid_instalments(loan)
        
        if not unpaid_instalments.exists():
            # Loan already fully paid
            return {
                'success': True,
                'message': 'Loan already fully paid',
                'loan_id': loan.application_id,
                'amount_processed': Decimal('0.00')
            }
        
        # Apply payment to earliest unpaid instalment
        instalment = unpaid_instalments.first()
        remaining = amount
        
        instalment.amount_paid += remaining
        instalment.mpesa_transaction_id = transaction_id
        instalment.paid_date = date.today()
        
        # Check if instalment is now fully paid
        if instalment.amount_paid >= instalment.amount_due:
            instalment.is_paid = True
            
            # Check if payment was late
            if date.today() > instalment.due_date:
                instalment.is_late = True
                instalment.days_late = (date.today() - instalment.due_date).days
        
        instalment.save()
        
        # Create audit log
        LoanAuditLog.objects.create(
            loan=loan,
            action='repayment',
            old_value={
                'payment_number': instalment.payment_number,
                'amount_paid_before': str(instalment.amount_paid - amount)
            },
            new_value={
                'payment_number': instalment.payment_number,
                'amount_paid_after': str(instalment.amount_paid),
                'transaction_id': transaction_id,
                'is_paid': instalment.is_paid
            },
            details=f"Repayment received: KES {amount} via M-Pesa ({transaction_id})",
            triggered_by_system=True
        )
        
        # Check if loan is now fully repaid
        if not RepaymentScheduler.get_unpaid_instalments(loan).exists():
            loan.status = 'repaid'
            loan.save()
            
            LoanAuditLog.objects.create(
                loan=loan,
                action='status_change',
                old_value={'status': 'disbursed'},
                new_value={'status': 'repaid'},
                details="Loan fully repaid",
                triggered_by_system=True
            )
        
        return {
            'success': True,
            'message': f'Payment of KES {amount} applied to instalment {instalment.payment_number}',
            'loan_id': loan.application_id,
            'amount_processed': amount
        }
    
    @staticmethod
    @transaction.atomic
    def flag_defaults(days_overdue: int = 90) -> int:
        """
        Flag loans as defaulted if any instalment is overdue beyond threshold.
        
        Run as a Celery task (e.g., daily at 3am).
        
        Args:
            days_overdue: Number of days overdue to trigger default (default: 90)
        
        Returns:
            Number of loans flagged as defaulted
        """
        from datetime import timedelta
        
        cutoff_date = date.today() - timedelta(days=days_overdue)
        
        # Find loans with instalments overdue beyond cutoff
        overdue_instalments = LoanRepayment.objects.filter(
            loan__status='disbursed',
            is_paid=False,
            due_date__lt=cutoff_date
        ).select_related('loan')
        
        loan_ids = set()
        for instalment in overdue_instalments:
            loan_ids.add(instalment.loan_id)
        
        # Update loans to defaulted status
        defaulted_loans = LoanApplication.objects.filter(
            id__in=loan_ids,
            status='disbursed'
        )
        
        count = 0
        for loan in defaulted_loans:
            loan.status = 'defaulted'
            loan.save()
            
            LoanAuditLog.objects.create(
                loan=loan,
                action='status_change',
                old_value={'status': 'disbursed'},
                new_value={'status': 'defaulted'},
                details=f"Flagged as defaulted: payment overdue by {days_overdue}+ days",
                triggered_by_system=True
            )
            
            count += 1
        
        return count