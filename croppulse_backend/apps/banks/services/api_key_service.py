# apps/banks/services/api_key_service.py

import hashlib
import secrets
import logging
from datetime import timedelta
from django.utils import timezone

from ..models import APIKey, Bank

logger = logging.getLogger(__name__)

_TOKEN_BYTES = 32   # → 64-char hex string


class APIKeyService:
    """
    Full lifecycle for APIKey records.

    ``validate()`` is the hot-path: called by ``api_key_middleware`` on
    every single inbound request.  It does exactly one indexed SELECT
    and nothing else.
    """

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------
    @staticmethod
    def _hash(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    # ------------------------------------------------------------------
    # create
    # ------------------------------------------------------------------
    @staticmethod
    def create(
        bank: Bank,
        name: str,
        permissions: list | None = None,
        expires_in_days: int | None = None,
    ) -> dict:
        """
        Generate + persist a new key.  Returns a dict that includes
        ``raw_key`` — the only time it will ever be visible.
        """
        raw        = secrets.token_hex(_TOKEN_BYTES)
        key_hash   = APIKeyService._hash(raw)
        key_prefix = raw[:8]

        expires_at = (
            timezone.now() + timedelta(days=expires_in_days)
            if expires_in_days else None
        )

        obj = APIKey.objects.create(
            bank       = bank,
            name       = name,
            key_prefix = key_prefix,
            key_hash   = key_hash,
            permissions= permissions or [],
            expires_at = expires_at,
        )

        logger.info('Created API key %s for bank %s', obj.key_prefix, bank.bank_id)

        return {
            'id':          obj.id,
            'bank_id':     bank.bank_id,
            'name':        obj.name,
            'key_prefix':  obj.key_prefix,
            'raw_key':     raw,                # ← shown once only
            'permissions': obj.permissions,
            'expires_at':  obj.expires_at,
            'created_at':  obj.created_at,
        }

    # ------------------------------------------------------------------
    # validate  (middleware hot-path)
    # ------------------------------------------------------------------
    @staticmethod
    def validate(raw_token: str) -> APIKey | None:
        """
        Return the APIKey if *raw_token* is valid & active; else None.
        Side-effect: stamps ``last_used_at``.
        """
        key_hash = APIKeyService._hash(raw_token)
        try:
            obj = APIKey.objects.select_related('bank').get(key_hash=key_hash)
        except APIKey.DoesNotExist:
            logger.warning('API-key lookup miss (hash prefix %s…)', key_hash[:12])
            return None

        if not obj.is_active:
            logger.warning('API key %s no longer active (status=%s)', obj.key_prefix, obj.status)
            return None

        # fire-and-forget stamp
        APIKey.objects.filter(pk=obj.pk).update(last_used_at=timezone.now())
        return obj

    # ------------------------------------------------------------------
    # revoke
    # ------------------------------------------------------------------
    @staticmethod
    def revoke(api_key: APIKey, revoked_by=None) -> APIKey:
        api_key.status     = APIKey.STATUS_REVOKED
        api_key.revoked_at = timezone.now()
        api_key.revoked_by = revoked_by
        api_key.save(update_fields=['status', 'revoked_at', 'revoked_by'])
        logger.info('Revoked key %s for bank %s', api_key.key_prefix, api_key.bank.bank_id)
        return api_key

    # ------------------------------------------------------------------
    # rotate  (revoke old + create new with same name / permissions)
    # ------------------------------------------------------------------
    @staticmethod
    def rotate(api_key: APIKey, revoked_by=None) -> dict:
        name        = api_key.name
        permissions = api_key.permissions
        bank        = api_key.bank

        expires_in_days = None
        if api_key.expires_at:
            remaining       = (api_key.expires_at - timezone.now()).days
            expires_in_days = max(remaining, 1)

        APIKeyService.revoke(api_key, revoked_by=revoked_by)
        return APIKeyService.create(
            bank=bank, name=name,
            permissions=permissions,
            expires_in_days=expires_in_days,
        )

    # ------------------------------------------------------------------
    # bulk expiry sweep  (Celery beat)
    # ------------------------------------------------------------------
    @staticmethod
    def expire_stale_keys() -> int:
        """
        Flip any ACTIVE key whose ``expires_at`` has passed to EXPIRED.
        Safe to call repeatedly.
        """
        count = (
            APIKey.objects
            .filter(status=APIKey.STATUS_ACTIVE, expires_at__lt=timezone.now())
            .update(status=APIKey.STATUS_EXPIRED)
        )
        if count:
            logger.info('Expired %d stale API key(s)', count)
        return count