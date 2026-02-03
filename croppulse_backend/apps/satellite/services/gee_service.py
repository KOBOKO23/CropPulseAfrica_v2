# apps/satellite/services/gee_service.py
#
# ---------------------------------------------------------------------------
# DEPRECATION NOTICE
# ---------------------------------------------------------------------------
# GoogleEarthEngineService was a duplicate of SentinelService with less
# error-handling, no fallback logic, and a date-arithmetic bug in
# calculate_ndvi (added a timedelta to a raw datetime without calling
# .isoformat() on the end_date).
#
# All Google Earth Engine interactions are now handled exclusively by
# SentinelService (sentinel_service.py).  This module is kept as a
# thin compatibility shim so that any stale imports
# ("from .services.gee_service import GoogleEarthEngineService")
# continue to resolve without error.
# ---------------------------------------------------------------------------

from .sentinel_service import SentinelService

# Alias — callers that still reference GoogleEarthEngineService get
# the fully-featured SentinelService instead.
GoogleEarthEngineService = SentinelService