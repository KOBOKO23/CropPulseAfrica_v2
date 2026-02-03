# apps/banks/views.py

import logging
from rest_framework import generics, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Bank, APIKey, Webhook, WebhookDelivery, UsageLog, BillingRecord
from .serializers import (
    BankSerializer, BankUpdateSerializer,
    APIKeySerializer, APIKeyCreateSerializer,
    WebhookSerializer, WebhookCreateSerializer, WebhookUpdateSerializer,
    WebhookDeliverySerializer,
    UsageLogSerializer,
    BillingRecordSerializer,
)
from .services.tenant_filter  import TenantFilter, TenantFilterMixin
from .services.usage_tracker  import UsageTracker
from .services.webhook_service import WebhookService

logger = logging.getLogger(__name__)


# ===========================================================================
# Helper mixins
# ===========================================================================

class BankContextMixin:
    """Resolve the authenticated bank and make it available as self.bank."""

    def get_bank(self):
        bank = TenantFilter.bank_from_request(self.request)
        if bank is None:
            return None
        return bank


class RateLimitHeaderMixin:
    """
    Attach X-RateLimit-Limit / Remaining / Reset to every response.
    """

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        bank = TenantFilter.bank_from_request(request)
        if bank:
            response['X-RateLimit-Limit']     = str(bank.daily_api_limit)
            response['X-RateLimit-Remaining'] = str(UsageTracker.remaining_calls(bank))
        return response


# ===========================================================================
# Bank profile
# ===========================================================================

