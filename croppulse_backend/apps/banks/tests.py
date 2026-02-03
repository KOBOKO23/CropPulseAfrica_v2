# apps/banks/tests.py

import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient, force_authenticate

from apps.accounts.models import User
from .models import (
    Bank, APIKey, Webhook, WebhookDelivery, UsageLog, BillingRecord,
    TIER_BASIC, TIER_PRO, TIER_ENTERPRISE,
)
from .services.api_key_service  import APIKeyService
from .services.billing_service  import BillingService, TIER_PRICING
from .services.usage_tracker    import UsageTracker
from .services.webhook_service  import WebhookService


# ===========================================================================
# Shared factory helpers
# ===========================================================================

def _make_user(username='bankuser', email='bank@test.com'):
    return User.objects.create_user(
        username=username, email=email, password='Str0ng!Pass'
    )


def _make_bank(user=None, bank_id='BANK001', tier=TIER_BASIC):
    user = user or _make_user()
    return Bank.objects.create(
        user=user,
        bank_id=bank_id,
        name='Test Bank',
        registration_number='REG-001',
        subscription_tier=tier,
    )


def _make_webhook(bank, name='hook1', url='https://example.com/hook'):
    secret = 'testsecret12345678901234567890ab'
    return Webhook.objects.create(
        bank=bank,
        name=name,
        url=url,
        signing_secret_hash=hashlib.sha256(secret.encode()).hexdigest(),
        secret_prefix=secret[:8],
        subscribed_events=[],
        max_retries=3,
    ), secret


# ===========================================================================
# Model tests
# ===========================================================================

class BankModelTestCase(TestCase):
    def setUp(self):
        self.bank = _make_bank(tier=TIER_PRO)

    def test_str(self):
        self.assertIn('BANK001', str(self.bank))

    def test_tier_limits_property(self):
        self.assertEqual(self.bank.daily_api_limit, 2_000)
        self.assertEqual(self.bank.max_webhooks, 5)
        self.assertEqual(self.bank.max_api_keys, 10)

    def test_unknown_tier_falls_back_to_basic(self):
        self.bank.subscription_tier = 'unknown_tier'
        self.assertEqual(self.bank.daily_api_limit, 500)

    def test_active_api_key_count(self):
        APIKey.objects.create(
            bank=self.bank, name='k1', key_prefix='aaaa1111',
            key_hash='a' * 64, status='active', permissions=[],
        )
        APIKey.objects.create(
            bank=self.bank, name='k2', key_prefix='bbbb2222',
            key_hash='b' * 64, status='revoked', permissions=[],
        )
        self.assertEqual(self.bank.active_api_key_count(), 1)


class APIKeyModelTestCase(TestCase):
    def setUp(self):
        self.bank = _make_bank()
        self.key  = APIKey.objects.create(
            bank=self.bank, name='test', key_prefix='abcd1234',
            key_hash='c' * 64, permissions=['read_farmers'],
        )

    def test_is_active_true_by_default(self):
        self.assertTrue(self.key.is_active)

    def test_is_active_false_when_revoked(self):
        self.key.status = APIKey.STATUS_REVOKED
        self.assertFalse(self.key.is_active)

    def test_is_active_false_when_expired(self):
        self.key.expires_at = timezone.now() - timedelta(hours=1)
        self.assertFalse(self.key.is_active)

    def test_has_permission(self):
        self.assertTrue(self.key.has_permission('read_farmers'))
        self.assertFalse(self.key.has_permission('write_loans'))

    def test_clean_rejects_bad_permissions(self):
        self.key.permissions = ['read_farmers', 'fly_rockets']
        with self.assertRaises(Exception):
            self.key.clean()


class WebhookModelTestCase(TestCase):
    def setUp(self):
        self.bank = _make_bank(tier=TIER_PRO)  # allows 5 webhooks

    def test_is_subscribed_to_all_when_empty(self):
        wh, _ = _make_webhook(self.bank)
        self.assertTrue(wh.is_subscribed_to('scan.completed'))

    def test_is_subscribed_to_specific_event(self):
        wh, _ = _make_webhook(self.bank)
        wh.subscribed_events = ['scan.completed']
        self.assertTrue(wh.is_subscribed_to('scan.completed'))
        self.assertFalse(wh.is_subscribed_to('loan.approved'))

    def test_clean_rejects_non_https(self):
        wh, _ = _make_webhook(self.bank)
        wh.url = 'http://insecure.example.com'
        with self.assertRaises(Exception):
            wh.clean()

    def test_clean_rejects_unknown_events(self):
        wh, _ = _make_webhook(self.bank)
        wh.subscribed_events = ['not_a_real_event']
        with self.assertRaises(Exception):
            wh.clean()


