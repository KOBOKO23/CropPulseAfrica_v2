# compliance/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count
from datetime import timedelta
from .models import AuditLog

from .models import (
    ExportPassport,
    DeforestationCheck,
    ComplianceDocument,
)
from .serializers import (
    ExportPassportSerializer,
    ExportPassportListSerializer,
    DeforestationCheckSerializer,
    ComplianceDocumentSerializer,
    AuditLogSerializer,
    PassportVerificationSerializer,
    BulkPassportCreateSerializer,
    DeforestationReportSerializer,
    BlockchainAnchorSerializer,
    TranslationRequestSerializer
)
from .services import (
    EUDRPassportGenerator,
    QRCodeGenerator,
    PDFGenerator,
    BlockchainAnchor,
    DeforestationAnalyzer,
    AuditLogger,
    TranslationService
)
from core.permissions import IsTenantUser
from core.pagination import StandardResultsSetPagination
import logging

logger = logging.getLogger(__name__)


class ExportPassportViewSet(viewsets.ModelViewSet):
    """ViewSet for managing export passports"""
    
    serializer_class = ExportPassportSerializer
    permission_classes = [IsAuthenticated, IsTenantUser]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Get passports for current tenant"""
        queryset = ExportPassport.objects.select_related(
            'farmer',
            'farm'
        ).prefetch_related(
            'documents',
            'deforestation_checks'
        )
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(deforestation_status=status_filter)
        
        # Filter by risk level
        risk_filter = self.request.query_params.get('risk_level')
        if risk_filter:
            queryset = queryset.filter(risk_level=risk_filter)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by expiring soon
        expiring_days = self.request.query_params.get('expiring_within_days')
        if expiring_days:
            expiry_date = timezone.now().date() + timedelta(days=int(expiring_days))
            queryset = queryset.filter(
                valid_until__lte=expiry_date,
                valid_until__gte=timezone.now().date()
            )
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(passport_id__icontains=search) |
                Q(dds_reference_number__icontains=search) |
                Q(farmer__full_name__icontains=search) |
                Q(farm__farm_name__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        """Use list serializer for list action"""
        if self.action == 'list':
            return ExportPassportListSerializer
        return ExportPassportSerializer
    
    def perform_create(self, serializer):
        """Create passport and log audit"""
        passport = serializer.save()
        
        # Log creation
        AuditLogger.log_passport_create(
            passport=passport,
            user_id=self.request.user.id,
            user_name=self.request.user.get_full_name(),
            request=self.request
        )
    
    def perform_update(self, serializer):
        """Update passport and log audit"""
        old_data = {
            field: getattr(serializer.instance, field)
            for field in serializer.validated_data.keys()
        }
        
        passport = serializer.save()
        
        # Log update
        AuditLogger.log_passport_update(
            passport=passport,
            user_id=self.request.user.id,
            user_name=self.request.user.get_full_name(),
            old_values=old_data,
            new_values=serializer.validated_data,
            request=self.request
        )
    
    @action(detail=False, methods=['post'])
    def create_full_passport(self, request):
        """
        Create complete passport with QR, PDF, and optional blockchain
        """
        try:
            # Get required data
            farmer_id = request.data.get('farmer_id')
            farm_id = request.data.get('farm_id')
            commodity_type = request.data.get('commodity_type')
            operator_name = request.data.get('operator_name')
            commodity_code = request.data.get('commodity_code')
            operator_eori = request.data.get('operator_eori')
            language = request.data.get('language', 'en')
            anchor_blockchain = request.data.get('anchor_blockchain', False)
            blockchain_network = request.data.get('blockchain_network', 'POLYGON')
            
            # Validate required fields
            if not all([farmer_id, farm_id, commodity_type, operator_name, commodity_code]):
                return Response(
                    {'error': 'Missing required fields'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get farmer and farm
            from apps.farmers.models import Farmer
            from apps.farms.models import Farm
            
            farmer = get_object_or_404(Farmer, id=farmer_id)
            farm = get_object_or_404(Farm, id=farm_id)
            
            # Create passport
            generator = EUDRPassportGenerator()
            passport = generator.create_passport(
                farmer=farmer,
                farm=farm,
                commodity_type=commodity_type,
                operator_name=operator_name,
                commodity_code=commodity_code,
                operator_eori=operator_eori,
                language=language,
                anchor_blockchain=anchor_blockchain,
                blockchain_network=blockchain_network
            )
            
            # Log creation
            AuditLogger.log_passport_create(
                passport=passport,
                user_id=request.user.id,
                user_name=request.user.get_full_name(),
                request=request
            )
            
            serializer = self.get_serializer(passport)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Failed to create full passport: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple passports in bulk"""
        serializer = BulkPassportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            from apps.farms.models import Farm
            
            farms = Farm.objects.filter(
                id__in=serializer.validated_data['farm_ids']
            ).select_related('farmer')
            
            farms_data = [
                {'farmer': farm.farmer, 'farm': farm}
                for farm in farms
            ]
            
            generator = EUDRPassportGenerator()
            results = generator.bulk_create_passports(
                farms_data=farms_data,
                operator_name=serializer.validated_data['operator_name'],
                commodity_type=serializer.validated_data['commodity_type'],
                commodity_code=request.data.get('commodity_code', 'N/A'),
                operator_eori=serializer.validated_data.get('operator_eori'),
                language=serializer.validated_data.get('language', 'en')
            )
            
            return Response(results, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Bulk passport creation failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify a passport"""
        passport = self.get_object()
        
        passport.is_verified = True
        passport.verified_by = request.user.get_full_name()
        passport.verified_date = timezone.now()
        passport.save()
        
        # Add audit entry
        passport.add_audit_entry(
            action='VERIFY',
            user=request.user.get_full_name(),
            details={'verified_date': timezone.now().isoformat()}
        )
        
        # Log audit
        AuditLogger.log_passport_verify(
            passport=passport,
            user_id=request.user.id,
            user_name=request.user.get_full_name(),
            verification_result='verified',
            request=request
        )
        
        serializer = self.get_serializer(passport)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def renew(self, request, pk=None):
        """Renew an expired or expiring passport"""
        passport = self.get_object()
        
        try:
            generator = EUDRPassportGenerator()
            new_passport = generator.renew_passport(
                existing_passport=passport,
                extend_months=request.data.get('extend_months', 12)
            )
            
            serializer = self.get_serializer(new_passport)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def anchor_blockchain(self, request, pk=None):
        """Anchor passport to blockchain"""
        passport = self.get_object()
        
        serializer = BlockchainAnchorSerializer(data={
            'passport_id': passport.passport_id,
            'network': request.data.get('network', 'POLYGON')
        })
        serializer.is_valid(raise_exception=True)
        
        try:
            blockchain = BlockchainAnchor(
                network=serializer.validated_data['network']
            )
            result = blockchain.anchor_to_blockchain(passport)
            
            # Log audit
            AuditLogger.log_blockchain_anchor(
                passport=passport,
                user_id=request.user.id,
                user_name=request.user.get_full_name(),
                blockchain_result=result,
                request=request
            )
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Blockchain anchoring failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """Download passport PDF"""
        passport = self.get_object()
        
        if not passport.pdf_document:
            # Generate PDF if not exists
            generator = PDFGenerator()
            generator.generate_export_passport(passport, language=passport.language)
        
        from django.http import FileResponse
        return FileResponse(
            passport.pdf_document.open('rb'),
            content_type='application/pdf',
            as_attachment=True,
            filename=f'passport_{passport.passport_id}.pdf'
        )
    
    @action(detail=True, methods=['get'])
    def qr_code(self, request, pk=None):
        """Get QR code image"""
        passport = self.get_object()
        
        if not passport.qr_code:
            # Generate QR code if not exists
            generator = QRCodeGenerator()
            generator.create_qr_code(passport, save_to_model=True)
        
        from django.http import FileResponse
        return FileResponse(
            passport.qr_code.open('rb'),
            content_type='image/png',
            as_attachment=True,
            filename=f'qr_{passport.passport_id}.png'
        )
    
    @action(detail=True, methods=['post'])
    def translate(self, request, pk=None):
        """Translate passport to another language"""
        passport = self.get_object()
        
        serializer = TranslationRequestSerializer(data={
            'passport_id': passport.passport_id,
            'target_language': request.data.get('target_language')
        })
        serializer.is_valid(raise_exception=True)
        
        target_language = serializer.validated_data['target_language']
        
        # Update passport language
        passport.language = target_language
        passport.save()
        
        # Regenerate PDF in new language
        generator = PDFGenerator()
        generator.generate_export_passport(passport, language=target_language)
        
        return Response({
            'message': f'Passport translated to {target_language}',
            'pdf_url': request.build_absolute_uri(passport.pdf_document.url)
        })
    
    @action(detail=True, methods=['get'])
    def audit_trail(self, request, pk=None):
        """Get audit trail for passport"""
        passport = self.get_object()
        
        logs = AuditLogger.get_entity_audit_trail(
            entity_type='EXPORT_PASSPORT',
            entity_id=passport.id,
            limit=request.query_params.get('limit', 50)
        )
        
        serializer = AuditLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get passport statistics"""
        queryset = self.get_queryset()
        
        total = queryset.count()
        active = queryset.filter(is_active=True).count()
        verified = queryset.filter(is_verified=True).count()
        
        by_status = queryset.values('deforestation_status').annotate(
            count=Count('id')
        )
        
        by_risk = queryset.values('risk_level').annotate(
            count=Count('id')
        )
        
        expiring_soon = queryset.filter(
            valid_until__lte=timezone.now().date() + timedelta(days=30),
            valid_until__gte=timezone.now().date()
        ).count()
        
        expired = queryset.filter(
            valid_until__lt=timezone.now().date()
        ).count()
        
        return Response({
            'total': total,
            'active': active,
            'verified': verified,
            'expiring_soon': expiring_soon,
            'expired': expired,
            'by_status': list(by_status),
            'by_risk': list(by_risk)
        })


class DeforestationCheckViewSet(viewsets.ModelViewSet):
    """ViewSet for managing deforestation checks"""
    
    serializer_class = DeforestationCheckSerializer
    permission_classes = [IsAuthenticated, IsTenantUser]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Get deforestation checks for current tenant"""
        queryset = DeforestationCheck.objects.select_related(
            'farm',
            'farm__farmer',
            'export_passport'
        )
        
        # Filter by farm
        farm_id = self.request.query_params.get('farm_id')
        if farm_id:
            queryset = queryset.filter(farm_id=farm_id)
        
        # Filter by result
        result = self.request.query_params.get('result')
        if result:
            queryset = queryset.filter(result=result)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(check_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(check_date__lte=end_date)
        
        return queryset.order_by('-check_date')
    
    @action(detail=False, methods=['post'])
    def run_analysis(self, request):
        """Run deforestation analysis on a farm"""
        farm_id = request.data.get('farm_id')
        check_type = request.data.get('check_type', 'PERIODIC')
        
        if not farm_id:
            return Response(
                {'error': 'farm_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from apps.farms.models import Farm
        farm = get_object_or_404(Farm, id=farm_id)
        
        try:
            analyzer = DeforestationAnalyzer()
            check = analyzer.analyze_farm(farm, check_type=check_type)
            
            # Log audit
            AuditLogger.log_deforestation_check(
                check=check,
                user_id=request.user.id,
                user_name=request.user.get_full_name(),
                request=request
            )
            
            serializer = self.get_serializer(check)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Deforestation analysis failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def batch_analysis(self, request):
        """Run batch deforestation analysis"""
        farm_ids = request.data.get('farm_ids', [])
        
        if not farm_ids:
            return Response(
                {'error': 'farm_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from apps.farms.models import Farm
        farms = Farm.objects.filter(id__in=farm_ids)
        
        try:
            analyzer = DeforestationAnalyzer()
            results = analyzer.batch_analyze(farms)
            
            return Response(results)
            
        except Exception as e:
            logger.error(f"Batch analysis failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def high_risk(self, request):
        """Get high-risk farms"""
        threshold = request.query_params.get('threshold', 70)
        
        analyzer = DeforestationAnalyzer()
        high_risk_checks = analyzer.get_high_risk_farms(threshold=int(threshold))
        
        serializer = self.get_serializer(high_risk_checks, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def generate_report(self, request):
        """Generate deforestation report"""
        serializer = DeforestationReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Generate summary report
        analyzer = DeforestationAnalyzer()
        summary = analyzer.generate_summary_report(
            start_date=serializer.validated_data['start_date'],
            end_date=serializer.validated_data['end_date']
        )
        
        return Response(summary)


class ComplianceDocumentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing compliance documents"""
    
    serializer_class = ComplianceDocumentSerializer
    permission_classes = [IsAuthenticated, IsTenantUser]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Get documents for current tenant"""
        queryset = ComplianceDocument.objects.select_related('export_passport')
        
        # Filter by passport
        passport_id = self.request.query_params.get('passport_id')
        if passport_id:
            queryset = queryset.filter(export_passport__passport_id=passport_id)
        
        # Filter by document type
        doc_type = self.request.query_params.get('document_type')
        if doc_type:
            queryset = queryset.filter(document_type=doc_type)
        
        return queryset.order_by('-upload_date')
    
    def perform_create(self, serializer):
        """Create document and log audit"""
        document = serializer.save(uploaded_by=self.request.user.get_full_name())
        
        # Log audit
        AuditLogger.log_document_upload(
            document=document,
            user_id=self.request.user.id,
            user_name=self.request.user.get_full_name(),
            request=self.request
        )


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing audit logs"""
    
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsTenantUser]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Get audit logs for current tenant"""
        queryset = AuditLog.objects.all()
        
        # Filter by entity type
        entity_type = self.request.query_params.get('entity_type')
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        
        # Filter by action
        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        # Filter by user
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        return queryset.order_by('-timestamp')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get audit summary"""
        days = int(request.query_params.get('days', 7))
        start_date = timezone.now() - timedelta(days=days)
        end_date = timezone.now()
        
        summary = AuditLogger.get_audit_summary(start_date, end_date)
        return Response(summary)