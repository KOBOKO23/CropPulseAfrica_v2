# compliance/serializers.py
from rest_framework import serializers
from .models import (
    ExportPassport,
    DeforestationCheck,
    ComplianceDocument,
    AuditLog,
    TranslationCache
)
from apps.farmers.serializers import FarmerSerializer
from apps.farms.serializers import FarmSerializer


class DeforestationCheckSerializer(serializers.ModelSerializer):
    """Serializer for deforestation checks"""
    
    farm_name = serializers.CharField(source='farm.farm_name', read_only=True)
    farmer_name = serializers.CharField(source='farm.farmer.full_name', read_only=True)
    
    class Meta:
        model = DeforestationCheck
        fields = [
            'id',
            'farm',
            'farm_name',
            'farmer_name',
            'export_passport',
            'check_date',
            'check_type',
            'analysis_start_date',
            'analysis_end_date',
            'baseline_date',
            'deforestation_detected',
            'forest_cover_percentage',
            'baseline_forest_cover',
            'change_in_forest_cover',
            'forest_loss_hectares',
            'satellite_provider',
            'satellite_imagery_urls',
            'cloud_cover_percentage',
            'ndvi_baseline',
            'ndvi_current',
            'ndvi_change',
            'risk_score',
            'risk_factors',
            'status',
            'result',
            'analysis_method',
            'confidence_score',
            'analysis_metadata',
            'reviewed_by',
            'reviewed_date',
            'reviewer_notes',
            'evidence_urls',
            'report_url',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'check_date', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate deforestation check data"""
        if data.get('analysis_end_date') and data.get('analysis_start_date'):
            if data['analysis_end_date'] < data['analysis_start_date']:
                raise serializers.ValidationError(
                    "Analysis end date must be after start date"
                )
        
        if data.get('forest_cover_percentage') is not None:
            if not 0 <= data['forest_cover_percentage'] <= 100:
                raise serializers.ValidationError(
                    "Forest cover percentage must be between 0 and 100"
                )
        
        return data


class ComplianceDocumentSerializer(serializers.ModelSerializer):
    """Serializer for compliance documents"""
    
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ComplianceDocument
        fields = [
            'id',
            'export_passport',
            'document_type',
            'document_name',
            'document_file',
            'file_url',
            'file_size_bytes',
            'file_hash',
            'description',
            'upload_date',
            'uploaded_by',
            'is_verified',
            'verified_by',
            'verified_date',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'upload_date', 'file_hash', 'created_at', 'updated_at']
    
    def get_file_url(self, obj):
        if obj.document_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.document_file.url)
            return obj.document_file.url
        return None


class ExportPassportSerializer(serializers.ModelSerializer):
    """Serializer for export passports"""
    
    farmer_details = FarmerSerializer(source='farmer', read_only=True)
    farm_details = FarmSerializer(source='farm', read_only=True)
    documents = ComplianceDocumentSerializer(many=True, read_only=True)
    deforestation_checks = DeforestationCheckSerializer(many=True, read_only=True)
    
    is_expired = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    qr_code_url = serializers.SerializerMethodField()
    pdf_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ExportPassport
        fields = [
            'id',
            'passport_id',
            'farmer',
            'farmer_details',
            'farm',
            'farm_details',
            'dds_reference_number',
            'operator_name',
            'operator_eori',
            'commodity_type',
            'commodity_code',
            'baseline_date',
            'deforestation_status',
            'risk_level',
            'satellite_proof_url',
            'satellite_analysis_date',
            'gps_coordinates',
            'centroid_latitude',
            'centroid_longitude',
            'farm_size_hectares',
            'plot_area_sqm',
            'land_ownership_verified',
            'land_tenure_type',
            'land_document_url',
            'land_document_type',
            'harvest_season',
            'estimated_production_kg',
            'blockchain_hash',
            'blockchain_network',
            'blockchain_tx_hash',
            'blockchain_timestamp',
            'audit_trail',
            'issued_date',
            'valid_until',
            'is_active',
            'is_verified',
            'verified_by',
            'verified_date',
            'qr_code',
            'qr_code_url',
            'qr_data',
            'pdf_document',
            'pdf_url',
            'language',
            'notes',
            'internal_reference',
            'documents',
            'deforestation_checks',
            'is_expired',
            'days_until_expiry',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'passport_id',
            'issued_date',
            'is_expired',
            'days_until_expiry',
            'created_at',
            'updated_at',
        ]
    
    def get_qr_code_url(self, obj):
        if obj.qr_code:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None
    
    def get_pdf_url(self, obj):
        if obj.pdf_document:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.pdf_document.url)
            return obj.pdf_document.url
        return None
    
    def validate_gps_coordinates(self, value):
        """Validate GPS coordinates format"""
        if not isinstance(value, list):
            raise serializers.ValidationError("GPS coordinates must be a list")
        
        if len(value) < 3:
            raise serializers.ValidationError(
                "At least 3 GPS points required for a polygon"
            )
        
        for point in value:
            if not isinstance(point, dict) or 'lat' not in point or 'lng' not in point:
                raise serializers.ValidationError(
                    "Each GPS point must have 'lat' and 'lng' keys"
                )
            
            try:
                lat = float(point['lat'])
                lng = float(point['lng'])
                
                if not -90 <= lat <= 90:
                    raise serializers.ValidationError(
                        f"Invalid latitude: {lat}. Must be between -90 and 90"
                    )
                
                if not -180 <= lng <= 180:
                    raise serializers.ValidationError(
                        f"Invalid longitude: {lng}. Must be between -180 and 180"
                    )
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    "GPS coordinates must be numeric values"
                )
        
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        if data.get('valid_until') and data.get('issued_date'):
            if data['valid_until'] <= data['issued_date']:
                raise serializers.ValidationError(
                    "Valid until date must be after issued date"
                )
        
        # Ensure centroid is provided when GPS coordinates are given
        if data.get('gps_coordinates'):
            if not data.get('centroid_latitude') or not data.get('centroid_longitude'):
                # Auto-calculate centroid
                coords = data['gps_coordinates']
                lats = [float(p['lat']) for p in coords]
                lngs = [float(p['lng']) for p in coords]
                data['centroid_latitude'] = sum(lats) / len(lats)
                data['centroid_longitude'] = sum(lngs) / len(lngs)
        
        return data


class ExportPassportListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing export passports"""
    
    farmer_name = serializers.CharField(source='farmer.full_name', read_only=True)
    farm_name = serializers.CharField(source='farm.farm_name', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = ExportPassport
        fields = [
            'id',
            'passport_id',
            'farmer_name',
            'farm_name',
            'dds_reference_number',
            'commodity_type',
            'deforestation_status',
            'risk_level',
            'issued_date',
            'valid_until',
            'is_active',
            'is_verified',
            'is_expired',
            'created_at',
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for audit logs"""
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'entity_type',
            'entity_id',
            'user_id',
            'user_name',
            'user_role',
            'action',
            'changes',
            'reason',
            'ip_address',
            'user_agent',
            'timestamp',
            'created_at',
        ]
        read_only_fields = ['id', 'timestamp', 'created_at']


class PassportVerificationSerializer(serializers.Serializer):
    """Serializer for passport verification requests"""
    
    passport_id = serializers.CharField(max_length=50)
    qr_code_data = serializers.JSONField(required=False)
    
    def validate_passport_id(self, value):
        """Check if passport exists"""
        if not ExportPassport.objects.filter(passport_id=value).exists():
            raise serializers.ValidationError("Passport not found")
        return value


class BulkPassportCreateSerializer(serializers.Serializer):
    """Serializer for bulk passport creation"""
    
    farm_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1
    )
    commodity_type = serializers.ChoiceField(
        choices=[
            'COFFEE', 'COCOA', 'PALM_OIL', 'CATTLE', 
            'WOOD', 'RUBBER', 'SOY'
        ]
    )
    operator_name = serializers.CharField(max_length=255)
    operator_eori = serializers.CharField(max_length=50, required=False, allow_blank=True)
    language = serializers.ChoiceField(
        choices=['en', 'fr', 'de', 'es', 'sw'],
        default='en'
    )


class DeforestationReportSerializer(serializers.Serializer):
    """Serializer for deforestation analysis reports"""
    
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    farm_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False
    )
    include_satellite_imagery = serializers.BooleanField(default=True)
    report_format = serializers.ChoiceField(
        choices=['PDF', 'JSON', 'CSV'],
        default='PDF'
    )
    
    def validate(self, data):
        if data['end_date'] < data['start_date']:
            raise serializers.ValidationError(
                "End date must be after start date"
            )
        return data


class BlockchainAnchorSerializer(serializers.Serializer):
    """Serializer for blockchain anchoring requests"""
    
    passport_id = serializers.CharField(max_length=50)
    network = serializers.ChoiceField(
        choices=['ETHEREUM', 'POLYGON', 'AVALANCHE', 'CELO'],
        default='POLYGON'
    )
    
    def validate_passport_id(self, value):
        try:
            passport = ExportPassport.objects.get(passport_id=value)
            if passport.blockchain_hash:
                raise serializers.ValidationError(
                    "Passport is already anchored on blockchain"
                )
        except ExportPassport.DoesNotExist:
            raise serializers.ValidationError("Passport not found")
        return value


class TranslationRequestSerializer(serializers.Serializer):
    """Serializer for translation requests"""
    
    passport_id = serializers.CharField(max_length=50)
    target_language = serializers.ChoiceField(
        choices=['en', 'fr', 'de', 'es', 'sw']
    )
    
    def validate_passport_id(self, value):
        if not ExportPassport.objects.filter(passport_id=value).exists():
            raise serializers.ValidationError("Passport not found")
        return value