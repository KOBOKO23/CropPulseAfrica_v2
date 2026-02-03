# apps/banks/serializers.py

from rest_framework import serializers

from .models import (
    Bank,
    APIKey,
    Webhook,
    WebhookDelivery,
    UsageLog,
    BillingRecord,
)


# ===========================================================================
# Bank
# ===========================================================================

class BankSerializer(serializers.ModelSerializer):
    """Read – safe to expose to any authenticated user."""

    tier_limits       = serializers.SerializerMethodField()
    active_api_keys   = serializers.SerializerMethodField()
    active_webhooks   = serializers.SerializerMethodField()

    class Meta:
        model  = Bank
        fields = [
            'id', 'bank_id', 'name', 'registration_number',
            'contact_email', 'contact_phone',
            'subscription_tier', 'is_active',
            'tier_limits', 'active_api_keys', 'active_webhooks',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'bank_id', 'created_at', 'updated_at']

    def get_tier_limits(self, obj):
        return obj.tier_limits

    def get_active_api_keys(self, obj):
        return obj.active_api_key_count()

    def get_active_webhooks(self, obj):
        return obj.active_webhook_count()


class BankUpdateSerializer(serializers.ModelSerializer):
    """Fields a bank owner is allowed to change after initial creation."""

    class Meta:
        model  = Bank
        fields = ['name', 'contact_email', 'contact_phone', 'subscription_tier']


# ===========================================================================
# APIKey
# ===========================================================================

class APIKeySerializer(serializers.ModelSerializer):
    """Read – never exposes the raw token or full hash."""

    class Meta:
        model  = APIKey
        fields = [
            'id', 'bank', 'name', 'key_prefix', 'status',
            'permissions', 'is_active',
            'created_at', 'expires_at', 'last_used_at', 'revoked_at',
        ]
        read_only_fields = fields   # everything read-only here


class APIKeyCreateSerializer(serializers.Serializer):
    """
    Write.  Accepts name / permissions / optional expiry.
    ``raw_key`` is injected into the response by the service and
    returned exactly once.
    """

    name            = serializers.CharField(max_length=100)
    permissions     = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    expires_in_days = serializers.IntegerField(required=False, allow_null=True, default=None, min_value=1, max_value=365)

    def validate_permissions(self, value):
        valid = {c[0] for c in APIKey.PERMISSION_CHOICES}
        bad   = set(value) - valid
        if bad:
            raise serializers.ValidationError(f'Unknown permissions: {bad}')
        return value

    def create(self, validated_data):
        from .services.api_key_service import APIKeyService
        return APIKeyService.create(
            bank            = self.context['bank'],
            name            = validated_data['name'],
            permissions     = validated_data['permissions'],
            expires_in_days = validated_data.get('expires_in_days'),
        )


# ===========================================================================
# Webhook
# ===========================================================================

class WebhookSerializer(serializers.ModelSerializer):
    """Read – exposes secret_prefix only."""

    class Meta:
        model  = Webhook
        fields = [
            'id', 'bank', 'name', 'url', 'secret_prefix',
            'subscribed_events', 'is_active',
            'max_retries', 'timeout_seconds',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'bank', 'secret_prefix', 'created_at', 'updated_at']


class WebhookCreateSerializer(serializers.Serializer):
    """
    Write.  ``signing_secret`` is accepted once and hashed by the
    service.  If omitted we auto-generate one and return it.
    """

    name              = serializers.CharField(max_length=100)
    url               = serializers.URLField(max_length=500)
    signing_secret    = serializers.CharField(max_length=200, required=False, allow_null=True, default=None)
    subscribed_events = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    max_retries       = serializers.IntegerField(default=3, min_value=0, max_value=10)
    timeout_seconds   = serializers.IntegerField(default=10, min_value=1, max_value=60)

    def validate_url(self, value):
        if not value.startswith('https://'):
            raise serializers.ValidationError('Webhook URL must use HTTPS.')
        return value

    def validate_subscribed_events(self, value):
        valid = {e[0] for e in Webhook.EVENT_TYPES}
        bad   = set(value) - valid
        if bad:
            raise serializers.ValidationError(f'Unknown event types: {bad}')
        return value

    def validate(self, attrs):
        bank = self.context['bank']
        if bank.active_webhook_count() >= bank.max_webhooks:
            raise serializers.ValidationError(
                'Subscription tier does not allow more active webhooks. '
                'Upgrade or deactivate an existing one.'
            )
        return attrs

    def create(self, validated_data):
        from .services.webhook_service import WebhookService
        return WebhookService.create(bank=self.context['bank'], **validated_data)


class WebhookUpdateSerializer(serializers.ModelSerializer):
    """Mutable fields on an existing webhook.  Secret cannot be changed – rotate instead."""

    class Meta:
        model  = Webhook
        fields = ['name', 'url', 'subscribed_events', 'is_active', 'max_retries', 'timeout_seconds']

    def validate_url(self, value):
        if not value.startswith('https://'):
            raise serializers.ValidationError('Webhook URL must use HTTPS.')
        return value


# ===========================================================================
# WebhookDelivery  (read-only)
# ===========================================================================

class WebhookDeliverySerializer(serializers.ModelSerializer):
    webhook_name = serializers.CharField(source='webhook.name', read_only=True)

    class Meta:
        model  = WebhookDelivery
        fields = [
            'id', 'webhook', 'webhook_name', 'event_type', 'payload',
            'status', 'http_status_code', 'response_body',
            'attempts', 'next_retry_at', 'created_at', 'completed_at',
        ]
        read_only_fields = fields


# ===========================================================================
# UsageLog  (read-only)
# ===========================================================================

class UsageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = UsageLog
        fields = [
            'id', 'bank', 'date', 'api_calls',
            'unique_endpoints', 'peak_calls_hour', 'created_at',
        ]
        read_only_fields = fields


# ===========================================================================
# BillingRecord  (read-only from API; writes happen inside billing_service)
# ===========================================================================

class BillingRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model  = BillingRecord
        fields = [
            'id', 'bank', 'billing_month', 'subscription_tier',
            'total_api_calls', 'overage_calls',
            'base_amount', 'overage_amount', 'total_amount',
            'status', 'issued_at', 'paid_at', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields