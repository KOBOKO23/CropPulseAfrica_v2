# apps/banks/services/usage_tracker.py
# ---------------------------------------------------------------------------
# Per-request usage tracking + rate-limit gate.
#
# Architecture
# ------------
# Redis key   bank:usage:{bank_id}:{YYYY-MM-DD}   holds today's counter.
# INCR is atomic so concurrent workers never race.
# Every _FLUSH_INTERVAL_SECONDS the value is written back to the
# UsageLog row in Postgres.  The Celery task flush_all_to_db() is a
# safety-net that does the same on a schedule.
#
# If Redis is unavailable we fall back to a DB-level F()-increment
# (slightly slower but correct).
# ---------------------------------------------------------------------------

import logging
from datetime import date

from django.db.models import F
from django.utils import timezone

from ..models import Bank, UsageLog

logger = logging.getLogger(__name__)

_FLUSH_INTERVAL_SECONDS = 60   # opportunistic write-back cadence


# ---------------------------------------------------------------------------
# Redis accessor  –  gracefully degrades
# ---------------------------------------------------------------------------
def _cache():
    """Return Django's default cache backend (Redis when configured), or None."""
    try:
        from django.core.cache import cache
        return cache
    except Exception:                                         # pragma: no cover
        return None


class UsageTracker:
    """All methods are @staticmethod – no instance state."""

    # ------------------------------------------------------------------
    # cache-key helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _key(bank_id: str, day: date | None = None) -> str:
        return f'bank:usage:{bank_id}:{(day or timezone.now().date()).isoformat()}'

    @staticmethod
    def _flush_ts_key(bank_id: str) -> str:
        return f'bank:usage:flush:{bank_id}'

    # ------------------------------------------------------------------
    # track()  ← called by usage_tracker_middleware on every request
    # ------------------------------------------------------------------
    @staticmethod
    def track(bank: Bank, endpoint_path: str = '') -> int:
        """
        Increment today's counter.  Returns the new daily total.
        Also opportunistically flushes to Postgres.
        """
        cache  = _cache()
        today  = timezone.now().date()
        key    = UsageTracker._key(bank.bank_id, today)

        if cache:
            new_count = cache.incr(key, delta=1)      # creates key at 0 + 1 if absent
            cache.set(key, new_count, 60 * 60 * 48)   # TTL 48 h

            # opportunistic flush
            ts_key     = UsageTracker._flush_ts_key(bank.bank_id)
            last_flush = cache.get(ts_key)
            now_ts     = int(timezone.now().timestamp())

            if last_flush is None or (now_ts - last_flush) >= _FLUSH_INTERVAL_SECONDS:
                UsageTracker._write_db(bank, today, new_count, endpoint_path)
                cache.set(ts_key, now_ts, 60 * 60 * 24)
        else:
            new_count = UsageTracker._db_increment(bank, today, endpoint_path)

        return new_count

    # ------------------------------------------------------------------
    # rate-limit check
    # ------------------------------------------------------------------
    @staticmethod
    def is_rate_limited(bank: Bank) -> bool:
        return UsageTracker.get_today_count(bank) >= bank.daily_api_limit

    @staticmethod
    def remaining_calls(bank: Bank) -> int:
        return max(0, bank.daily_api_limit - UsageTracker.get_today_count(bank))

    @staticmethod
    def get_today_count(bank: Bank, day: date | None = None) -> int:
        """Redis first, DB fallback."""
        day   = day or timezone.now().date()
        cache = _cache()
        if cache:
            val = cache.get(UsageTracker._key(bank.bank_id, day))
            if val is not None:
                return int(val)

        try:
            return UsageLog.objects.get(bank=bank, date=day).api_calls
        except UsageLog.DoesNotExist:
            return 0

    # ------------------------------------------------------------------
    # internal: write through to Postgres
    # ------------------------------------------------------------------
    @staticmethod
    def _write_db(bank: Bank, day: date, count: int, endpoint_path: str = ''):
        log, _ = UsageLog.objects.update_or_create(
            bank=bank, date=day,
            defaults={'api_calls': count},
        )
        if endpoint_path and endpoint_path not in log.unique_endpoints:
            log.unique_endpoints.append(endpoint_path)
            log.save(update_fields=['unique_endpoints', 'updated_at'])

    @staticmethod
    def _db_increment(bank: Bank, day: date, endpoint_path: str = '') -> int:
        """Atomic F()-increment – used when Redis is unavailable."""
        log, created = UsageLog.objects.get_or_create(bank=bank, date=day)
        if created:
            log.api_calls = 1
            log.save(update_fields=['api_calls'])
        else:
            UsageLog.objects.filter(pk=log.pk).update(api_calls=F('api_calls') + 1)
            log.refresh_from_db()

        if endpoint_path and endpoint_path not in log.unique_endpoints:
            log.unique_endpoints.append(endpoint_path)
            log.save(update_fields=['unique_endpoints', 'updated_at'])

        return log.api_calls

    # ------------------------------------------------------------------
    # bulk flush  (Celery beat entry-point)
    # ------------------------------------------------------------------
    @staticmethod
    def flush_all_to_db() -> int:
        """Walk every active bank, read Redis, write Postgres."""
        cache  = _cache()
        if not cache:                                         # pragma: no cover
            return 0

        today  = timezone.now().date()
        count  = 0
        for bank in Bank.objects.filter(is_active=True):
            val = cache.get(UsageTracker._key(bank.bank_id, today))
            if val is not None:
                UsageTracker._write_db(bank, today, int(val))
                count += 1

        logger.info('Flushed usage for %d bank(s)', count)
        return count