class BankProfileView(RateLimitHeaderMixin, BankContextMixin, APIView):
    """GET / PATCH the authenticated bank's own profile."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bank = self.get_bank()
        if not bank:
            return Response({'detail': 'No bank profile found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(BankSerializer(bank).data)

    def patch(self, request):
        bank = self.get_bank()
        if not bank:
            return Response({'detail': 'No bank profile found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = BankUpdateSerializer(bank, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BankSerializer(bank).data)


# ===========================================================================
# API Keys
# ===========================================================================

class APIKeyListView(RateLimitHeaderMixin, TenantFilterMixin, generics.ListAPIView):
    """List all API keys for the authenticated bank."""
    permission_classes = [IsAuthenticated]
    serializer_class   = APIKeySerializer
    queryset           = APIKey.objects.all()


class APIKeyCreateView(RateLimitHeaderMixin, BankContextMixin, generics.CreateAPIView):
    """
    POST  { name, permissions, expires_in_days }
    Response includes ``raw_key`` exactly once.
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = APIKeyCreateSerializer

    def get_serializer_context(self):
        ctx  = super().get_serializer_context()
        ctx['bank'] = self.get_bank()
        return ctx

    def create(self, request, *args, **kwargs):
        bank = self.get_bank()
        if not bank:
            return Response({'detail': 'No bank profile found.'}, status=status.HTTP_404_NOT_FOUND)

        # Tier cap
        if bank.active_api_key_count() >= bank.max_api_keys:
            return Response(
                {'detail': 'Subscription tier does not allow more API keys.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key_data   = serializer.save()   # returns the dict from APIKeyService.create()
        return Response(key_data, status=status.HTTP_201_CREATED)


class APIKeyRevokeView(RateLimitHeaderMixin, BankContextMixin, APIView):
    """POST  /api/v1/banks/api-keys/{id}/revoke/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        bank = self.get_bank()
        if not bank:
            return Response({'detail': 'No bank profile found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            key = APIKey.objects.get(pk=pk, bank=bank)
        except APIKey.DoesNotExist:
            return Response({'detail': 'Key not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not key.is_active:
            return Response({'detail': 'Key is already inactive.'}, status=status.HTTP_400_BAD_REQUEST)

        from .services.api_key_service import APIKeyService
        APIKeyService.revoke(key, revoked_by=request.user)
        return Response(APIKeySerializer(key).data)


class APIKeyRotateView(RateLimitHeaderMixin, BankContextMixin, APIView):
    """POST  /api/v1/banks/api-keys/{id}/rotate/  — revoke old, return new raw_key."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        bank = self.get_bank()
        if not bank:
            return Response({'detail': 'No bank profile found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            key = APIKey.objects.get(pk=pk, bank=bank)
        except APIKey.DoesNotExist:
            return Response({'detail': 'Key not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not key.is_active:
            return Response({'detail': 'Key is already inactive.'}, status=status.HTTP_400_BAD_REQUEST)

        from .services.api_key_service import APIKeyService
        new_data = APIKeyService.rotate(key, revoked_by=request.user)
        return Response(new_data, status=status.HTTP_201_CREATED)


# ===========================================================================
# Webhooks
# ===========================================================================

class WebhookListView(RateLimitHeaderMixin, TenantFilterMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class   = WebhookSerializer
    queryset           = Webhook.objects.all()


class WebhookCreateView(RateLimitHeaderMixin, BankContextMixin, generics.CreateAPIView):
    """
    POST  { name, url, signing_secret?, subscribed_events, … }
    Response includes ``raw_signing_secret`` exactly once.
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = WebhookCreateSerializer

    def get_serializer_context(self):
        ctx  = super().get_serializer_context()
        ctx['bank'] = self.get_bank()
        return ctx

    def create(self, request, *args, **kwargs):
        bank = self.get_bank()
        if not bank:
            return Response({'detail': 'No bank profile found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wh_data    = serializer.save()
        return Response(wh_data, status=status.HTTP_201_CREATED)


class WebhookDetailView(RateLimitHeaderMixin, BankContextMixin, generics.RetrieveUpdateDestroyAPIView):
    """GET / PATCH / DELETE a single webhook."""
    permission_classes = [IsAuthenticated]
    serializer_class   = WebhookUpdateSerializer

    def get_object(self):
        bank = self.get_bank()
        if not bank:
            from rest_framework.exceptions import NotFound
            raise NotFound('No bank profile found.')
        try:
            return Webhook.objects.get(pk=self.kwargs['pk'], bank=bank)
        except Webhook.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Webhook not found.')

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        return Response(WebhookSerializer(obj).data)


class WebhookRotateSecretView(RateLimitHeaderMixin, BankContextMixin, APIView):
    """POST  /api/v1/banks/webhooks/{id}/rotate-secret/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        bank = self.get_bank()
        if not bank:
            return Response({'detail': 'No bank profile found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            wh = Webhook.objects.get(pk=pk, bank=bank)
        except Webhook.DoesNotExist:
            return Response({'detail': 'Webhook not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = WebhookService.rotate_secret(wh)
        return Response(data)


# ===========================================================================
# Webhook Deliveries  (read-only)
# ===========================================================================

class WebhookDeliveryListView(RateLimitHeaderMixin, TenantFilterMixin, generics.ListAPIView):
    """List delivery logs for the authenticated bank's webhooks."""
    permission_classes = [IsAuthenticated]
    serializer_class   = WebhookDeliverySerializer
    queryset           = WebhookDelivery.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        # Allow filtering by webhook id or event_type via query params
        webhook_id = self.request.query_params.get('webhook')
        event_type = self.request.query_params.get('event_type')
        status_    = self.request.query_params.get('status')

        if webhook_id:
            qs = qs.filter(webhook_id=webhook_id)
        if event_type:
            qs = qs.filter(event_type=event_type)
        if status_:
            qs = qs.filter(status=status_)
        return qs


# ===========================================================================
# Usage Logs  (read-only)
# ===========================================================================

class UsageLogListView(RateLimitHeaderMixin, TenantFilterMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class   = UsageLogSerializer
    queryset           = UsageLog.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        # Allow ?from=YYYY-MM-DD&to=YYYY-MM-DD
        from_date = self.request.query_params.get('from')
        to_date   = self.request.query_params.get('to')
        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)
        return qs


class UsageSummaryView(RateLimitHeaderMixin, BankContextMixin, APIView):
    """GET  /api/v1/banks/usage/summary/  — today's snapshot."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bank = self.get_bank()
        if not bank:
            return Response({'detail': 'No bank profile found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'bank_id':          bank.bank_id,
            'daily_limit':      bank.daily_api_limit,
            'calls_today':      UsageTracker.get_today_count(bank),
            'remaining_today':  UsageTracker.remaining_calls(bank),
            'is_rate_limited':  UsageTracker.is_rate_limited(bank),
        })


# ===========================================================================
# Billing Records  (read-only)
# ===========================================================================

class BillingRecordListView(RateLimitHeaderMixin, TenantFilterMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class   = BillingRecordSerializer
    queryset           = BillingRecord.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        status_ = self.request.query_params.get('status')
        if status_:
            qs = qs.filter(status=status_)
        return qs


class BillingRecordDetailView(RateLimitHeaderMixin, BankContextMixin, generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class   = BillingRecordSerializer

    def get_object(self):
        bank = self.get_bank()
        if not bank:
            from rest_framework.exceptions import NotFound
            raise NotFound('No bank profile found.')
        try:
            return BillingRecord.objects.get(pk=self.kwargs['pk'], bank=bank)
        except BillingRecord.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Billing record not found.')