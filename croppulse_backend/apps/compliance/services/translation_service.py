# compliance/services/translation_service.py
from django.utils import timezone
from datetime import timedelta
import hashlib
from ..models import TranslationCache
import logging

logger = logging.getLogger(__name__)


class TranslationService:
    """Service for translating compliance documents"""
    
    # Translation mappings for common EUDR terms
    TRANSLATIONS = {
        'en': {
            'export_passport': 'Export Passport',
            'dds_reference': 'DDS Reference Number',
            'operator_information': 'Operator Information',
            'commodity_information': 'Commodity Information',
            'farmer_information': 'Farmer Information',
            'farm_geolocation': 'Farm & Geolocation Data',
            'land_tenure': 'Land Tenure Information',
            'deforestation_verification': 'Deforestation Verification',
            'blockchain_verification': 'Blockchain Verification',
            'passport_validity': 'Passport Validity',
            'status_clear': 'Clear - No Deforestation',
            'status_under_review': 'Under Review',
            'status_flagged': 'Flagged - Deforestation Detected',
            'status_remediated': 'Remediated',
            'risk_low': 'Low Risk',
            'risk_standard': 'Standard Risk',
            'risk_high': 'High Risk',
            'issued_date': 'Issued Date',
            'valid_until': 'Valid Until',
            'verified': 'Verified',
            'active': 'Active',
            'inactive': 'Inactive',
            'disclaimer': 'This digital passport is issued in compliance with EU Regulation 2023/1115 on deforestation-free products.'
        },
        'fr': {
            'export_passport': 'Passeport d\'Exportation',
            'dds_reference': 'Numéro de Référence DDS',
            'operator_information': 'Informations sur l\'Opérateur',
            'commodity_information': 'Informations sur les Produits',
            'farmer_information': 'Informations sur l\'Agriculteur',
            'farm_geolocation': 'Données de la Ferme et Géolocalisation',
            'land_tenure': 'Informations sur la Tenure Foncière',
            'deforestation_verification': 'Vérification de la Déforestation',
            'blockchain_verification': 'Vérification Blockchain',
            'passport_validity': 'Validité du Passeport',
            'status_clear': 'Clair - Pas de Déforestation',
            'status_under_review': 'En Cours d\'Examen',
            'status_flagged': 'Signalé - Déforestation Détectée',
            'status_remediated': 'Remédié',
            'risk_low': 'Risque Faible',
            'risk_standard': 'Risque Standard',
            'risk_high': 'Risque Élevé',
            'issued_date': 'Date d\'Émission',
            'valid_until': 'Valable Jusqu\'au',
            'verified': 'Vérifié',
            'active': 'Actif',
            'inactive': 'Inactif',
            'disclaimer': 'Ce passeport numérique est délivré conformément au règlement UE 2023/1115 sur les produits sans déforestation.'
        },
        'de': {
            'export_passport': 'Exportpass',
            'dds_reference': 'DDS-Referenznummer',
            'operator_information': 'Betreiberinformationen',
            'commodity_information': 'Wareninformationen',
            'farmer_information': 'Landwirtinformationen',
            'farm_geolocation': 'Bauernhof & Geolokalisierungsdaten',
            'land_tenure': 'Informationen zum Landbesitz',
            'deforestation_verification': 'Entwaldungsüberprüfung',
            'blockchain_verification': 'Blockchain-Verifizierung',
            'passport_validity': 'Passgültigkeit',
            'status_clear': 'Klar - Keine Entwaldung',
            'status_under_review': 'In Überprüfung',
            'status_flagged': 'Markiert - Entwaldung Erkannt',
            'status_remediated': 'Behoben',
            'risk_low': 'Niedriges Risiko',
            'risk_standard': 'Standardrisiko',
            'risk_high': 'Hohes Risiko',
            'issued_date': 'Ausstellungsdatum',
            'valid_until': 'Gültig bis',
            'verified': 'Verifiziert',
            'active': 'Aktiv',
            'inactive': 'Inaktiv',
            'disclaimer': 'Dieser digitale Pass wird gemäß der EU-Verordnung 2023/1115 über entwaldungsfreie Produkte ausgestellt.'
        },
        'es': {
            'export_passport': 'Pasaporte de Exportación',
            'dds_reference': 'Número de Referencia DDS',
            'operator_information': 'Información del Operador',
            'commodity_information': 'Información de Productos',
            'farmer_information': 'Información del Agricultor',
            'farm_geolocation': 'Datos de la Granja y Geolocalización',
            'land_tenure': 'Información de Tenencia de Tierra',
            'deforestation_verification': 'Verificación de Deforestación',
            'blockchain_verification': 'Verificación Blockchain',
            'passport_validity': 'Validez del Pasaporte',
            'status_clear': 'Claro - Sin Deforestación',
            'status_under_review': 'En Revisión',
            'status_flagged': 'Marcado - Deforestación Detectada',
            'status_remediated': 'Remediado',
            'risk_low': 'Riesgo Bajo',
            'risk_standard': 'Riesgo Estándar',
            'risk_high': 'Riesgo Alto',
            'issued_date': 'Fecha de Emisión',
            'valid_until': 'Válido Hasta',
            'verified': 'Verificado',
            'active': 'Activo',
            'inactive': 'Inactivo',
            'disclaimer': 'Este pasaporte digital se emite en cumplimiento del Reglamento UE 2023/1115 sobre productos libres de deforestación.'
        },
        'sw': {
            'export_passport': 'Pasipoti ya Usafirishaji',
            'dds_reference': 'Nambari ya Kumbukumbu ya DDS',
            'operator_information': 'Taarifa za Mfanyabiashara',
            'commodity_information': 'Taarifa za Bidhaa',
            'farmer_information': 'Taarifa za Mkulima',
            'farm_geolocation': 'Data ya Shamba na Mahali',
            'land_tenure': 'Taarifa za Umiliki wa Ardhi',
            'deforestation_verification': 'Uthibitisho wa Ukataji Miti',
            'blockchain_verification': 'Uthibitisho wa Blockchain',
            'passport_validity': 'Uhalali wa Pasipoti',
            'status_clear': 'Safi - Hakuna Ukataji Miti',
            'status_under_review': 'Inakaguliwa',
            'status_flagged': 'Imeripotiwa - Ukataji Miti Umegunduliwa',
            'status_remediated': 'Imetatuliwa',
            'risk_low': 'Hatari Ndogo',
            'risk_standard': 'Hatari ya Kawaida',
            'risk_high': 'Hatari Kubwa',
            'issued_date': 'Tarehe ya Utoaji',
            'valid_until': 'Halali Hadi',
            'verified': 'Imethibitishwa',
            'active': 'Inatumika',
            'inactive': 'Haifanyi Kazi',
            'disclaimer': 'Pasipoti hii ya kidijitali imetolewa kufuatia Kanuni ya EU 2023/1115 kuhusu bidhaa zisizo na ukataji miti.'
        }
    }
    
    def __init__(self, cache_days=30):
        self.cache_days = cache_days
    
    def translate(self, text, source_lang='en', target_lang='en'):
        """
        Translate text from source to target language
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
        
        Returns:
            str: Translated text
        """
        # If same language, return original
        if source_lang == target_lang:
            return text
        
        # Check cache first
        cache_key = self._generate_cache_key(text, source_lang, target_lang)
        cached = self._get_from_cache(cache_key)
        
        if cached:
            return cached
        
        # Try direct translation mapping
        if text.lower().replace(' ', '_') in self.TRANSLATIONS.get(source_lang, {}):
            key = text.lower().replace(' ', '_')
            if key in self.TRANSLATIONS.get(target_lang, {}):
                translated = self.TRANSLATIONS[target_lang][key]
                self._save_to_cache(cache_key, text, translated, source_lang, target_lang)
                return translated
        
        # For now, return original if no translation found
        # In production, this would call Google Translate API or similar
        logger.warning(
            f"No translation found for '{text}' from {source_lang} to {target_lang}"
        )
        return text
    
    def translate_passport_data(self, passport_data, target_lang='en'):
        """
        Translate passport data dictionary
        
        Args:
            passport_data: Dict containing passport information
            target_lang: Target language code
        
        Returns:
            dict: Translated passport data
        """
        translated = passport_data.copy()
        
        # Translate specific fields
        translate_keys = [
            'deforestation_status',
            'risk_level',
            'land_tenure_type',
            'commodity_type'
        ]
        
        for key in translate_keys:
            if key in translated:
                translated[key] = self.translate(
                    str(translated[key]),
                    'en',
                    target_lang
                )
        
        return translated
    
    def get_field_label(self, field_key, language='en'):
        """
        Get translated label for a field
        
        Args:
            field_key: Field key (e.g., 'export_passport')
            language: Target language
        
        Returns:
            str: Translated label
        """
        translations = self.TRANSLATIONS.get(language, self.TRANSLATIONS['en'])
        return translations.get(field_key, field_key)
    
    def _generate_cache_key(self, text, source_lang, target_lang):
        """Generate cache key for translation"""
        key_str = f"{text}_{source_lang}_{target_lang}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key):
        """Retrieve translation from cache"""
        try:
            cached = TranslationCache.objects.get(
                cache_key=cache_key,
                expires_at__gt=timezone.now()
            )
            
            # Increment hit count
            cached.hit_count += 1
            cached.save(update_fields=['hit_count'])
            
            return cached.translated_text
            
        except TranslationCache.DoesNotExist:
            return None
    
    def _save_to_cache(self, cache_key, source_text, translated_text, source_lang, target_lang):
        """Save translation to cache"""
        try:
            TranslationCache.objects.create(
                cache_key=cache_key,
                source_language=source_lang,
                target_language=target_lang,
                source_text=source_text,
                translated_text=translated_text,
                expires_at=timezone.now() + timedelta(days=self.cache_days)
            )
        except Exception as e:
            logger.error(f"Failed to cache translation: {str(e)}")
    
    def clear_expired_cache(self):
        """Remove expired translation cache entries"""
        deleted_count = TranslationCache.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()[0]
        
        logger.info(f"Cleared {deleted_count} expired translation cache entries")
        return deleted_count
    
    def get_supported_languages(self):
        """Get list of supported languages"""
        return [
            {'code': 'en', 'name': 'English'},
            {'code': 'fr', 'name': 'Français'},
            {'code': 'de', 'name': 'Deutsch'},
            {'code': 'es', 'name': 'Español'},
            {'code': 'sw', 'name': 'Kiswahili'},
        ]
    
    def translate_document_template(self, template_data, target_lang='en'):
        """
        Translate document template
        
        Args:
            template_data: Document template data
            target_lang: Target language
        
        Returns:
            dict: Translated template
        """
        translated = {}
        
        for key, value in template_data.items():
            if isinstance(value, str):
                translated[key] = self.translate(value, 'en', target_lang)
            elif isinstance(value, dict):
                translated[key] = self.translate_document_template(value, target_lang)
            elif isinstance(value, list):
                translated[key] = [
                    self.translate(item, 'en', target_lang) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                translated[key] = value
        
        return translated