# compliance/services/eudr_generator.py
from django.utils import timezone
from datetime import timedelta
import uuid
from ..models import ExportPassport
from .qr_generator import QRCodeGenerator
from .pdf_generator import PDFGenerator
from .blockchain_anchor import BlockchainAnchor
from .deforestation import DeforestationAnalyzer
import logging

logger = logging.getLogger(__name__)


class EUDRPassportGenerator:
    """Generate EUDR-compliant export passports"""
    
    def __init__(self):
        self.qr_generator = QRCodeGenerator()
        self.pdf_generator = PDFGenerator()
        self.deforestation_analyzer = DeforestationAnalyzer()
    
    def create_passport(
        self,
        farmer,
        farm,
        commodity_type,
        operator_name,
        commodity_code,
        operator_eori=None,
        language='en',
        anchor_blockchain=False,
        blockchain_network='POLYGON'
    ):
        """
        Create a new export passport with full EUDR compliance
        
        Args:
            farmer: Farmer instance
            farm: Farm instance
            commodity_type: Type of commodity
            operator_name: EU operator/trader name
            commodity_code: CN/HS code
            operator_eori: EORI number (optional)
            language: Document language
            anchor_blockchain: Whether to anchor on blockchain
            blockchain_network: Blockchain network to use
        
        Returns:
            ExportPassport instance
        """
        try:
            # Validate farm has GPS coordinates
            if not farm.boundary_points.exists():
                raise ValueError("Farm must have GPS boundary points")
            
            # Get GPS coordinates
            boundary_points = farm.boundary_points.all().order_by('sequence')
            gps_coordinates = [
                {
                    'lat': float(point.latitude),
                    'lng': float(point.longitude)
                }
                for point in boundary_points
            ]
            
            # Calculate centroid
            lats = [p['lat'] for p in gps_coordinates]
            lngs = [p['lng'] for p in gps_coordinates]
            centroid_lat = sum(lats) / len(lats)
            centroid_lng = sum(lngs) / len(lngs)
            
            # Generate DDS reference number
            dds_reference = self._generate_dds_reference()
            
            # Create passport
            passport = ExportPassport.objects.create(
                farmer=farmer,
                farm=farm,
                dds_reference_number=dds_reference,
                operator_name=operator_name,
                operator_eori=operator_eori,
                commodity_type=commodity_type,
                commodity_code=commodity_code,
                gps_coordinates=gps_coordinates,
                centroid_latitude=centroid_lat,
                centroid_longitude=centroid_lng,
                farm_size_hectares=farm.area_hectares,
                plot_area_sqm=farm.area_sqm if hasattr(farm, 'area_sqm') else None,
                language=language,
                deforestation_status='UNDER_REVIEW',
                risk_level='STANDARD',
                valid_until=timezone.now().date() + timedelta(days=365)
            )
            
            # Add initial audit entry
            passport.add_audit_entry(
                action='CREATE',
                user='system',
                details={
                    'method': 'eudr_generator',
                    'operator': operator_name,
                    'commodity': commodity_type
                }
            )
            
            # Perform deforestation check
            logger.info(f"Running deforestation analysis for passport {passport.passport_id}")
            deforestation_check = self.deforestation_analyzer.analyze_farm(
                farm=farm,
                check_type='INITIAL'
            )
            
            # Update passport with deforestation results
            passport.deforestation_status = deforestation_check.result
            if deforestation_check.result == 'VIOLATION':
                passport.risk_level = 'HIGH'
            elif deforestation_check.result == 'WARNING':
                passport.risk_level = 'STANDARD'
            else:
                passport.risk_level = 'LOW'
            
            passport.satellite_analysis_date = deforestation_check.check_date
            passport.save()
            
            # Generate QR code
            logger.info(f"Generating QR code for passport {passport.passport_id}")
            self.qr_generator.create_qr_code(passport, save_to_model=True)
            
            # Generate PDF
            logger.info(f"Generating PDF for passport {passport.passport_id}")
            self.pdf_generator.generate_export_passport(passport, language=language)
            
            # Anchor to blockchain if requested and status is clear
            if anchor_blockchain and passport.deforestation_status == 'CLEAR':
                logger.info(
                    f"Anchoring passport {passport.passport_id} to {blockchain_network}"
                )
                blockchain = BlockchainAnchor(network=blockchain_network)
                blockchain.anchor_to_blockchain(passport)
            
            logger.info(f"Successfully created passport {passport.passport_id}")
            return passport
            
        except Exception as e:
            logger.error(f"Failed to create passport: {str(e)}")
            raise
    
    def _generate_dds_reference(self):
        """Generate unique DDS reference number"""
        # Format: DDS-YYYY-XXXXXXXX
        year = timezone.now().year
        unique_id = str(uuid.uuid4().hex)[:8].upper()
        return f"DDS-{year}-{unique_id}"
    
    def renew_passport(self, existing_passport, extend_months=12):
        """
        Renew an existing passport
        
        Args:
            existing_passport: ExportPassport instance to renew
            extend_months: Number of months to extend validity
        
        Returns:
            New ExportPassport instance
        """
        # Perform fresh deforestation check
        deforestation_check = self.deforestation_analyzer.analyze_farm(
            farm=existing_passport.farm,
            check_type='RENEWAL'
        )
        
        # Only renew if deforestation check is clear or warning
        if deforestation_check.result == 'VIOLATION':
            raise ValueError(
                "Cannot renew passport: Active deforestation violation detected"
            )
        
        # Create new passport (copying data from old one)
        new_passport = ExportPassport.objects.create(
            farmer=existing_passport.farmer,
            farm=existing_passport.farm,
            dds_reference_number=self._generate_dds_reference(),
            operator_name=existing_passport.operator_name,
            operator_eori=existing_passport.operator_eori,
            commodity_type=existing_passport.commodity_type,
            commodity_code=existing_passport.commodity_code,
            gps_coordinates=existing_passport.gps_coordinates,
            centroid_latitude=existing_passport.centroid_latitude,
            centroid_longitude=existing_passport.centroid_longitude,
            farm_size_hectares=existing_passport.farm_size_hectares,
            plot_area_sqm=existing_passport.plot_area_sqm,
            land_ownership_verified=existing_passport.land_ownership_verified,
            land_tenure_type=existing_passport.land_tenure_type,
            land_document_url=existing_passport.land_document_url,
            land_document_type=existing_passport.land_document_type,
            language=existing_passport.language,
            deforestation_status=deforestation_check.result,
            risk_level=existing_passport.risk_level,
            valid_until=timezone.now().date() + timedelta(days=extend_months * 30)
        )
        
        # Add audit entry indicating renewal
        new_passport.add_audit_entry(
            action='CREATE',
            user='system',
            details={
                'method': 'renewal',
                'previous_passport': existing_passport.passport_id,
                'deforestation_check': str(deforestation_check.id)
            }
        )
        
        # Deactivate old passport
        existing_passport.is_active = False
        existing_passport.notes = f"Renewed as {new_passport.passport_id}"
        existing_passport.save()
        
        # Generate QR and PDF for new passport
        self.qr_generator.create_qr_code(new_passport, save_to_model=True)
        self.pdf_generator.generate_export_passport(
            new_passport,
            language=new_passport.language
        )
        
        return new_passport
    
    def bulk_create_passports(
        self,
        farms_data,
        operator_name,
        commodity_type,
        commodity_code,
        operator_eori=None,
        language='en'
    ):
        """
        Create multiple passports in bulk
        
        Args:
            farms_data: List of dicts with 'farmer' and 'farm' instances
            operator_name: EU operator name
            commodity_type: Commodity type
            commodity_code: CN/HS code
            operator_eori: EORI number
            language: Document language
        
        Returns:
            dict: Results summary
        """
        results = {
            'total': len(farms_data),
            'successful': 0,
            'failed': 0,
            'passports': [],
            'errors': []
        }
        
        for data in farms_data:
            try:
                passport = self.create_passport(
                    farmer=data['farmer'],
                    farm=data['farm'],
                    commodity_type=commodity_type,
                    operator_name=operator_name,
                    commodity_code=commodity_code,
                    operator_eori=operator_eori,
                    language=language
                )
                
                results['successful'] += 1
                results['passports'].append({
                    'passport_id': passport.passport_id,
                    'farmer_name': passport.farmer.full_name,
                    'farm_name': passport.farm.farm_name,
                    'status': passport.deforestation_status
                })
                
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'farmer_name': data['farmer'].full_name,
                    'farm_name': data['farm'].farm_name,
                    'error': str(e)
                })
                logger.error(
                    f"Failed to create passport for {data['farm'].farm_name}: {str(e)}"
                )
        
        return results
    
    def verify_passport_validity(self, passport):
        """
        Comprehensive validity check
        
        Args:
            passport: ExportPassport instance
        
        Returns:
            dict: Validation results
        """
        issues = []
        warnings = []
        
        # Check expiry
        if passport.is_expired():
            issues.append("Passport has expired")
        elif passport.days_until_expiry() < 30:
            warnings.append(f"Passport expires in {passport.days_until_expiry()} days")
        
        # Check active status
        if not passport.is_active:
            issues.append("Passport is not active")
        
        # Check deforestation status
        if passport.deforestation_status == 'FLAGGED':
            issues.append("Deforestation violation detected")
        elif passport.deforestation_status == 'UNDER_REVIEW':
            warnings.append("Deforestation status under review")
        
        # Check verification
        if not passport.is_verified:
            warnings.append("Passport not yet verified by authority")
        
        # Check if recent deforestation check exists
        recent_checks = passport.deforestation_checks.filter(
            check_date__gte=timezone.now().date() - timedelta(days=180)
        )
        if not recent_checks.exists():
            warnings.append("No recent deforestation check (last 6 months)")
        
        # Blockchain verification
        if passport.blockchain_hash:
            blockchain = BlockchainAnchor(network=passport.blockchain_network)
            blockchain_result = blockchain.verify_on_blockchain(passport)
            if not blockchain_result.get('verified'):
                issues.append("Blockchain verification failed - data may have been tampered")
        
        is_valid = len(issues) == 0
        
        return {
            'valid': is_valid,
            'passport_id': passport.passport_id,
            'issues': issues,
            'warnings': warnings,
            'status': passport.deforestation_status,
            'risk_level': passport.risk_level,
            'expires': passport.valid_until.isoformat(),
            'days_remaining': passport.days_until_expiry() if not passport.is_expired() else 0
        }