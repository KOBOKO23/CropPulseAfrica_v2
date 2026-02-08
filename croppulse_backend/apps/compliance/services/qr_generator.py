# compliance/services/qr_generator.py
import qrcode
from io import BytesIO
from django.core.files import File
import json
import base64
from datetime import datetime


class QRCodeGenerator:
    """Generate QR codes for export passports"""
    
    def __init__(self):
        self.version = 1
        self.box_size = 10
        self.border = 4
    
    def generate_qr_data(self, passport):
        """
        Generate data to encode in QR code
        
        Args:
            passport: ExportPassport instance
        
        Returns:
            dict: Data to encode
        """
        qr_data = {
            'passport_id': passport.passport_id,
            'dds_ref': passport.dds_reference_number,
            'farmer_id': str(passport.farmer.id),
            'farmer_name': passport.farmer.full_name,
            'farm_id': str(passport.farm.id),
            'commodity': passport.commodity_type,
            'coordinates': {
                'lat': float(passport.centroid_latitude),
                'lng': float(passport.centroid_longitude)
            },
            'issued': passport.issued_date.isoformat(),
            'expires': passport.valid_until.isoformat(),
            'status': passport.deforestation_status,
            'verified': passport.is_verified,
            'blockchain': passport.blockchain_hash if passport.blockchain_hash else None,
            'verification_url': f"https://verify.croppulse.com/passport/{passport.passport_id}"
        }
        
        return qr_data
    
    def create_qr_code(self, passport, save_to_model=True):
        """
        Generate QR code for export passport
        
        Args:
            passport: ExportPassport instance
            save_to_model: Whether to save QR code to passport model
        
        Returns:
            File object containing QR code image
        """
        # Generate QR data
        qr_data = self.generate_qr_data(passport)
        
        # Store QR data in passport
        if save_to_model:
            passport.qr_data = qr_data
        
        # Convert to JSON string
        qr_string = json.dumps(qr_data)
        
        # Create QR code
        qr = qrcode.QRCode(
            version=self.version,
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
            box_size=self.box_size,
            border=self.border,
        )
        
        qr.add_data(qr_string)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to BytesIO
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Create Django File
        filename = f'qr_{passport.passport_id}.png'
        qr_file = File(buffer, name=filename)
        
        # Save to passport if requested
        if save_to_model:
            passport.qr_code.save(filename, qr_file, save=True)
        
        return qr_file
    
    def verify_qr_code(self, qr_data_string):
        """
        Verify QR code data
        
        Args:
            qr_data_string: JSON string from QR code
        
        Returns:
            dict: Verification result
        """
        try:
            qr_data = json.loads(qr_data_string)
            
            # Get passport
            from ..models import ExportPassport
            passport = ExportPassport.objects.get(
                passport_id=qr_data['passport_id']
            )
            
            # Verify data integrity
            current_hash = passport.blockchain_hash
            qr_hash = qr_data.get('blockchain')
            
            is_valid = True
            issues = []
            
            # Check expiry
            if passport.is_expired():
                is_valid = False
                issues.append("Passport has expired")
            
            # Check if active
            if not passport.is_active:
                is_valid = False
                issues.append("Passport is not active")
            
            # Check blockchain hash if exists
            if current_hash and qr_hash and current_hash != qr_hash:
                is_valid = False
                issues.append("Blockchain hash mismatch - data may have been tampered")
            
            # Check deforestation status
            if passport.deforestation_status == 'FLAGGED':
                is_valid = False
                issues.append("Deforestation detected for this farm")
            
            return {
                'valid': is_valid,
                'passport': passport,
                'issues': issues,
                'verification_date': datetime.now().isoformat(),
                'qr_data': qr_data
            }
            
        except ExportPassport.DoesNotExist:
            return {
                'valid': False,
                'passport': None,
                'issues': ['Passport not found'],
                'verification_date': datetime.now().isoformat()
            }
        except json.JSONDecodeError:
            return {
                'valid': False,
                'passport': None,
                'issues': ['Invalid QR code format'],
                'verification_date': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'valid': False,
                'passport': None,
                'issues': [f'Verification error: {str(e)}'],
                'verification_date': datetime.now().isoformat()
            }
    
    def generate_batch_qr_codes(self, passports):
        """
        Generate QR codes for multiple passports
        
        Args:
            passports: QuerySet or list of ExportPassport instances
        
        Returns:
            list: Results for each passport
        """
        results = []
        
        for passport in passports:
            try:
                self.create_qr_code(passport, save_to_model=True)
                results.append({
                    'passport_id': passport.passport_id,
                    'success': True,
                    'message': 'QR code generated successfully'
                })
            except Exception as e:
                results.append({
                    'passport_id': passport.passport_id,
                    'success': False,
                    'message': str(e)
                })
        
        return results