class UsageLogModelTestCase(TestCase):
    def test_unique_together(self):
        bank = _make_bank()
        UsageLog.objects.create(bank=bank, date=date.today(), api_calls=10)
        with self.assertRaises(Exception):
            UsageLog.objects.create(bank=bank, date=date.today(), api_calls=5)


class BillingRecordModelTestCase(TestCase):
    def test_unique_together(self):
        bank = _make_bank()
        BillingRecord.objects.create(
            bank=bank,
            billing_month=date(2025, 1, 1),
            subscription_tier=TIER_BASIC,
            base_amount=Decimal('5000'),
            total_amount=Decimal('5000'),
        )
        with self.assertRaises(Exception):
            BillingRecord.objects.create(
                bank=bank,
                billing_month=date(2025, 1, 1),
                subscription_tier=TIER_BASIC,
                base_amount=Decimal('5000'),
                total_amount=Decimal('5000'),
            )


# ===========================================================================
# APIKeyService tests
# ===========================================================================

class APIKeyServiceTestCase(TestCase):
    def setUp(self):
        self.bank = _make_bank()

    # --- create -----------------------------------------------------------
    def test_create_returns_raw_key(self):
        result = APIKeyService.create(self.bank, name='svc-key', permissions=['read_farms'])
        self.assertIn('raw_key', result)
        self.assertEqual(len(result['raw_key']), 64)   # 32 bytes → 64 hex chars
        self.assertEqual(result['key_prefix'], result['raw_key'][:8])

    def test_create_persists_hashed_key(self):
        result = APIKeyService.create(self.bank, name='svc-key')
        obj    = APIKey.objects.get(pk=result['id'])
        expected_hash = hashlib.sha256(result['raw_key'].encode()).hexdigest()
        self.assertEqual(obj.key_hash, expected_hash)

    def test_create_with_expiry(self):
        result = APIKeyService.create(self.bank, name='exp-key', expires_in_days=7)
        obj    = APIKey.objects.get(pk=result['id'])
        self.assertIsNotNone(obj.expires_at)
        self.assertAlmostEqual(
            (obj.expires_at - timezone.now()).days, 7, delta=1
        )

    # --- validate ---------------------------------------------------------
    def test_validate_returns_key_on_valid_token(self):
        result = APIKeyService.create(self.bank, name='v-key')
        obj    = APIKeyService.validate(result['raw_key'])
        self.assertIsNotNone(obj)
        self.assertEqual(obj.bank, self.bank)

    def test_validate_returns_none_on_garbage(self):
        self.assertIsNone(APIKeyService.validate('not-a-real-token'))

    def test_validate_returns_none_on_revoked(self):
        result = APIKeyService.create(self.bank, name='rv-key')
        obj    = APIKey.objects.get(pk=result['id'])
        APIKeyService.revoke(obj)
        self.assertIsNone(APIKeyService.validate(result['raw_key']))

    def test_validate_stamps_last_used_at(self):
        result  = APIKeyService.create(self.bank, name='lu-key')
        before  = timezone.now()
        APIKeyService.validate(result['raw_key'])
        obj     = APIKey.objects.get(pk=result['id'])
        self.assertIsNotNone(obj.last_used_at)
        self.assertGreaterEqual(obj.last_used_at, before)

    # --- revoke -----------------------------------------------------------
    def test_revoke_sets_status_and_timestamp(self):
        result = APIKeyService.create(self.bank, name='rev-key')
        obj    = APIKey.objects.get(pk=result['id'])
        APIKeyService.revoke(obj)
        obj.refresh_from_db()
        self.assertEqual(obj.status, APIKey.STATUS_REVOKED)
        self.assertIsNotNone(obj.revoked_at)

    # --- rotate -----------------------------------------------------------
    def test_rotate_revokes_old_and_creates_new(self):
        result  = APIKeyService.create(self.bank, name='rot-key', permissions=['read_farms'])
        old_obj = APIKey.objects.get(pk=result['id'])
        new     = APIKeyService.rotate(old_obj)

        old_obj.refresh_from_db()
        self.assertEqual(old_obj.status, APIKey.STATUS_REVOKED)

        self.assertIn('raw_key', new)
        self.assertNotEqual(new['raw_key'], result['raw_key'])
        self.assertEqual(new['name'], 'rot-key')
        self.assertEqual(new['permissions'], ['read_farms'])

    # --- expire_stale_keys ------------------------------------------------
    def test_expire_stale_keys(self):
        result = APIKeyService.create(self.bank, name='exp-key', expires_in_days=1)
        obj    = APIKey.objects.get(pk=result['id'])
        # Backdate expires_at
        obj.expires_at = timezone.now() - timedelta(hours=2)
        obj.save()

        count = APIKeyService.expire_stale_keys()
        self.assertEqual(count, 1)

        obj.refresh_from_db()
        self.assertEqual(obj.status, APIKey.STATUS_EXPIRED)


