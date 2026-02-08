# compliance/services/audit_logger.py
from django.utils import timezone
from ..models import AuditLog
import logging

logger = logging.getLogger(__name__)


class AuditLogger:
    """Comprehensive audit logging service for compliance"""
    
    @staticmethod
    def log_action(
        entity_type,
        entity_id,
        action,
        user_id,
        user_name,
        changes=None,
        reason=None,
        user_role=None,
        ip_address=None,
        user_agent=None
    ):
        """
        Log an audit event
        
        Args:
            entity_type: Type of entity (EXPORT_PASSPORT, DEFORESTATION_CHECK, etc.)
            entity_id: UUID of the entity
            action: Action performed (CREATE, UPDATE, DELETE, etc.)
            user_id: ID of user performing action
            user_name: Name of user
            changes: Dict of before/after values for updates
            reason: Reason for the action
            user_role: Role of user
            ip_address: IP address of request
            user_agent: User agent string
        
        Returns:
            AuditLog instance
        """
        try:
            audit_log = AuditLog.objects.create(
                entity_type=entity_type,
                entity_id=entity_id,
                user_id=str(user_id),
                user_name=user_name,
                user_role=user_role,
                action=action,
                changes=changes or {},
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            logger.info(
                f"Audit log created: {action} on {entity_type} {entity_id} by {user_name}"
            )
            
            return audit_log
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}")
            # Don't raise - audit logging should not break the main flow
            return None
    
    @staticmethod
    def log_passport_create(passport, user_id, user_name, request=None):
        """Log passport creation"""
        return AuditLogger.log_action(
            entity_type='EXPORT_PASSPORT',
            entity_id=passport.id,
            action='CREATE',
            user_id=user_id,
            user_name=user_name,
            changes={
                'created': {
                    'passport_id': passport.passport_id,
                    'dds_reference': passport.dds_reference_number,
                    'farmer': passport.farmer.full_name,
                    'farm': passport.farm.farm_name
                }
            },
            ip_address=AuditLogger._get_client_ip(request) if request else None,
            user_agent=AuditLogger._get_user_agent(request) if request else None
        )
    
    @staticmethod
    def log_passport_update(passport, user_id, user_name, old_values, new_values, request=None):
        """Log passport update"""
        changes = {
            'before': old_values,
            'after': new_values
        }
        
        return AuditLogger.log_action(
            entity_type='EXPORT_PASSPORT',
            entity_id=passport.id,
            action='UPDATE',
            user_id=user_id,
            user_name=user_name,
            changes=changes,
            ip_address=AuditLogger._get_client_ip(request) if request else None,
            user_agent=AuditLogger._get_user_agent(request) if request else None
        )
    
    @staticmethod
    def log_passport_verify(passport, user_id, user_name, verification_result, request=None):
        """Log passport verification"""
        return AuditLogger.log_action(
            entity_type='EXPORT_PASSPORT',
            entity_id=passport.id,
            action='VERIFY',
            user_id=user_id,
            user_name=user_name,
            changes={
                'verification': {
                    'verified': passport.is_verified,
                    'verified_by': passport.verified_by,
                    'result': verification_result
                }
            },
            ip_address=AuditLogger._get_client_ip(request) if request else None,
            user_agent=AuditLogger._get_user_agent(request) if request else None
        )
    
    @staticmethod
    def log_blockchain_anchor(passport, user_id, user_name, blockchain_result, request=None):
        """Log blockchain anchoring"""
        return AuditLogger.log_action(
            entity_type='EXPORT_PASSPORT',
            entity_id=passport.id,
            action='BLOCKCHAIN_ANCHOR',
            user_id=user_id,
            user_name=user_name,
            changes={
                'blockchain': {
                    'network': passport.blockchain_network,
                    'hash': passport.blockchain_hash,
                    'tx_hash': passport.blockchain_tx_hash,
                    'result': blockchain_result
                }
            },
            ip_address=AuditLogger._get_client_ip(request) if request else None,
            user_agent=AuditLogger._get_user_agent(request) if request else None
        )
    
    @staticmethod
    def log_deforestation_check(check, user_id, user_name, request=None):
        """Log deforestation check"""
        return AuditLogger.log_action(
            entity_type='DEFORESTATION_CHECK',
            entity_id=check.id,
            action='CREATE',
            user_id=user_id,
            user_name=user_name,
            changes={
                'analysis': {
                    'farm': check.farm.farm_name,
                    'result': check.result,
                    'risk_score': check.risk_score,
                    'deforestation_detected': check.deforestation_detected,
                    'forest_change': float(check.change_in_forest_cover)
                }
            },
            ip_address=AuditLogger._get_client_ip(request) if request else None,
            user_agent=AuditLogger._get_user_agent(request) if request else None
        )
    
    @staticmethod
    def log_document_upload(document, user_id, user_name, request=None):
        """Log compliance document upload"""
        return AuditLogger.log_action(
            entity_type='COMPLIANCE_DOCUMENT',
            entity_id=document.id,
            action='CREATE',
            user_id=user_id,
            user_name=user_name,
            changes={
                'document': {
                    'type': document.document_type,
                    'name': document.document_name,
                    'passport_id': document.export_passport.passport_id,
                    'size': document.file_size_bytes
                }
            },
            ip_address=AuditLogger._get_client_ip(request) if request else None,
            user_agent=AuditLogger._get_user_agent(request) if request else None
        )
    
    @staticmethod
    def get_entity_audit_trail(entity_type, entity_id, limit=None):
        """
        Get audit trail for a specific entity
        
        Args:
            entity_type: Type of entity
            entity_id: UUID of entity
            limit: Maximum number of records to return
        
        Returns:
            QuerySet of AuditLog entries
        """
        logs = AuditLog.objects.filter(
            entity_type=entity_type,
            entity_id=entity_id
        ).order_by('-timestamp')
        
        if limit:
            logs = logs[:limit]
        
        return logs
    
    @staticmethod
    def get_user_audit_trail(user_id, start_date=None, end_date=None, limit=None):
        """
        Get audit trail for a specific user
        
        Args:
            user_id: User ID
            start_date: Start date for filtering
            end_date: End date for filtering
            limit: Maximum number of records
        
        Returns:
            QuerySet of AuditLog entries
        """
        logs = AuditLog.objects.filter(user_id=str(user_id))
        
        if start_date:
            logs = logs.filter(timestamp__gte=start_date)
        
        if end_date:
            logs = logs.filter(timestamp__lte=end_date)
        
        logs = logs.order_by('-timestamp')
        
        if limit:
            logs = logs[:limit]
        
        return logs
    
    @staticmethod
    def get_recent_actions(days=7, action_type=None, limit=100):
        """
        Get recent audit actions
        
        Args:
            days: Number of days to look back
            action_type: Filter by action type
            limit: Maximum number of records
        
        Returns:
            QuerySet of AuditLog entries
        """
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        logs = AuditLog.objects.filter(timestamp__gte=cutoff_date)
        
        if action_type:
            logs = logs.filter(action=action_type)
        
        logs = logs.order_by('-timestamp')[:limit]
        
        return logs
    
    @staticmethod
    def get_audit_summary(start_date, end_date):
        """
        Get summary of audit activities
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            dict: Summary statistics
        """
        from django.db.models import Count
        
        logs = AuditLog.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date
        )
        
        total_actions = logs.count()
        
        # Count by action type
        by_action = logs.values('action').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Count by entity type
        by_entity = logs.values('entity_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Count by user
        by_user = logs.values('user_name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_actions': total_actions,
            'by_action': list(by_action),
            'by_entity': list(by_entity),
            'top_users': list(by_user)
        }
    
    @staticmethod
    def _get_client_ip(request):
        """Extract client IP from request"""
        if not request:
            return None
        
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @staticmethod
    def _get_user_agent(request):
        """Extract user agent from request"""
        if not request:
            return None
        
        return request.META.get('HTTP_USER_AGENT', '')