# Celo Blockchain Integration

from web3 import Web3
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class CeloBlockchain:
    """Blockchain service for immutable action logging"""
    
    def __init__(self):
        self.enabled = getattr(settings, 'CELO_ENABLED', False)
        if self.enabled:
            rpc_url = getattr(settings, 'CELO_RPC_URL', 'https://alfajores-forno.celo-testnet.org')
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
            self.account = getattr(settings, 'CELO_ACCOUNT', None)
            self.private_key = getattr(settings, 'CELO_PRIVATE_KEY', None)
    
    def log_action(self, farmer_id, action_type, description, timestamp):
        """Log farmer action to blockchain"""
        if not self.enabled:
            logger.info(f"Blockchain (disabled): {farmer_id} - {action_type}")
            return {'status': 'disabled', 'hash': f'mock_{farmer_id}_{timestamp}'}
        
        try:
            # Create transaction data
            data = f"{farmer_id}|{action_type}|{description}|{timestamp}"
            
            # Send transaction
            tx = {
                'from': self.account,
                'to': self.account,  # Self-transaction for data storage
                'value': 0,
                'gas': 21000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account),
                'data': self.w3.to_hex(text=data)
            }
            
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(f"Blockchain logged: {tx_hash.hex()}")
            return {'status': 'success', 'hash': tx_hash.hex()}
            
        except Exception as e:
            logger.error(f"Blockchain error: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def verify_action(self, tx_hash):
        """Verify action exists on blockchain"""
        if not self.enabled:
            return {'status': 'disabled', 'verified': True}
        
        try:
            tx = self.w3.eth.get_transaction(tx_hash)
            return {'status': 'verified', 'data': tx}
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return {'status': 'error', 'error': str(e)}