# ===========================================================================
# BillingService tests
# ===========================================================================

class BillingServiceTestCase(TestCase):
    def setUp(self):
        self.bank = _make_bank(tier=TIER_PRO)

    def _seed_usage(self, year, month, calls_per_day):
        """Create UsageLog rows for every day in a given month."""
        import calendar
        days = calendar.monthrange(year, month)[1]
        for d in range(1, days + 1):
            UsageLog.objects.create(
                bank=self.bank,
                date=date(year, month, d),
                api_calls=calls_per_day,
            )

    def test_generate_no_overage(self):
        # PRO allows 2 000/day × 31 days = 62 000.  Use 1 000/day.
        self._seed_usage(2025, 1, 1_000)
        rec = BillingService.generate_monthly_invoice(self.bank, billing_month=date(2025, 1, 1))

        self.assertEqual(rec.total_api_calls, 31_000)
        self.assertEqual(rec.overage_calls,   0)
        self.assertEqual(rec.base_amount,     TIER_PRICING[TIER_PRO]['base_fee'])
        self.assertEqual(rec.overage_amount,  Decimal('0'))
        self.assertEqual(rec.status,          BillingRecord.STATUS_DRAFT)

    def test_generate_with_overage(self):
        # 3 000 calls/day × 31 = 93 000.  Allowance = 62 000.  Overage = 31 000.
        self._seed_usage(2025, 1, 3_000)
        rec = BillingService.generate_monthly_invoice(self.bank, billing_month=date(2025, 1, 1))

        self.assertEqual(rec.overage_calls, 31_000)
        expected_overage = (Decimal(31_000) / Decimal(1_000)) * TIER_PRICING[TIER_PRO]['overage_per_1000']
        self.assertEqual(rec.overage_amount, expected_overage)

    def test_generate_is_idempotent(self):
        self._seed_usage(2025, 2, 100)
        r1 = BillingService.generate_monthly_invoice(self.bank, billing_month=date(2025, 2, 1))
        r2 = BillingService.generate_monthly_invoice(self.bank, billing_month=date(2025, 2, 1))
        self.assertEqual(r1.pk, r2.pk)

    # --- status transitions -----------------------------------------------
    def test_issue_invoice(self):
        self._seed_usage(2025, 3, 10)
        rec = BillingService.generate_monthly_invoice(self.bank, billing_month=date(2025, 3, 1))
        rec = BillingService.issue_invoice(rec)
        self.assertEqual(rec.status, BillingRecord.STATUS_ISSUED)
        self.assertIsNotNone(rec.issued_at)

    def test_issue_rejects_non_draft(self):
        self._seed_usage(2025, 3, 10)
        rec = BillingService.generate_monthly_invoice(self.bank, billing_month=date(2025, 3, 1))
        BillingService.issue_invoice(rec)
        with self.assertRaises(ValueError):
            BillingService.issue_invoice(rec)   # already issued

    def test_mark_paid(self):
        self._seed_usage(2025, 4, 10)
        rec = BillingService.generate_monthly_invoice(self.bank, billing_month=date(2025, 4, 1))
        BillingService.issue_invoice(rec)
        rec = BillingService.mark_paid(rec, notes='Wire transfer #123')
        self.assertEqual(rec.status, BillingRecord.STATUS_PAID)
        self.assertEqual(rec.notes,  'Wire transfer #123')

    def test_mark_paid_rejects_draft(self):
        self._seed_usage(2025, 5, 10)
        rec = BillingService.generate_monthly_invoice(self.bank, billing_month=date(2025, 5, 1))
        with self.assertRaises(ValueError):
            BillingService.mark_paid(rec)

    def test_mark_overdue(self):
        self._seed_usage(2025, 6, 10)
        rec = BillingService.generate_monthly_invoice(self.bank, billing_month=date(2025, 6, 1))
        BillingService.issue_invoice(rec)
        rec = BillingService.mark_overdue(rec)
        self.assertEqual(rec.status, BillingRecord.STATUS_OVERDUE)

    def test_flag_overdue_invoices(self):
        self._seed_usage(2025, 7, 10)
        rec = BillingService.generate_monthly_invoice(self.bank, billing_month=date(2025, 7, 1))
        BillingService.issue_invoice(rec)
        # Backdate issued_at
        rec.issued_at = timezone.now() - timedelta(days=35)
        rec.save()

        count = BillingService.flag_overdue_invoices(days_overdue=30)
        self.assertEqual(count, 1)
        rec.refresh_from_db()
        self.assertEqual(rec.status, BillingRecord.STATUS_OVERDUE)


