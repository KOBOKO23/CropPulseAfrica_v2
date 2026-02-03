# apps/banks/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from .models import Bank, APIKey, Webhook, WebhookDelivery, UsageLog, BillingRecord


# ===========================================================================
# Bank
# ===========================================================================

@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display  = ('bank_id', 'name', 'tier_badge', 'active_keys', 'active_whs', 'is_active', 'created_at')
    list_filter   = ('subscription_tier', 'is_active')
    search_fields = ('bank_id', 'name', 'registration_number', 'contact_email')
    ordering      = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'tier_limits_display')

    fieldsets = (
        ('Identity', {
            'fields': ('user', 'bank_id', 'name', 'registration_number'),
        }),
        ('Contact', {
            'fields': ('contact_email', 'contact_phone'),
        }),
        ('Subscription', {
            'fields': ('subscription_tier', 'is_active', 'tier_limits_display'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    # --- computed columns -------------------------------------------------
    _TIER_COLOURS = {
        'basic':      '#6b7280',
        'pro':        '#3b82f6',
        'enterprise': '#10b981',
    }

    def tier_badge(self, obj):
        colour = self._TIER_COLOURS.get(obj.subscription_tier, '#6b7280')
        return format_html(
            '<span style="background:{c};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">{t}</span>',
            c=colour, t=obj.get_subscription_tier_display(),
        )
    tier_badge.short_description = 'Tier'

    def active_keys(self, obj):
        return obj.active_api_key_count()
    active_keys.short_description = 'Active API Keys'

    def active_whs(self, obj):
        return obj.active_webhook_count()
    active_whs.short_description = 'Active Webhooks'

    def tier_limits_display(self, obj):
        limits = obj.tier_limits
        return format_html(
            '<pre style="font-size:13px">{}</pre>',
            '\n'.join(f'{k}: {v}' for k, v in limits.items()),
        )
    tier_limits_display.short_description = 'Tier Limits'


# ===========================================================================
# APIKey
# ===========================================================================

@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display  = ('bank', 'name', 'key_prefix', 'status_badge', 'permissions_summary', 'expires_at', 'last_used_at', 'created_at')
    list_filter   = ('status', 'bank')
    search_fields = ('bank__bank_id', 'bank__name', 'name', 'key_prefix')
    ordering      = ('-created_at',)
    readonly_fields = ('key_prefix', 'key_hash', 'created_at', 'revoked_at', 'revoked_by')

    # never expose the hash in forms
    exclude = ('key_hash',)

    actions = ('revoke_selected_keys',)

    # --- computed columns -------------------------------------------------
    _STATUS_COLOURS = {'active': '#10b981', 'revoked': '#ef4444', 'expired': '#f59e0b'}

    def status_badge(self, obj):
        colour = self._STATUS_COLOURS.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{c};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">{s}</span>',
            c=colour, s=obj.get_status_choices_display() if hasattr(obj, 'get_status_choices_display') else obj.status,
        )
    status_badge.short_description = 'Status'

    def permissions_summary(self, obj):
        return ', '.join(obj.permissions) if obj.permissions else '(none)'
    permissions_summary.short_description = 'Permissions'

    # --- actions ----------------------------------------------------------
    def revoke_selected_keys(self, request, queryset):
        from .services.api_key_service import APIKeyService
        for key in queryset.filter(status=APIKey.STATUS_ACTIVE):
            APIKeyService.revoke(key, revoked_by=request.user)
        self.message_user(request, f'Revoked {queryset.count()} key(s).')
    revoke_selected_keys.short_description = 'Revoke selected keys'


# ===========================================================================
# Webhook
# ===========================================================================

@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display  = ('bank', 'name', 'url_truncated', 'events_summary', 'is_active', 'created_at')
    list_filter   = ('is_active', 'bank')
    search_fields = ('bank__bank_id', 'name', 'url')
    ordering      = ('-created_at',)
    readonly_fields = ('secret_prefix', 'signing_secret_hash', 'created_at', 'updated_at')

    actions = ('deactivate_selected_webhooks',)

    def url_truncated(self, obj):
        return obj.url if len(obj.url) <= 60 else obj.url[:57] + '…'
    url_truncated.short_description = 'URL'

    def events_summary(self, obj):
        return ', '.join(obj.subscribed_events) if obj.subscribed_events else '(all events)'
    events_summary.short_description = 'Subscribed Events'

    def deactivate_selected_webhooks(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {queryset.count()} webhook(s).')
    deactivate_selected_webhooks.short_description = 'Deactivate selected webhooks'


# ===========================================================================
# WebhookDelivery
# ===========================================================================

@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display  = ('webhook', 'event_type', 'status_badge', 'http_status_code', 'attempts', 'created_at', 'completed_at')
    list_filter   = ('status', 'event_type')
    search_fields = ('webhook__name', 'webhook__bank__bank_id', 'event_type')
    ordering      = ('-created_at',)
    readonly_fields = ('created_at', 'completed_at')

    _STATUS_COLOURS = {
        'pending':  '#6b7280',
        'success':  '#10b981',
        'failed':   '#ef4444',
        'retrying': '#f59e0b',
    }

    def status_badge(self, obj):
        colour = self._STATUS_COLOURS.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{c};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">{s}</span>',
            c=colour, s=obj.status,
        )
    status_badge.short_description = 'Status'


# ===========================================================================
# UsageLog
# ===========================================================================

@admin.register(UsageLog)
class UsageLogAdmin(admin.ModelAdmin):
    list_display  = ('bank', 'date', 'calls_heat', 'unique_endpoint_count', 'peak_calls_hour')
    list_filter   = ('bank', 'date')
    ordering      = ('-date',)
    readonly_fields = ('created_at', 'updated_at')

    def calls_heat(self, obj):
        """Colour the call count green → amber → red based on usage %."""
        bank  = obj.bank
        pct   = (obj.api_calls / bank.daily_api_limit * 100) if bank.daily_api_limit else 0
        colour = '#10b981' if pct < 50 else ('#f59e0b' if pct < 80 else '#ef4444')
        return format_html(
            '<span style="color:{c};font-weight:bold">{n} <small>({p:.0f}%)</small></span>',
            c=colour, n=obj.api_calls, p=pct,
        )
    calls_heat.short_description = 'API Calls'

    def unique_endpoint_count(self, obj):
        return len(obj.unique_endpoints)
    unique_endpoint_count.short_description = 'Unique Endpoints'


# ===========================================================================
# BillingRecord
# ===========================================================================

@admin.register(BillingRecord)
class BillingRecordAdmin(admin.ModelAdmin):
    list_display  = ('bank', 'billing_month', 'subscription_tier', 'total_amount_display', 'status_badge', 'issued_at', 'paid_at')
    list_filter   = ('status', 'subscription_tier')
    search_fields = ('bank__bank_id', 'bank__name')
    ordering      = ('-billing_month',)
    readonly_fields = ('created_at', 'updated_at')

    actions = ('issue_selected_invoices',)

    _STATUS_COLOURS = {
        'draft':   '#6b7280',
        'issued':  '#3b82f6',
        'paid':    '#10b981',
        'overdue': '#ef4444',
    }

    def status_badge(self, obj):
        colour = self._STATUS_COLOURS.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{c};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">{s}</span>',
            c=colour, s=obj.status,
        )
    status_badge.short_description = 'Status'

    def total_amount_display(self, obj):
        return f'KES {obj.total_amount:,.2f}'
    total_amount_display.short_description = 'Total (KES)'

    def issue_selected_invoices(self, request, queryset):
        from .services.billing_service import BillingService
        issued = 0
        for rec in queryset.filter(status=BillingRecord.STATUS_DRAFT):
            BillingService.issue_invoice(rec)
            issued += 1
        self.message_user(request, f'Issued {issued} invoice(s).')
    issue_selected_invoices.short_description = 'Issue selected invoices'