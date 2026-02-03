"""
Loan Calculator Service

Handles:
- EMI (Equated Monthly Instalment) calculation
- Amortisation schedule generation
- Interest/principal breakdown
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Any


class LoanCalculator:
    """Pure calculation service - no database operations"""
    
    @staticmethod
    def calculate_emi(
        principal: Decimal,
        annual_interest_rate: float,
        months: int
    ) -> Decimal:
        """
        Calculate Equated Monthly Instalment (EMI).
        
        Formula: EMI = P × r × (1 + r)^n / ((1 + r)^n - 1)
        Where:
        - P = Principal
        - r = Monthly interest rate (annual_rate / 12 / 100)
        - n = Number of months
        
        Args:
            principal: Loan amount
            annual_interest_rate: Annual rate as percentage (e.g., 12.5 for 12.5%)
            months: Loan tenor in months
        
        Returns:
            Monthly EMI amount (rounded to 2 decimal places)
        """
        if annual_interest_rate == 0:
            # Zero interest rate - simple division
            return (principal / Decimal(months)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
        
        # Convert annual rate to monthly decimal rate
        monthly_rate = Decimal(str(annual_interest_rate)) / Decimal('1200')
        
        # Calculate (1 + r)^n
        multiplier = (Decimal('1') + monthly_rate) ** months
        
        # Calculate EMI
        emi = (principal * monthly_rate * multiplier) / (multiplier - Decimal('1'))
        
        return emi.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def generate_amortisation_schedule(
        principal: Decimal,
        annual_interest_rate: float,
        months: int,
        start_date: date
    ) -> Dict[str, Any]:
        """
        Generate complete amortisation schedule.
        
        Returns:
            {
                'monthly_payment': Decimal,
                'total_interest': Decimal,
                'total_repayment': Decimal,
                'start_date': date,
                'end_date': date,
                'rows': [
                    {
                        'payment_number': int,
                        'due_date': date,
                        'opening_balance': Decimal,
                        'emi': Decimal,
                        'principal': Decimal,
                        'interest': Decimal,
                        'closing_balance': Decimal
                    },
                    ...
                ]
            }
        """
        emi = LoanCalculator.calculate_emi(principal, annual_interest_rate, months)
        
        monthly_rate = Decimal(str(annual_interest_rate)) / Decimal('1200')
        
        balance = principal
        total_interest = Decimal('0.00')
        rows = []
        
        for month in range(1, months + 1):
            # Calculate interest for this month
            interest_payment = (balance * monthly_rate).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            
            # Calculate principal repayment
            principal_payment = emi - interest_payment
            
            # Last payment adjustment to clear remaining balance
            if month == months:
                principal_payment = balance
                emi = principal_payment + interest_payment
            
            # Update balance
            opening_balance = balance
            balance = balance - principal_payment
            
            # Ensure balance doesn't go negative due to rounding
            if balance < Decimal('0.01'):
                balance = Decimal('0.00')
            
            total_interest += interest_payment
            
            # Calculate due date
            due_date = start_date + relativedelta(months=month)
            
            rows.append({
                'payment_number': month,
                'due_date': due_date,
                'opening_balance': opening_balance.quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                ),
                'emi': emi.quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                ),
                'principal': principal_payment.quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                ),
                'interest': interest_payment.quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                ),
                'closing_balance': balance.quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
            })
        
        end_date = start_date + relativedelta(months=months)
        
        return {
            'monthly_payment': emi.quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            ),
            'total_interest': total_interest.quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            ),
            'total_repayment': (principal + total_interest).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            ),
            'start_date': start_date,
            'end_date': end_date,
            'rows': rows
        }
    
    @staticmethod
    def reschedule_remaining_balance(
        outstanding_balance: Decimal,
        new_annual_interest_rate: float,
        new_months: int,
        start_date: date
    ) -> Dict[str, Any]:
        """
        Recalculate schedule for remaining balance (used in loan restructuring).
        
        This is essentially the same as generate_amortisation_schedule but
        semantically clearer for restructuring scenarios.
        
        Args:
            outstanding_balance: Current unpaid principal
            new_annual_interest_rate: New rate to apply
            new_months: New tenor
            start_date: When new schedule starts
        
        Returns:
            Same structure as generate_amortisation_schedule
        """
        return LoanCalculator.generate_amortisation_schedule(
            principal=outstanding_balance,
            annual_interest_rate=new_annual_interest_rate,
            months=new_months,
            start_date=start_date
        )


# Example usage:
if __name__ == '__main__':
    from datetime import date
    
    # Test: 100,000 KES loan at 12% for 12 months
    principal = Decimal('100000.00')
    rate = 12.0  # 12% per annum
    tenor = 12  # months
    start = date(2026, 3, 1)
    
    schedule = LoanCalculator.generate_amortisation_schedule(
        principal, rate, tenor, start
    )
    
    print(f"Monthly EMI: KES {schedule['monthly_payment']}")
    print(f"Total Interest: KES {schedule['total_interest']}")
    print(f"Total Repayment: KES {schedule['total_repayment']}")
    print(f"\nFirst 3 payments:")
    for row in schedule['rows'][:3]:
        print(f"  Month {row['payment_number']}: "
              f"Principal={row['principal']}, "
              f"Interest={row['interest']}, "
              f"Balance={row['closing_balance']}")