# ===========================================================================
# UsageTracker tests
# ===========================================================================

class UsageTrackerTestCase(TestCase):
    def setUp(self):
        self.bank = _make_bank(tier=TIER_PRO)   # 2 000 calls/day

    @patch('apps.banks.services.usage_tracker._cache', return_value=None)
    def test_track_db_only_increments(self, _mock_cache):
        """When Redis is gone we fall back to DB F()-increment."""
        count1 = UsageTracker.track(self.bank, endpoint_path='/api/v1/test/')
        count2 = UsageTracker.track(self.bank, endpoint_path='/api/v1/test/')
        self.assertEqual(count1, 1)
        self.assertEqual(count2, 2)

    @patch('apps.banks.services.usage_tracker._cache', return_value=None)
    def test_get_today_count_db_fallback(self, _mock_cache):
        UsageLog.objects.create(bank=self.bank, date=date.today(), api_calls=42)
        self.assertEqual(UsageTracker.get_today_count(self.bank), 42)

    @patch('apps.banks.services.usage_tracker._cache', return_value=None)
    def test_get_today_count_zero_when_no_log(self, _mock_cache):
        self.assertEqual(UsageTracker.get_today_count(self.bank), 0)

    @patch('apps.banks.services.usage_tracker._cache', return_value=None)
    def test_is_rate_limited_false_under_limit(self, _mock_cache):
        UsageLog.objects.create(bank=self.bank, date=date.today(), api_calls=100)
        self.assertFalse(UsageTracker.is_rate_limited(self.bank))

    @patch('apps.banks.services.usage_tracker._cache', return_value=None)
    def test_is_rate_limited_true_at_limit(self, _mock_cache):
        UsageLog.objects.create(bank=self.bank, date=date.today(), api_calls=2_000)
        self.assertTrue(UsageTracker.is_rate_limited(self.bank))

    @patch('apps.banks.services.usage_tracker._cache', return_value=None)
    def test_remaining_calls(self, _mock_cache):
        UsageLog.objects.create(bank=self.bank, date=date.today(), api_calls=500)
        self.assertEqual(UsageTracker.remaining_calls(self.bank), 1_500)

    @patch('apps.banks.services.usage_tracker._cache', return_value=None)
    def test_remaining_calls_never_negative(self, _mock_cache):
        UsageLog.objects.create(bank=self.bank, date=date.today(), api_calls=9_999)
        self.assertEqual(UsageTracker.remaining_calls(self.bank), 0)

    @patch('apps.banks.services.usage_tracker._cache', return_value=None)
    def test_track_records_unique_endpoints(self, _mock_cache):
        UsageTracker.track(self.bank, endpoint_path='/a/')
        UsageTracker.track(self.bank, endpoint_path='/b/')
        UsageTracker.track(self.bank, endpoint_path='/a/')   # duplicate – should not be added again
        log = UsageLog.objects.get(bank=self.bank, date=date.today())
        self.assertIn('/a/', log.unique_endpoints)
        self.assertIn('/b/', log.unique_endpoints)
        self.assertEqual(log.unique_endpoints.count('/a/'), 1)


