# compliance/services/blockchain_anchor.py
import hashlib
import json
from datetime import datetime
from web3 import Web3
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class BlockchainAnchor:
    """Service to anchor export passport data on blockchain"""
    
    def __init__(self, network='POLYGON'):
        self.network = network
        self.web3 = self._get_web3_provider()
        
    def _get_web3_provider(self):
        """Get Web3 provider based on network"""
        rpc_urls = {
            'ETHEREUM': getattr(settings, 'ETHEREUM_RPC_URL', None),
            'POLYGON': getattr(settings, 'POLYGON_RPC_URL', 'https://polygon-rpc.com'),
            'AVALANCHE': getattr(settings, 'AVALANCHE_RPC_URL', 'https://api.avax.network/ext/bc/C/rpc'),
            'CELO': getattr(settings, 'CELO_RPC_URL', 'https://forno.celo.org'),
        }
        
        rpc_url = rpc_urls.get(self.network)
        if not rpc_url:
            raise ValueError(f"No RPC URL configured for network: {self.network}")
        
        return Web3(Web3.HTTPProvider(rpc_url))
    
    def generate_passport_hash(self, passport):
        """
        Generate SHA-256 hash of passport data
        
        Args:
            passport: ExportPassport instance
        
        Returns:
            str: Hash of passport data
        """
        # Create canonical representation of passport data
        passport_data = {
            'passport_id': passport.passport_id,
            'dds_reference': passport.dds_reference_number,
            'farmer_id': str(passport.farmer.id),
            'farm_id': str(passport.farm.id),
            'commodity_type': passport.commodity_type,
            'gps_coordinates': passport.gps_coordinates,
            'farm_size_hectares': str(passport.farm_size_hectares),
            'deforestation_status': passport.deforestation_status,
            'issued_date': passport.issued_date.isoformat(),
            'valid_until': passport.valid_until.isoformat(),
        }
        
        # Sort keys for consistent hashing
        canonical_json = json.dumps(passport_data, sort_keys=True)
        
        # Generate SHA-256 hash
        hash_object = hashlib.sha256(canonical_json.encode())
        return '0x' + hash_object.hexdigest()
    
    def anchor_to_blockchain(self, passport, private_key=None):
        """
        Anchor passport hash to blockchain
        
        Args:
            passport: ExportPassport instance
            private_key: Private key for signing transaction (optional)
        
        Returns:
            dict: Transaction details
        """
        try:
            # Generate hash
            data_hash = self.generate_passport_hash(passport)
            
            # Get account
            if private_key:
                account = self.web3.eth.account.from_key(private_key)
            else:
                # Use configured account
                private_key = getattr(settings, f'{self.network}_PRIVATE_KEY', None)
                if not private_key:
                    raise ValueError(f"No private key configured for {self.network}")
                account = self.web3.eth.account.from_key(private_key)
            
            # Prepare transaction
            nonce = self.web3.eth.get_transaction_count(account.address)
            
            # Create transaction to store hash
            # We'll use a simple transaction with data field containing our hash
            transaction = {
                'nonce': nonce,
                'to': account.address,  # Send to self
                'value': 0,
                'gas': 21000 + 68 * len(data_hash),  # Base + data cost
                'gasPrice': self.web3.eth.gas_price,
                'data': data_hash.encode().hex(),
                'chainId': self._get_chain_id()
            }
            
            # Sign transaction
            signed_txn = self.web3.eth.account.sign_transaction(
                transaction,
                private_key
            )
            
            # Send transaction
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for receipt (with timeout)
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(
                tx_hash,
                timeout=120
            )
            
            # Update passport
            passport.blockchain_hash = data_hash
            passport.blockchain_network = self.network
            passport.blockchain_tx_hash = '0x' + tx_hash.hex()
            passport.blockchain_timestamp = datetime.now()
            passport.save(update_fields=[
                'blockchain_hash',
                'blockchain_network',
                'blockchain_tx_hash',
                'blockchain_timestamp'
            ])
            
            # Add audit entry
            passport.add_audit_entry(
                action='BLOCKCHAIN_ANCHOR',
                user='system',
                details={
                    'network': self.network,
                    'tx_hash': '0x' + tx_hash.hex(),
                    'block_number': tx_receipt['blockNumber']
                }
            )
            
            return {
                'success': True,
                'hash': data_hash,
                'tx_hash': '0x' + tx_hash.hex(),
                'block_number': tx_receipt['blockNumber'],
                'network': self.network,
                'timestamp': passport.blockchain_timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Blockchain anchoring failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_on_blockchain(self, passport):
        """
        Verify passport data against blockchain
        
        Args:
            passport: ExportPassport instance
        
        Returns:
            dict: Verification result
        """
        try:
            if not passport.blockchain_tx_hash:
                return {
                    'verified': False,
                    'message': 'No blockchain transaction recorded'
                }
            
            # Get transaction
            tx = self.web3.eth.get_transaction(passport.blockchain_tx_hash)
            
            # Extract hash from transaction data
            tx_data = bytes.fromhex(tx['input'][2:]).decode()
            
            # Generate current hash
            current_hash = self.generate_passport_hash(passport)
            
            # Compare
            if tx_data == current_hash:
                return {
                    'verified': True,
                    'message': 'Passport data matches blockchain record',
                    'block_number': tx['blockNumber'],
                    'timestamp': datetime.fromtimestamp(
                        self.web3.eth.get_block(tx['blockNumber'])['timestamp']
                    ).isoformat()
                }
            else:
                return {
                    'verified': False,
                    'message': 'Passport data has been modified since blockchain anchoring',
                    'expected_hash': current_hash,
                    'blockchain_hash': tx_data
                }
                
        except Exception as e:
            logger.error(f"Blockchain verification failed: {str(e)}")
            return {
                'verified': False,
                'error': str(e)
            }
    
    def _get_chain_id(self):
        """Get chain ID for network"""
        chain_ids = {
            'ETHEREUM': 1,
            'POLYGON': 137,
            'AVALANCHE': 43114,
            'CELO': 42220,
        }
        return chain_ids.get(self.network, 1)
    
    def get_transaction_details(self, tx_hash):
        """
        Get details of a blockchain transaction
        
        Args:
            tx_hash: Transaction hash
        
        Returns:
            dict: Transaction details
        """
        try:
            tx = self.web3.eth.get_transaction(tx_hash)
            receipt = self.web3.eth.get_transaction_receipt(tx_hash)
            block = self.web3.eth.get_block(tx['blockNumber'])
            
            return {
                'hash': tx_hash,
                'from': tx['from'],
                'to': tx['to'],
                'value': self.web3.from_wei(tx['value'], 'ether'),
                'gas_used': receipt['gasUsed'],
                'block_number': tx['blockNumber'],
                'timestamp': datetime.fromtimestamp(block['timestamp']).isoformat(),
                'status': 'success' if receipt['status'] == 1 else 'failed',
                'network': self.network
            }
        except Exception as e:
            logger.error(f"Failed to get transaction details: {str(e)}")
            return {
                'error': str(e)
            }
    
    def batch_anchor(self, passports, private_key=None):
        """
        Anchor multiple passports to blockchain
        
        Args:
            passports: List of ExportPassport instances
            private_key: Private key for signing transactions
        
        Returns:
            list: Results for each passport
        """
        results = []
        
        for passport in passports:
            result = self.anchor_to_blockchain(passport, private_key)
            results.append({
                'passport_id': passport.passport_id,
                **result
            })
        
        return results


class BlockchainVerifier:
    """Verify blockchain-anchored data"""
    
    @staticmethod
    def verify_hash(original_data, stored_hash):
        """
        Verify data against stored hash
        
        Args:
            original_data: Original data dict
            stored_hash: Stored hash to verify against
        
        Returns:
            bool: True if hash matches
        """
        canonical_json = json.dumps(original_data, sort_keys=True)
        calculated_hash = '0x' + hashlib.sha256(canonical_json.encode()).hexdigest()
        return calculated_hash == stored_hash
    
    @staticmethod
    def create_merkle_root(hashes):
        """
        Create Merkle root from list of hashes (for batch verification)
        
        Args:
            hashes: List of hash strings
        
        Returns:
            str: Merkle root hash
        """
        if not hashes:
            return None
        
        if len(hashes) == 1:
            return hashes[0]
        
        # Ensure even number of hashes
        if len(hashes) % 2 != 0:
            hashes.append(hashes[-1])
        
        # Create next level
        next_level = []
        for i in range(0, len(hashes), 2):
            combined = hashes[i] + hashes[i + 1]
            next_hash = '0x' + hashlib.sha256(combined.encode()).hexdigest()
            next_level.append(next_hash)
        
        # Recursively build tree
        return BlockchainVerifier.create_merkle_root(next_level)