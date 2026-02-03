# apps/banks/services/webhook_service.py
# ---------------------------------------------------------------------------
# Webhook lifecycle + event dispatch.
#
# Signing
# -------
# Every outbound POST carries ``X-Webhook-Signature``: the hex-encoded
# HMAC-SHA256 of the raw JSON body, keyed with the SHA-256 of the
# signing secret.
#
# Retry policy  (exponential back-off)
# ------------------------------------
# attempt 1 →  10 s
# attempt 2 →  60 s
# attempt 3 → 300 s
# …  up to webhook.max_retries.
# ---------------------------------------------------------------------------

import hashlib
import hmac
import json
import logging
import secrets
from datetime import timedelta

import requests
from django.utils import timezone

from ..models import Bank, Webhook, WebhookDelivery

logger = logging.getLogger(__name__)

_BACKOFF_BASE = 10   # seconds;  actual = base × 2^(attempt-1)


class WebhookService:

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @staticmethod
    def create(
        bank: Bank,
        name: str,
        url: str,
        signing_secret: str | None = None,
        subscribed_events: list | None = None,
        max_retries: int = 3,
        timeout_seconds: int = 10,
    ) -> dict:
        """
        Register a webhook.  Returns a dict that includes
        ``raw_signing_secret`` – visible exactly once.
        """
        if signing_secret is None:
            signing_secret = secrets.token_hex(32)

        secret_hash   = hashlib.sha256(signing_secret.encode()).hexdigest()
        secret_prefix = signing_secret[:8]

        wh = Webhook.objects.create(
            bank               = bank,
            name               = name,
            url                = url,
            signing_secret_hash= secret_hash,
            secret_prefix      = secret_prefix,
            subscribed_events  = subscribed_events or [],
            max_retries        = max_retries,
            timeout_seconds    = timeout_seconds,
        )

        logger.info("Created webhook '%s' for bank %s", wh.name, bank.bank_id)

        return {
            'id':                  wh.id,
            'bank_id':             bank.bank_id,
            'name':                wh.name,
            'url':                 wh.url,
            'secret_prefix':       wh.secret_prefix,
            'raw_signing_secret':  signing_secret,   # ← once only
            'subscribed_events':   wh.subscribed_events,
            'is_active':           wh.is_active,
            'created_at':          wh.created_at,
        }

    @staticmethod
    def rotate_secret(webhook: Webhook) -> dict:
        """Issue a new signing secret; return the raw value."""
        new_secret = secrets.token_hex(32)
        webhook.signing_secret_hash = hashlib.sha256(new_secret.encode()).hexdigest()
        webhook.secret_prefix       = new_secret[:8]
        webhook.save(update_fields=['signing_secret_hash', 'secret_prefix', 'updated_at'])
        logger.info("Rotated secret for webhook '%s'", webhook.name)
        return {
            'secret_prefix':      webhook.secret_prefix,
            'raw_signing_secret': new_secret,
        }

    # ------------------------------------------------------------------
    # Fan-out  (called by Celery task; creates pending delivery rows)
    # ------------------------------------------------------------------
    @staticmethod
    def enqueue_event(event_type: str, payload: dict, bank: Bank) -> int:
        """
        Create a WebhookDelivery(PENDING) for every active, subscribed
        webhook.  Returns the number of rows created.
        """
        created = 0
        for wh in Webhook.objects.filter(bank=bank, is_active=True):
            if wh.is_subscribed_to(event_type):
                WebhookDelivery.objects.create(
                    webhook   = wh,
                    event_type= event_type,
                    payload   = payload,
                )
                created += 1

        logger.info("Enqueued '%s' for bank %s → %d webhook(s)", event_type, bank.bank_id, created)
        return created

    # ------------------------------------------------------------------
    # Deliver  (called by Celery task; performs the HTTP POST)
    # ------------------------------------------------------------------
    @staticmethod
    def deliver(delivery: WebhookDelivery) -> bool:
        """
        POST the payload.  Returns True on 2xx.  On failure either
        schedules a retry or marks FAILED.
        """
        wh              = delivery.webhook
        delivery.attempts += 1

        body      = json.dumps(delivery.payload, separators=(',', ':'))
        signature = WebhookService._sign(body, wh.signing_secret_hash)

        headers = {
            'Content-Type':         'application/json',
            'X-Webhook-Signature':  signature,
            'X-Webhook-Event':      delivery.event_type,
            'User-Agent':           'CropPulse-Webhook/1.0',
        }

        try:
            resp = requests.post(wh.url, data=body, headers=headers, timeout=wh.timeout_seconds)
            delivery.http_status_code = resp.status_code
            delivery.response_body    = resp.text[:4096]

            if resp.ok:
                delivery.status      = WebhookDelivery.STATUS_SUCCESS
                delivery.completed_at = timezone.now()
                delivery.save()
                logger.info("Delivered '%s' → '%s' HTTP %d", delivery.event_type, wh.name, resp.status_code)
                return True

            logger.warning("Webhook '%s' returned HTTP %d", wh.name, resp.status_code)

        except requests.RequestException as exc:
            logger.warning("Webhook '%s' request error: %s", wh.name, exc)
            delivery.http_status_code = None
            delivery.response_body    = str(exc)[:4096]

        # --- failure path: retry or give up -------------------------------
        if delivery.attempts < wh.max_retries:
            delay                 = _BACKOFF_BASE * (2 ** (delivery.attempts - 1))
            delivery.status       = WebhookDelivery.STATUS_RETRYING
            delivery.next_retry_at = timezone.now() + timedelta(seconds=delay)
        else:
            delivery.status       = WebhookDelivery.STATUS_FAILED
            delivery.completed_at  = timezone.now()

        delivery.save()
        return False

    # ------------------------------------------------------------------
    # Retry sweep  (Celery beat – every 30-60 s)
    # ------------------------------------------------------------------
    @staticmethod
    def retry_due_deliveries() -> int:
        """Attempt delivery on every RETRYING row whose next_retry_at ≤ now."""
        due   = WebhookDelivery.objects.filter(
            status=WebhookDelivery.STATUS_RETRYING,
            next_retry_at__lte=timezone.now(),
        ).select_related('webhook')

        count = 0
        for d in due:
            WebhookService.deliver(d)
            count += 1

        if count:
            logger.info('Retried %d webhook delivery(ies)', count)
        return count

    # ------------------------------------------------------------------
    # Signing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _sign(body: str, secret_hash: str) -> str:
        """HMAC-SHA256 of *body* keyed with the stored secret hash."""
        return hmac.new(
            secret_hash.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def verify_signature(raw_body: str, received_sig: str, secret_hash: str) -> bool:
        """Public helper – can be used in integration tests or receiver code."""
        return hmac.compare_digest(
            WebhookService._sign(raw_body, secret_hash),
            received_sig,
        )