# compliance/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(name='compliance.periodic_deforestation_checks')
def run_periodic_deforestation_checks():
    """
    Run periodic deforestation checks on all active farms with passports
    """
    from .models import ExportPassport
    from .services import DeforestationAnalyzer
    
    logger.info("Starting periodic deforestation checks")
    
    # Get active passports that haven't been checked in last 30 days
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    
    passports = ExportPassport.objects.filter(
        is_active=True,
        satellite_analysis_date__lt=thirty_days_ago
    ).select_related('farm')
    
    analyzer = DeforestationAnalyzer()
    results = {
        'total': 0,
        'successful': 0,
        'failed': 0
    }
    
    for passport in passports:
        try:
            analyzer.analyze_farm(
                farm=passport.farm,
                check_type='PERIODIC'
            )
            results['successful'] += 1
        except Exception as e:
            logger.error(
                f"Failed to check farm {passport.farm.id}: {str(e)}"
            )
            results['failed'] += 1
        
        results['total'] += 1
    
    logger.info(f"Periodic checks completed: {results}")
    return results


@shared_task(name='compliance.generate_passport_batch')
def generate_passport_batch(farm_ids, operator_name, commodity_type, commodity_code):
    """
    Generate passports for multiple farms in background
    """
    from .services import EUDRPassportGenerator
    from apps.farms.models import Farm
    
    logger.info(f"Starting batch passport generation for {len(farm_ids)} farms")
    
    farms = Farm.objects.filter(id__in=farm_ids).select_related('farmer')
    farms_data = [
        {'farmer': farm.farmer, 'farm': farm}
        for farm in farms
    ]
    
    generator = EUDRPassportGenerator()
    results = generator.bulk_create_passports(
        farms_data=farms_data,
        operator_name=operator_name,
        commodity_type=commodity_type,
        commodity_code=commodity_code
    )
    
    logger.info(f"Batch generation completed: {results['successful']} successful, {results['failed']} failed")
    return results


@shared_task(name='compliance.regenerate_passport_documents')
def regenerate_passport_documents(passport_id):
    """
    Regenerate QR code and PDF for a passport
    """
    from .models import ExportPassport
    from .services import QRCodeGenerator, PDFGenerator
    
    try:
        passport = ExportPassport.objects.get(passport_id=passport_id)
        
        # Regenerate QR code
        qr_generator = QRCodeGenerator()
        qr_generator.create_qr_code(passport, save_to_model=True)
        
        # Regenerate PDF
        pdf_generator = PDFGenerator()
        pdf_generator.generate_export_passport(passport, language=passport.language)
        
        logger.info(f"Successfully regenerated documents for passport {passport_id}")
        return {'success': True, 'passport_id': passport_id}
        
    except Exception as e:
        logger.error(f"Failed to regenerate documents for {passport_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='compliance.anchor_passports_to_blockchain')
def anchor_passports_to_blockchain(passport_ids, network='POLYGON'):
    """
    Anchor multiple passports to blockchain
    """
    from .models import ExportPassport
    from .services import BlockchainAnchor
    
    logger.info(f"Starting blockchain anchoring for {len(passport_ids)} passports")
    
    passports = ExportPassport.objects.filter(
        passport_id__in=passport_ids,
        deforestation_status='CLEAR',
        blockchain_hash__isnull=True
    )
    
    blockchain = BlockchainAnchor(network=network)
    results = blockchain.batch_anchor(passports)
    
    successful = sum(1 for r in results if r.get('success'))
    logger.info(f"Blockchain anchoring completed: {successful}/{len(results)} successful")
    
    return results


@shared_task(name='compliance.send_expiry_notifications')
def send_expiry_notifications():
    """
    Send notifications for passports expiring soon
    """
    from .models import ExportPassport
    
    logger.info("Checking for expiring passports")
    
    # Get passports expiring in 30 days
    thirty_days = timezone.now().date() + timedelta(days=30)
    seven_days = timezone.now().date() + timedelta(days=7)
    
    expiring_soon = ExportPassport.objects.filter(
        is_active=True,
        valid_until__lte=thirty_days,
        valid_until__gte=timezone.now().date()
    ).select_related('farmer', 'farm')
    
    notifications_sent = 0
    
    for passport in expiring_soon:
        days_remaining = (passport.valid_until - timezone.now().date()).days
        
        # Send notification (integrate with notification service)
        try:
            # TODO: Integrate with notifications app
            logger.info(
                f"Passport {passport.passport_id} expires in {days_remaining} days"
            )
            notifications_sent += 1
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
    
    logger.info(f"Sent {notifications_sent} expiry notifications")
    return {'notifications_sent': notifications_sent}


@shared_task(name='compliance.cleanup_expired_cache')
def cleanup_expired_cache():
    """
    Clean up expired translation cache entries
    """
    from .services import TranslationService
    
    logger.info("Cleaning up expired translation cache")
    
    translation_service = TranslationService()
    deleted_count = translation_service.clear_expired_cache()
    
    logger.info(f"Cleaned up {deleted_count} expired cache entries")
    return {'deleted_count': deleted_count}


@shared_task(name='compliance.generate_compliance_report')
def generate_compliance_report(start_date, end_date, email_to=None):
    """
    Generate comprehensive compliance report
    """
    from .models import ExportPassport, DeforestationCheck
    from django.db.models import Count, Avg
    
    logger.info(f"Generating compliance report for {start_date} to {end_date}")
    
    # Passport statistics
    passports = ExportPassport.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    passport_stats = {
        'total': passports.count(),
        'by_status': list(passports.values('deforestation_status').annotate(count=Count('id'))),
        'by_risk': list(passports.values('risk_level').annotate(count=Count('id'))),
        'verified': passports.filter(is_verified=True).count(),
        'blockchain_anchored': passports.filter(blockchain_hash__isnull=False).count()
    }
    
    # Deforestation check statistics
    checks = DeforestationCheck.objects.filter(
        check_date__gte=start_date,
        check_date__lte=end_date,
        status='COMPLETED'
    )
    
    check_stats = {
        'total': checks.count(),
        'by_result': list(checks.values('result').annotate(count=Count('id'))),
        'avg_risk_score': checks.aggregate(Avg('risk_score'))['risk_score__avg'],
        'violations': checks.filter(result='VIOLATION').count()
    }
    
    report = {
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat()
        },
        'passports': passport_stats,
        'deforestation_checks': check_stats,
        'generated_at': timezone.now().isoformat()
    }
    
    # TODO: Send email if email_to is provided
    
    logger.info("Compliance report generated successfully")
    return report


