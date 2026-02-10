# SMS service using Africa's Talking

import os
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class SMSService:
    """SMS service for farmer alerts"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'AFRICAS_TALKING_API_KEY', None)
        self.username = getattr(settings, 'AFRICAS_TALKING_USERNAME', 'sandbox')
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            try:
                import africastalking
                africastalking.initialize(self.username, self.api_key)
                self.sms = africastalking.SMS
            except ImportError:
                logger.warning("africastalking package not installed")
                self.enabled = False
    
    def send_alert(self, phone_number, message):
        """Send SMS alert to farmer"""
        if not self.enabled:
            logger.info(f"SMS (disabled): {phone_number} - {message}")
            return {'status': 'disabled', 'message': message}
        
        try:
            response = self.sms.send(message, [phone_number])
            logger.info(f"SMS sent to {phone_number}: {response}")
            return {'status': 'sent', 'response': response}
        except Exception as e:
            logger.error(f"SMS failed for {phone_number}: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    def broadcast_alert(self, phone_numbers, message):
        """Broadcast alert to multiple farmers"""
        if not self.enabled:
            logger.info(f"SMS broadcast (disabled) to {len(phone_numbers)} farmers")
            return {'status': 'disabled', 'count': len(phone_numbers)}
        
        try:
            response = self.sms.send(message, phone_numbers)
            logger.info(f"Broadcast sent to {len(phone_numbers)} farmers")
            return {'status': 'sent', 'response': response}
        except Exception as e:
            logger.error(f"Broadcast failed: {e}")
            return {'status': 'failed', 'error': str(e)}