# ===========================================================================
# WebhookService tests
# ===========================================================================

class WebhookServiceTestCase(TestCase):
    def setUp(self):
        self.bank = _make_bank(tier=TIER_PRO)

    # --- create -----------------------------------------------------------
    def test_create_returns_raw_secret(self):
        data = WebhookService.create(
            bank=self.bank, name='hook', url='https://example.com/wh',
        )
        self.assertIn('raw_signing_secret', data)
        self.assertEqual(len(data['raw_signing_secret']), 64)

    def test_create_with_user_provided_secret(self):
        secret = 'my_custom_secret_value_here_1234567890'
        data   = WebhookService.create(
            bank=self.bank, name='hook2', url='https://example.com/wh2',
            signing_secret=secret,
        )
        self.assertEqual(data['raw_signing_secret'], secret)
        wh = Webhook.objects.get(pk=data['id'])
        self.assertEqual(wh.signing_secret_hash, hashlib.sha256(secret.encode()).hexdigest())

    def test_create_persists_subscribed_events(self):
        data = WebhookService.create(
            bank=self.bank, name='hook3', url='https://example.com/wh3',
            subscribed_events=['scan.completed', 'loan.approved'],
        )
        wh = Webhook.objects.get(pk=data['id'])
        self.assertEqual(wh.subscribed_events, ['scan.completed', 'loan.approved'])

    # --- rotate_secret ----------------------------------------------------
    def test_rotate_secret_changes_hash(self):
        data       = WebhookService.create(self.bank, name='rot', url='https://example.com/rot')
        wh         = Webhook.objects.get(pk=data['id'])
        old_hash   = wh.signing_secret_hash
        new_data   = WebhookService.rotate_secret(wh)
        wh.refresh_from_db()
        self.assertNotEqual(wh.signing_secret_hash, old_hash)
        self.assertEqual(wh.secret_prefix, new_data['raw_signing_secret'][:8])

    # --- enqueue_event ----------------------------------------------------
    def test_enqueue_creates_delivery_rows(self):
        WebhookService.create(self.bank, name='h1', url='https://a.com/h')
        WebhookService.create(self.bank, name='h2', url='https://b.com/h')
        count = WebhookService.enqueue_event('scan.completed', {'farm': 1}, self.bank)
        self.assertEqual(count, 2)
        self.assertEqual(WebhookDelivery.objects.count(), 2)

    def test_enqueue_respects_subscribed_events(self):
        # h1 listens to scan.completed only
        data = WebhookService.create(
            self.bank, name='h1', url='https://a.com/h',
            subscribed_events=['scan.completed'],
        )
        # h2 listens to loan.approved only
        WebhookService.create(
            self.bank, name='h2', url='https://b.com/h',
            subscribed_events=['loan.approved'],
        )
        count = WebhookService.enqueue_event('scan.completed', {}, self.bank)
        self.assertEqual(count, 1)

    # --- deliver ----------------------------------------------------------
    @patch('apps.banks.services.webhook_service.requests.post')
    def test_deliver_success(self, mock_post):
        mock_post.return_value = MagicMock(ok=True, status_code=200, text='OK')
        WebhookService.create(self.bank, name='d', url='https://x.com/d')
        WebhookService.enqueue_event('scan.completed', {'x': 1}, self.bank)
        delivery = WebhookDelivery.objects.first()

        result = WebhookService.deliver(delivery)
        self.assertTrue(result)

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.STATUS_SUCCESS)
        self.assertEqual(delivery.attempts, 1)
        self.assertIsNotNone(delivery.completed_at)

    @patch('apps.banks.services.webhook_service.requests.post')
    def test_deliver_failure_schedules_retry(self, mock_post):
        mock_post.return_value = MagicMock(ok=False, status_code=500, text='err')
        WebhookService.create(self.bank, name='d2', url='https://x.com/d2')
        WebhookService.enqueue_event('scan.failed', {}, self.bank)
        delivery = WebhookDelivery.objects.first()

        result = WebhookService.deliver(delivery)
        self.assertFalse(result)

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.STATUS_RETRYING)
        self.assertIsNotNone(delivery.next_retry_at)

    @patch('apps.banks.services.webhook_service.requests.post')
    def test_deliver_exhausts_retries(self, mock_post):
        mock_post.return_value = MagicMock(ok=False, status_code=503, text='down')
        WebhookService.create(self.bank, name='d3', url='https://x.com/d3', max_retries=2)
        WebhookService.enqueue_event('scan.failed', {}, self.bank)
        delivery = WebhookDelivery.objects.first()

        # Attempt 1 → retrying
        WebhookService.deliver(delivery)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.STATUS_RETRYING)

        # Attempt 2 → failed (max_retries=2)
        WebhookService.deliver(delivery)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.STATUS_FAILED)
        self.assertEqual(delivery.attempts, 2)

    # --- signing ----------------------------------------------------------
    def test_sign_and_verify_round_trip(self):
        secret_hash = hashlib.sha256(b'mysecret').hexdigest()
        body        = '{"hello":"world"}'
        sig         = WebhookService._sign(body, secret_hash)
        self.assertTrue(WebhookService.verify_signature(body, sig, secret_hash))

    def test_verify_rejects_tampered_body(self):
        secret_hash = hashlib.sha256(b'mysecret').hexdigest()
        sig         = WebhookService._sign('{"hello":"world"}', secret_hash)
        self.assertFalse(WebhookService.verify_signature('{"hello":"tampered"}', sig, secret_hash))


