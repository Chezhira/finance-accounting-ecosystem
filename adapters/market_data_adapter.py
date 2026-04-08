"""
Market Data Adapter — Session 10
Interface + Live implementation using free-tier APIs:
  - ExchangeRate-API (FX rates) — free tier, no key needed for base endpoint
  - FRED (Federal Reserve Economic Data) — US rates, free API
  - Bank of Tanzania proxy (TZ rates) — scraped/cached fallback

Pattern: Adapter interface — swap mock ↔ live without changing agent code.
Usage: Instantiate LiveMarketDataAdapter, call .fetch(), inject result into agent.analyze(market_data=...)
"""

import os
import json
import time
import logging
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Base Interface
# ---------------------------------------------------------------------------

class MarketDataAdapter(ABC):
    """Abstract base — all implementations must satisfy this interface."""

    @abstractmethod
    def fetch(
        self,
        base_currency: str = "USD",
        target_currencies: list = None,
        include_us_rates: bool = True,
        include_tz_rates: bool = True
    ) -> dict:
        """
        Fetch live/mock market data.

        Returns dict with keys:
          fx_rates, us_rates, tz_rates, commodities, meta
        """
        pass

    @abstractmethod
    def get_fx_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Return spot rate from_currency → to_currency, or None if unavailable."""
        pass


# ---------------------------------------------------------------------------
# Mock Adapter (existing behaviour — used in tests + offline)
# ---------------------------------------------------------------------------

class MockMarketDataAdapter(MarketDataAdapter):
    """
    Returns static sandbox rates.
    Used for testing and offline mode.
    """

    MOCK_DATA = {
        "fx_rates": {
            "USD_TZS": 2530.00,
            "EUR_TZS": 2740.00,
            "GBP_TZS": 3180.00,
            "USD_EUR": 0.918,
            "USD_GBP": 0.791,
            "EUR_USD": 1.089,
            "GBP_USD": 1.264,
            "TZS_USD": 0.000395
        },
        "us_rates": {
            "fed_funds_rate": 4.33,
            "prime_rate": 7.50,
            "sofr_overnight": 4.31,
            "treasury_3m": 4.28,
            "treasury_6m": 4.22,
            "treasury_1y": 4.09,
            "treasury_2y": 3.97,
            "treasury_5y": 3.96,
            "treasury_10y": 4.18,
            "treasury_30y": 4.49
        },
        "tz_rates": {
            "bot_policy_rate": 6.00,
            "interbank_rate": 6.25,
            "tbill_91_day": 7.30,
            "tbill_182_day": 8.10,
            "tbill_364_day": 9.50
        },
        "commodities": {},
        "meta": {
            "source": "mock",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "Static sandbox data — not live rates"
        }
    }

    def fetch(self, base_currency="USD", target_currencies=None, include_us_rates=True, include_tz_rates=True) -> dict:
        return dict(self.MOCK_DATA)

    def get_fx_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        key = f"{from_currency}_{to_currency}"
        return self.MOCK_DATA["fx_rates"].get(key)


# ---------------------------------------------------------------------------
# Live Adapter
# ---------------------------------------------------------------------------

class LiveMarketDataAdapter(MarketDataAdapter):
    """
    Live market data adapter using free-tier public APIs:

    1. ExchangeRate-API (open.er-api.com) — no API key required for basic FX
       Endpoint: https://open.er-api.com/v6/latest/{base}
       Limit: ~1,500 requests/month free

    2. FRED (Federal Reserve Economic Data) — free, requires free API key
       API key stored in .env as FRED_API_KEY
       Endpoint: https://api.stlouisfed.org/fred/series/observations
       Key series: FEDFUNDS, DPRIME, SOFR, DGS3MO, DGS6MO, DGS1, DGS2, DGS5, DGS10, DGS30

    3. Bank of Tanzania — no official public JSON API.
       We use a cached fallback with last known rates + staleness flag.
       If FRED_API_KEY is set, we also fetch USD/TZS from FRED (series: DEXTZUS)

    Offline fallback: If any fetch fails, returns MockMarketDataAdapter data
    with a staleness warning in meta.
    """

    EXCHANGERATE_BASE_URL = "https://open.er-api.com/v6/latest"
    FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    # FRED series IDs for US rates
    FRED_SERIES = {
        "fed_funds_rate": "FEDFUNDS",
        "prime_rate": "DPRIME",
        "sofr_overnight": "SOFR",
        "treasury_3m": "DGS3MO",
        "treasury_6m": "DGS6MO",
        "treasury_1y": "DGS1",
        "treasury_2y": "DGS2",
        "treasury_5y": "DGS5",
        "treasury_10y": "DGS10",
        "treasury_30y": "DGS30"
    }

    # Tanzania T-bill series (FRED has limited TZ data — use cached fallback)
    TZ_RATE_CACHE = {
        "bot_policy_rate": 6.00,
        "interbank_rate": 6.25,
        "tbill_91_day": 7.30,
        "tbill_182_day": 8.10,
        "tbill_364_day": 9.50,
        "_cache_note": "Bank of Tanzania rates — cached (no public JSON API). Update manually when BoT announces changes."
    }

    def __init__(
        self,
        fred_api_key: str = None,
        timeout_seconds: int = 8,
        fallback_on_error: bool = True
    ):
        """
        Args:
            fred_api_key: FRED API key (free at fred.stlouisfed.org).
                          If None, reads from env FRED_API_KEY.
                          If still None, FRED calls are skipped.
            timeout_seconds: HTTP request timeout
            fallback_on_error: If True, returns mock data on any fetch failure
        """
        self.fred_api_key = fred_api_key or os.getenv("FRED_API_KEY", "")
        self.timeout = timeout_seconds
        self.fallback_on_error = fallback_on_error
        self._mock = MockMarketDataAdapter()
        self._cache = {}  # in-memory cache for this session

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch(
        self,
        base_currency: str = "USD",
        target_currencies: list = None,
        include_us_rates: bool = True,
        include_tz_rates: bool = True
    ) -> dict:
        """
        Fetch live market data.

        Args:
            base_currency: Base currency for FX rates (default USD)
            target_currencies: List of target currencies to include
                               (None = all available from API)
            include_us_rates: Fetch FRED US interest rates
            include_tz_rates: Include Tanzania rates (cached fallback)

        Returns:
            {
                "fx_rates": {...},
                "us_rates": {...},
                "tz_rates": {...},
                "commodities": {},
                "meta": {
                    "source": "live|mixed|fallback",
                    "timestamp": "...",
                    "fx_source": "exchangerate-api.com",
                    "us_rates_source": "FRED",
                    "tz_rates_source": "cached",
                    "warnings": [...]
                }
            }
        """
        result = {
            "fx_rates": {},
            "us_rates": {},
            "tz_rates": {},
            "commodities": {},
            "meta": {
                "source": "live",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fx_source": None,
                "us_rates_source": None,
                "tz_rates_source": None,
                "warnings": []
            }
        }

        # --- FX Rates ---
        try:
            fx = self._fetch_fx_rates(base_currency, target_currencies)
            result["fx_rates"] = fx
            result["meta"]["fx_source"] = "open.er-api.com (live)"
        except Exception as e:
            logger.warning(f"FX fetch failed: {e}")
            result["meta"]["warnings"].append(f"FX rates unavailable (live) — using mock fallback: {e}")
            result["fx_rates"] = self._mock.MOCK_DATA["fx_rates"]
            result["meta"]["fx_source"] = "mock (fallback)"
            result["meta"]["source"] = "mixed"

        # --- US Rates (FRED) ---
        if include_us_rates:
            if self.fred_api_key:
                try:
                    us_rates = self._fetch_fred_rates()
                    result["us_rates"] = us_rates
                    result["meta"]["us_rates_source"] = "FRED (live)"
                except Exception as e:
                    logger.warning(f"FRED fetch failed: {e}")
                    result["meta"]["warnings"].append(f"US rates unavailable (FRED) — using mock fallback: {e}")
                    result["us_rates"] = self._mock.MOCK_DATA["us_rates"]
                    result["meta"]["us_rates_source"] = "mock (fallback)"
                    result["meta"]["source"] = "mixed"
            else:
                result["us_rates"] = self._mock.MOCK_DATA["us_rates"]
                result["meta"]["us_rates_source"] = "mock (no FRED_API_KEY set)"
                result["meta"]["warnings"].append(
                    "FRED_API_KEY not set — using sandbox US rates. "
                    "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
                )
                result["meta"]["source"] = "mixed"

        # --- TZ Rates (cached) ---
        if include_tz_rates:
            tz_rates = dict(self.TZ_RATE_CACHE)
            # Try to get USD/TZS from FRED if key is available
            if self.fred_api_key:
                try:
                    tzs_rate = self._fetch_fred_single("DEXTZUS")
                    if tzs_rate:
                        tz_rates["usd_tzs_fred"] = tzs_rate
                        tz_rates["_fred_note"] = "USD/TZS from FRED DEXTZUS series"
                except Exception as e:
                    logger.debug(f"FRED DEXTZUS fetch failed: {e}")
            result["tz_rates"] = tz_rates
            result["meta"]["tz_rates_source"] = "cached (BoT — no public JSON API)"

        # Determine overall source
        warnings = result["meta"]["warnings"]
        if not warnings:
            result["meta"]["source"] = "live"
        elif len(warnings) >= 2:
            result["meta"]["source"] = "fallback"

        return result

    def get_fx_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Return spot rate. Tries live first, falls back to mock."""
        try:
            data = self._fetch_fx_rates(from_currency, [to_currency])
            return data.get(f"{from_currency}_{to_currency}")
        except Exception:
            return self._mock.get_fx_rate(from_currency, to_currency)

    # ------------------------------------------------------------------
    # Private fetch helpers
    # ------------------------------------------------------------------

    def _http_get(self, url: str) -> dict:
        """Simple HTTP GET — returns parsed JSON dict."""
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "FinOps-Ecosystem/1.0 (internal market data adapter)"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)

    def _fetch_fx_rates(self, base: str, targets: list = None) -> dict:
        """
        Fetch FX rates from open.er-api.com (free, no key needed).
        Returns flat dict: {"USD_TZS": 2530.5, "USD_EUR": 0.918, ...}
        """
        cache_key = f"fx_{base}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < 3600:  # 1-hour cache
                return cached_data

        url = f"{self.EXCHANGERATE_BASE_URL}/{base}"
        data = self._http_get(url)

        if data.get("result") != "success":
            raise ValueError(f"ExchangeRate-API error: {data.get('error-type', 'unknown')}")

        rates_raw = data.get("rates", {})

        # Build flat dict: BASE_TARGET → rate
        flat = {}
        for target, rate in rates_raw.items():
            flat[f"{base}_{target}"] = rate
            # Also add inverse for convenience
            if rate > 0:
                flat[f"{target}_{base}"] = round(1 / rate, 8)

        if targets:
            flat = {k: v for k, v in flat.items()
                    if any(t in k for t in targets)}

        self._cache[cache_key] = (time.time(), flat)
        return flat

    def _fetch_fred_rates(self) -> dict:
        """Fetch all US interest rate series from FRED."""
        result = {}
        for label, series_id in self.FRED_SERIES.items():
            try:
                val = self._fetch_fred_single(series_id)
                if val is not None:
                    result[label] = val
            except Exception as e:
                logger.debug(f"FRED series {series_id} failed: {e}")
                # Fall back to mock value for this series
                result[label] = self._mock.MOCK_DATA["us_rates"].get(label)

        return result

    def _fetch_fred_single(self, series_id: str) -> Optional[float]:
        """
        Fetch the latest observation for a FRED series.
        Returns float value or None.
        """
        cache_key = f"fred_{series_id}"
        if cache_key in self._cache:
            cached_time, cached_val = self._cache[cache_key]
            if time.time() - cached_time < 3600:
                return cached_val

        url = (
            f"{self.FRED_BASE_URL}"
            f"?series_id={series_id}"
            f"&api_key={self.fred_api_key}"
            f"&file_type=json"
            f"&sort_order=desc"
            f"&limit=1"
        )
        data = self._http_get(url)
        observations = data.get("observations", [])
        if not observations:
            return None

        latest = observations[0]
        val_str = latest.get("value", ".")
        if val_str == ".":
            # FRED uses "." for missing data — try second-to-last
            return None

        val = float(val_str)
        self._cache[cache_key] = (time.time(), val)
        return val


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_market_data_adapter(live: bool = True, fred_api_key: str = None) -> MarketDataAdapter:
    """
    Factory function.

    Args:
        live: If True, return LiveMarketDataAdapter. If False, return MockMarketDataAdapter.
        fred_api_key: Optional FRED API key override (reads .env if None)

    Usage in main.py:
        from adapters.market_data_adapter import get_market_data_adapter
        market_adapter = get_market_data_adapter(live=True)
        market_data = market_adapter.fetch()
        result = agent.analyze(..., market_data=market_data)
    """
    if live:
        return LiveMarketDataAdapter(fred_api_key=fred_api_key)
    return MockMarketDataAdapter()