@shared_task(name='compliance.verify_blockchain_integrity')
def verify_blockchain_integrity():
    """
    Verify integrity of blockchain-anchored passports
    """
    from .models import ExportPassport
    from .services import BlockchainAnchor
    
    logger.info("Starting blockchain integrity verification")
    
    passports = ExportPassport.objects.filter(
        blockchain_hash__isnull=False,
        is_active=True
    )
    
    results = {
        'total': 0,
        'verified': 0,
        'tampered': 0,
        'errors': 0
    }
    
    for passport in passports:
        try:
            blockchain = BlockchainAnchor(network=passport.blockchain_network)
            verification = blockchain.verify_on_blockchain(passport)
            
            if verification.get('verified'):
                results['verified'] += 1
            else:
                results['tampered'] += 1
                logger.warning(
                    f"Passport {passport.passport_id} failed blockchain verification"
                )
        except Exception as e:
            logger.error(f"Error verifying {passport.passport_id}: {str(e)}")
            results['errors'] += 1
        
        results['total'] += 1
    
    logger.info(f"Blockchain verification completed: {results}")
    return results


@shared_task(name='compliance.auto_renew_expiring_passports')
def auto_renew_expiring_passports(days_before_expiry=30):
    """
    Automatically renew passports that are expiring soon (if configured)
    """
    from .models import ExportPassport
    from .services import EUDRPassportGenerator
    
    logger.info(f"Checking for passports expiring within {days_before_expiry} days")
    
    expiry_date = timezone.now().date() + timedelta(days=days_before_expiry)
    
    expiring_passports = ExportPassport.objects.filter(
        is_active=True,
        valid_until__lte=expiry_date,
        valid_until__gte=timezone.now().date(),
        deforestation_status__in=['CLEAR', 'REMEDIATED']
    )
    
    generator = EUDRPassportGenerator()
    results = {
        'total': 0,
        'renewed': 0,
        'failed': 0
    }
    
    for passport in expiring_passports:
        try:
            generator.renew_passport(passport)
            results['renewed'] += 1
            logger.info(f"Successfully renewed passport {passport.passport_id}")
        except Exception as e:
            logger.error(f"Failed to renew {passport.passport_id}: {str(e)}")
            results['failed'] += 1
        
        results['total'] += 1
    
    logger.info(f"Auto-renewal completed: {results}")
    return results