# ===========================================================================
# API integration tests
# ===========================================================================

class BankProfileAPITestCase(APITestCase):
    def setUp(self):
        self.user = _make_user()
        self.bank = _make_bank(user=self.user, tier=TIER_PRO)
        self.client.force_authenticate(user=self.user)

    def test_get_profile(self):
        resp = self.client.get('/api/v1/banks/profile/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['bank_id'], 'BANK001')
        self.assertIn('tier_limits', resp.data)

    def test_patch_profile(self):
        resp = self.client.patch(
            '/api/v1/banks/profile/',
            {'contact_email': 'new@test.com'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.bank.refresh_from_db()
        self.assertEqual(self.bank.contact_email, 'new@test.com')


class APIKeyAPITestCase(APITestCase):
    def setUp(self):
        self.user = _make_user()
        self.bank = _make_bank(user=self.user, tier=TIER_PRO)
        self.client.force_authenticate(user=self.user)

    def test_list_empty(self):
        resp = self.client.get('/api/v1/banks/api-keys/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)

    def test_create_key(self):
        resp = self.client.post(
            '/api/v1/banks/api-keys/create/',
            {'name': 'mobile', 'permissions': ['read_farms']},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn('raw_key', resp.data)
        self.assertEqual(resp.data['permissions'], ['read_farms'])

    def test_create_key_invalid_permission(self):
        resp = self.client.post(
            '/api/v1/banks/api-keys/create/',
            {'name': 'bad', 'permissions': ['fly_rockets']},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_revoke_key(self):
        create_resp = self.client.post(
            '/api/v1/banks/api-keys/create/',
            {'name': 'rev', 'permissions': []},
            format='json',
        )
        key_id = create_resp.data['id']
        resp   = self.client.post(f'/api/v1/banks/api-keys/{key_id}/revoke/')
        self.assertEqual(resp.status_code, 200)

        # second revoke should 400
        resp2 = self.client.post(f'/api/v1/banks/api-keys/{key_id}/revoke/')
        self.assertEqual(resp2.status_code, 400)

    def test_rotate_key(self):
        create_resp = self.client.post(
            '/api/v1/banks/api-keys/create/',
            {'name': 'rot', 'permissions': ['read_farms']},
            format='json',
        )
        key_id  = create_resp.data['id']
        old_raw = create_resp.data['raw_key']

        resp = self.client.post(f'/api/v1/banks/api-keys/{key_id}/rotate/')
        self.assertEqual(resp.status_code, 201)
        self.assertNotEqual(resp.data['raw_key'], old_raw)
        self.assertEqual(resp.data['name'], 'rot')

    def test_rate_limit_headers_present(self):
        resp = self.client.get('/api/v1/banks/api-keys/')
        self.assertIn('X-RateLimit-Limit',     resp)
        self.assertIn('X-RateLimit-Remaining', resp)


class WebhookAPITestCase(APITestCase):
    def setUp(self):
        self.user = _make_user()
        self.bank = _make_bank(user=self.user, tier=TIER_PRO)
        self.client.force_authenticate(user=self.user)

    def test_list_empty(self):
        resp = self.client.get('/api/v1/banks/webhooks/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)

    def test_create_webhook(self):
        resp = self.client.post(
            '/api/v1/banks/webhooks/create/',
            {
                'name': 'loan-hook',
                'url':  'https://myapp.io/webhooks/loans',
                'subscribed_events': ['loan.approved'],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn('raw_signing_secret', resp.data)
        self.assertEqual(resp.data['subscribed_events'], ['loan.approved'])

    def test_create_webhook_rejects_http(self):
        resp = self.client.post(
            '/api/v1/banks/webhooks/create/',
            {'name': 'bad', 'url': 'http://insecure.com/hook'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_update_webhook(self):
        create_resp = self.client.post(
            '/api/v1/banks/webhooks/create/',
            {'name': 'upd', 'url': 'https://x.com/h'},
            format='json',
        )
        wh_id = create_resp.data['id']
        resp  = self.client.patch(
            f'/api/v1/banks/webhooks/{wh_id}/',
            {'name': 'updated-name'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)

    def test_delete_webhook(self):
        create_resp = self.client.post(
            '/api/v1/banks/webhooks/create/',
            {'name': 'del', 'url': 'https://x.com/h'},
            format='json',
        )
        wh_id = create_resp.data['id']
        resp  = self.client.delete(f'/api/v1/banks/webhooks/{wh_id}/')
        self.assertEqual(resp.status_code, 204)

    def test_rotate_secret(self):
        create_resp = self.client.post(
            '/api/v1/banks/webhooks/create/',
            {'name': 'rot', 'url': 'https://x.com/h'},
            format='json',
        )
        wh_id      = create_resp.data['id']
        old_prefix = create_resp.data['secret_prefix']

        resp = self.client.post(f'/api/v1/banks/webhooks/{wh_id}/rotate-secret/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('raw_signing_secret', resp.data)


class UsageAPITestCase(APITestCase):
    def setUp(self):
        self.user = _make_user()
        self.bank = _make_bank(user=self.user, tier=TIER_PRO)
        self.client.force_authenticate(user=self.user)

    def test_usage_summary(self):
        resp = self.client.get('/api/v1/banks/usage/summary/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['daily_limit'], 2_000)
        self.assertIn('calls_today', resp.data)
        self.assertIn('remaining_today', resp.data)

    def test_usage_list(self):
        UsageLog.objects.create(bank=self.bank, date=date.today(), api_calls=55)
        resp = self.client.get('/api/v1/banks/usage/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['api_calls'], 55)


class BillingAPITestCase(APITestCase):
    def setUp(self):
        self.user = _make_user()
        self.bank = _make_bank(user=self.user, tier=TIER_PRO)
        self.client.force_authenticate(user=self.user)

    def test_billing_list_empty(self):
        resp = self.client.get('/api/v1/banks/billing/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)

    def test_billing_list_with_record(self):
        BillingRecord.objects.create(
            bank=self.bank,
            billing_month=date(2025, 1, 1),
            subscription_tier=TIER_PRO,
            base_amount=Decimal('15000'),
            total_amount=Decimal('15000'),
        )
        resp = self.client.get('/api/v1/banks/billing/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_billing_detail(self):
        rec = BillingRecord.objects.create(
            bank=self.bank,
            billing_month=date(2025, 2, 1),
            subscription_tier=TIER_PRO,
            base_amount=Decimal('15000'),
            total_amount=Decimal('15000'),
        )
        resp = self.client.get(f'/api/v1/banks/billing/{rec.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['billing_month'], '2025-02-01')