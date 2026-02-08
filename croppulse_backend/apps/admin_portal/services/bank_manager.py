# apps/admin_portal/services/bank_manager.py

from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta


class BankManager:
    """
    Service for managing bank configurations and analytics
    """
    
    @staticmethod
    def create_bank_configuration(bank, **kwargs):
        """
        Create configuration for a bank
        
        Args:
            bank: Bank instance
            **kwargs: Configuration parameters
            
        Returns:
            BankConfiguration instance
        """
        from apps.admin_portal.models import BankConfiguration
        
        config = BankConfiguration.objects.create(
            bank=bank,
            api_rate_limit=kwargs.get('api_rate_limit', 1000),
            webhook_url=kwargs.get('webhook_url', ''),
            webhook_secret=kwargs.get('webhook_secret', ''),
            max_farmers=kwargs.get('max_farmers', 10000),
            max_loans_per_farmer=kwargs.get('max_loans_per_farmer', 5),
            min_credit_score=kwargs.get('min_credit_score', 0),
            use_satellite_verification=kwargs.get('use_satellite_verification', True),
            use_climate_risk_assessment=kwargs.get('use_climate_risk_assessment', True),
            use_fraud_detection=kwargs.get('use_fraud_detection', True),
            notification_channels=kwargs.get('notification_channels', ['email']),
            billing_plan=kwargs.get('billing_plan', 'basic'),
            monthly_api_quota=kwargs.get('monthly_api_quota', 50000),
            custom_config=kwargs.get('custom_config', {})
        )
        
        return config
    
    @staticmethod
    def get_bank_stats(bank):
        """
        Get comprehensive statistics for a bank
        
        Args:
            bank: Bank instance
            
        Returns:
            dict: Bank statistics
        """
        from apps.farmers.models import Farmer
        from apps.loans.models import Loan
        from apps.scoring.models import CreditScore
        from apps.banks.models import BankFarmerLink
        
        # Get linked farmers
        farmer_links = BankFarmerLink.objects.filter(
            bank=bank,
            is_active=True
        )
        
        farmer_ids = farmer_links.values_list('farmer_id', flat=True)
        farmers = Farmer.objects.filter(id__in=farmer_ids)
        
        # Loan statistics
        loans = Loan.objects.filter(farmer__in=farmers)
        
        total_loans = loans.count()
        active_loans = loans.filter(status='active').count()
        completed_loans = loans.filter(status='completed').count()
        defaulted_loans = loans.filter(status='defaulted').count()
        
        total_disbursed = loans.filter(
            status__in=['active', 'completed', 'defaulted']
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        total_outstanding = loans.filter(
            status='active'
        ).aggregate(Sum('outstanding_balance'))['outstanding_balance__sum'] or 0
        
        # Calculate default rate
        if total_loans > 0:
            default_rate = (defaulted_loans / total_loans) * 100
        else:
            default_rate = 0.0
        
        # Credit score statistics
        scores = CreditScore.objects.filter(farmer__in=farmers)
        avg_credit_score = scores.aggregate(Avg('score'))['score__avg'] or 0
        
        # API usage
        config = bank.configuration if hasattr(bank, 'configuration') else None
        if config:
            from apps.admin_portal.models import APIUsageLog
            
            thirty_days_ago = timezone.now() - timedelta(days=30)
            api_usage = APIUsageLog.objects.filter(
                bank=bank,
                timestamp__gte=thirty_days_ago
            ).count()
            
            quota_remaining = config.monthly_api_quota - api_usage
        else:
            api_usage = 0
            quota_remaining = 0
        
        return {
            'bank_id': bank.id,
            'bank_name': bank.name,
            'farmers': {
                'total': farmers.count(),
                'verified': farmers.filter(user__is_verified=True).count(),
                'with_active_loans': farmers.filter(loans__status='active').distinct().count()
            },
            'loans': {
                'total': total_loans,
                'active': active_loans,
                'completed': completed_loans,
                'defaulted': defaulted_loans,
                'default_rate': round(default_rate, 2),
                'total_disbursed': float(total_disbursed),
                'total_outstanding': float(total_outstanding)
            },
            'credit_scores': {
                'average': round(avg_credit_score, 2),
                'above_threshold': scores.filter(score__gte=50).count(),
                'below_threshold': scores.filter(score__lt=50).count()
            },
            'api': {
                'usage_this_month': api_usage,
                'quota_remaining': quota_remaining
            }
        }
    
    @staticmethod
    def update_api_quota(bank, new_quota):
        """
        Update monthly API quota for a bank
        
        Args:
            bank: Bank instance
            new_quota: New quota value
        """
        from apps.admin_portal.models import BankConfiguration
        
        config, created = BankConfiguration.objects.get_or_create(bank=bank)
        config.monthly_api_quota = new_quota
        config.save()
    
    @staticmethod
    def update_billing_plan(bank, plan):
        """
        Update billing plan for a bank
        
        Args:
            bank: Bank instance
            plan: Billing plan (free, basic, professional, enterprise)
        """
        from apps.admin_portal.models import BankConfiguration
        
        valid_plans = ['free', 'basic', 'professional', 'enterprise']
        if plan not in valid_plans:
            raise ValueError(f"Invalid plan. Must be one of: {valid_plans}")
        
        config, created = BankConfiguration.objects.get_or_create(bank=bank)
        config.billing_plan = plan
        
        # Set quotas based on plan
        plan_quotas = {
            'free': 10000,
            'basic': 50000,
            'professional': 200000,
            'enterprise': 1000000
        }
        
        config.monthly_api_quota = plan_quotas[plan]
        config.save()
    
    @staticmethod
    def toggle_feature(bank, feature_name, enabled):
        """
        Enable or disable a feature for a bank
        
        Args:
            bank: Bank instance
            feature_name: Feature name (e.g., 'use_satellite_verification')
            enabled: Boolean
        """
        from apps.admin_portal.models import BankConfiguration
        
        config, created = BankConfiguration.objects.get_or_create(bank=bank)
        
        if hasattr(config, feature_name):
            setattr(config, feature_name, enabled)
            config.save()
        else:
            raise ValueError(f"Unknown feature: {feature_name}")
    
    @staticmethod
    def get_api_usage_analytics(bank, days=30):
        """
        Get detailed API usage analytics for a bank
        
        Args:
            bank: Bank instance
            days: Number of days to analyze
            
        Returns:
            dict: API usage analytics
        """
        from apps.admin_portal.models import APIUsageLog
        from django.db.models import Count, Avg
        
        since = timezone.now() - timedelta(days=days)
        
        logs = APIUsageLog.objects.filter(
            bank=bank,
            timestamp__gte=since
        )
        
        # Total requests
        total_requests = logs.count()
        
        # Requests by status
        requests_by_status = logs.values('status_code').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Successful vs failed
        successful = logs.filter(status_code__lt=400).count()
        failed = logs.filter(status_code__gte=400).count()
        
        # Average response time
        avg_response_time = logs.aggregate(
            avg=Avg('response_time')
        )['avg'] or 0.0
        
        # Top endpoints
        top_endpoints = logs.values('endpoint', 'method').annotate(
            count=Count('id'),
            avg_time=Avg('response_time')
        ).order_by('-count')[:10]
        
        # Requests over time (daily)
        requests_by_day = []
        for i in range(days):
            day = timezone.now() - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            count = logs.filter(
                timestamp__gte=day_start,
                timestamp__lt=day_end
            ).count()
            
            requests_by_day.append({
                'date': day_start.date().isoformat(),
                'count': count
            })
        
        return {
            'period_days': days,
            'total_requests': total_requests,
            'successful_requests': successful,
            'failed_requests': failed,
            'success_rate': round((successful / total_requests * 100), 2) if total_requests > 0 else 0,
            'avg_response_time': round(avg_response_time, 2),
            'requests_by_status': list(requests_by_status),
            'top_endpoints': list(top_endpoints),
            'requests_by_day': requests_by_day[::-1]  # Reverse to show oldest first
        }
    
    @staticmethod
    def check_quota_exceeded(bank):
        """
        Check if bank has exceeded API quota
        
        Args:
            bank: Bank instance
            
        Returns:
            tuple: (exceeded: bool, usage: int, quota: int)
        """
        from apps.admin_portal.models import APIUsageLog, BankConfiguration
        
        try:
            config = bank.configuration
        except BankConfiguration.DoesNotExist:
            return False, 0, 0
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        usage = APIUsageLog.objects.filter(
            bank=bank,
            timestamp__gte=thirty_days_ago
        ).count()
        
        exceeded = usage >= config.monthly_api_quota
        
        return exceeded, usage, config.monthly_api_quota
    
    @staticmethod
    def get_all_banks_overview():
        """
        Get overview of all banks in the system
        
        Returns:
            list: List of bank summaries
        """
        from apps.banks.models import Bank
        
        banks = Bank.objects.all()
        
        overview = []
        for bank in banks:
            try:
                config = bank.configuration
                has_config = True
            except:
                has_config = False
            
            stats = BankManager.get_bank_stats(bank)
            
            overview.append({
                'id': bank.id,
                'name': bank.name,
                'email': bank.user.email,
                'created_at': bank.created_at,
                'is_active': bank.is_active,
                'has_configuration': has_config,
                'billing_plan': config.billing_plan if has_config else 'none',
                'total_farmers': stats['farmers']['total'],
                'active_loans': stats['loans']['active'],
                'api_usage': stats['api']['usage_this_month']
            })
        
        return overview
    
    @staticmethod
    def deactivate_bank(bank, reason=''):
        """
        Deactivate a bank
        
        Args:
            bank: Bank instance
            reason: Reason for deactivation
        """
        from apps.admin_portal.models import SystemAlert
        
        bank.is_active = False
        bank.save()
        
        # Create alert
        SystemAlert.objects.create(
            title=f'Bank Deactivated: {bank.name}',
            message=f'Bank {bank.name} has been deactivated. Reason: {reason}',
            severity='warning',
            category='system',
            source='bank_manager',
            metadata={'bank_id': bank.id, 'reason': reason}
        )
    
    @staticmethod
    def activate_bank(bank):
        """
        Activate a bank
        
        Args:
            bank: Bank instance
        """
        bank.is_active = True
        bank.save()