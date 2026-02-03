# apps/banks/services/tenant_filter.py
# ---------------------------------------------------------------------------
# Every queryset that exposes bank-owned data passes through here before
# it reaches the client.  Two entry-points:
#
#     1.  TenantFilter.scope(qs, bank)    – explicit call
#     2.  TenantFilterMixin               – CBV mixin (calls #1 automatically)
# ---------------------------------------------------------------------------

import logging
from django.db import models

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry: model_label → ORM filter kwarg that reaches Bank
# ---------------------------------------------------------------------------
# Direct FK  (model.bank  is a ForeignKey to Bank)
_DIRECT  = {
    'banks.apikey':        'bank',
    'banks.webhook':       'bank',
    'banks.usagelog':      'bank',
    'banks.billingrecord': 'bank',
}

# Indirect FK  (need to traverse a relation first)
_INDIRECT = {
    'banks.webhookdelivery': 'webhook__bank',
}


class TenantFilter:
    """Stateless helper – all methods are static."""

    @staticmethod
    def scope(queryset: models.QuerySet, bank) -> models.QuerySet:
        """
        Return *queryset* filtered to rows belonging to *bank*.

        Raises ValueError for unrecognised models so that a developer
        can never accidentally ship an unscoped list endpoint.
        """
        label = f'{queryset.model._meta.app_label}.{queryset.model._meta.model_name}'

        if label in _DIRECT:
            return queryset.filter(**{_DIRECT[label]: bank})
        if label in _INDIRECT:
            return queryset.filter(**{_INDIRECT[label]: bank})

        # Safety net: if the model literally has a ``bank`` field we use
        # it but log a warning so it gets registered properly.
        if hasattr(queryset.model, 'bank'):
            logger.warning(
                "TenantFilter: '%s' not registered – falling back to "
                "filter(bank=…).  Add it to tenant_filter.py.", label,
            )
            return queryset.filter(bank=bank)

        raise ValueError(
            f"TenantFilter does not know how to scope '{label}'. "
            f"Register it in apps/banks/services/tenant_filter.py."
        )

    # ------------------------------------------------------------------
    # Pull the bank out of whatever auth mechanism was used
    # ------------------------------------------------------------------
    @staticmethod
    def bank_from_request(request):
        """
        Works with:
            a) API-key auth  → request.api_key.bank   (set by middleware)
            b) Session / JWT → request.user.bank_profile
        """
        if getattr(request, 'api_key', None) is not None:
            return request.api_key.bank

        user = getattr(request, 'user', None)
        if user and user.is_authenticated and hasattr(user, 'bank_profile'):
            return user.bank_profile

        return None


class TenantFilterMixin:
    """
    DRF mixin for ListAPIView / RetrieveAPIView / …

    If the request carries a bank identity we scope; if not (e.g. a
    platform-admin user) we leave the queryset untouched.  Views that
    *require* a bank should enforce that in get() / post() explicitly.
    """

    def get_queryset(self):
        qs   = super().get_queryset()
        bank = TenantFilter.bank_from_request(self.request)
        return TenantFilter.scope(qs, bank) if bank else qs