"""
utils/agent_utils.py
=====================
Shared utilities for all Finance & Accounting AI agents.

Covers:
  - Anthropic client caching (replaces per-call client creation in corp_finance_agents)
  - Timezone-aware datetime helpers (replaces deprecated datetime.utcnow())
  - Model validation (prevents silent failures from invalid env var model names)
  - Standard fallback result builders
  - Jurisdiction normalisation
  - Auto-escalation detection

Usage:
    from utils.agent_utils import (
        get_client,
        utc_now,
        utc_date,
        validate_model,
        build_error_result,
        normalise_jurisdiction,
        has_critical_flag,
    )
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported models
# ---------------------------------------------------------------------------

VALID_MODELS = {
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
}

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_STRATEGY_MODEL = "claude-opus-4-6"

# ---------------------------------------------------------------------------
# Client cache — one client per API key, reused across calls
# ---------------------------------------------------------------------------

_client_cache: dict[str, anthropic.Anthropic] = {}


def get_client(api_key: Optional[str] = None) -> anthropic.Anthropic:
    """
    Return a cached Anthropic client for the given API key.
    Reuses the same client across calls to preserve HTTP connection pooling.

    Args:
        api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.

    Returns:
        anthropic.Anthropic client instance.
    """
    key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    if key not in _client_cache:
        _client_cache[key] = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
    return _client_cache[key]


# ---------------------------------------------------------------------------
# Datetime helpers — replaces deprecated datetime.utcnow()
# ---------------------------------------------------------------------------

def utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware). Replaces datetime.utcnow()."""
    return datetime.now(timezone.utc)


def utc_date() -> str:
    """Return today's UTC date as YYYY-MM-DD string."""
    return datetime.now(timezone.utc).date().isoformat()


def utc_iso() -> str:
    """Return current UTC datetime as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def utc_year() -> int:
    """Return current UTC year as int."""
    return datetime.now(timezone.utc).year


def format_period(period: Optional[str] = None, fmt: str = "%B %Y") -> str:
    """
    Return period string, defaulting to current month/year if not provided.

    Args:
        period: Optional explicit period string (e.g. "Q1 2026").
        fmt:    strftime format for auto-generated period. Default: "April 2026".

    Returns:
        Period string.
    """
    return period or datetime.now(timezone.utc).strftime(fmt)


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------

def validate_model(model: str, fallback: str = DEFAULT_MODEL) -> str:
    """
    Validate a model string against the known valid set.
    Logs a warning and returns fallback if model is not recognised.

    Args:
        model:    Model string to validate.
        fallback: Model to use if validation fails.

    Returns:
        Validated model string.
    """
    if model not in VALID_MODELS:
        logger.warning(
            "Model '%s' is not in known valid set %s — falling back to '%s'",
            model, VALID_MODELS, fallback,
        )
        return fallback
    return model


def get_model_from_env(env_var: str, fallback: str = DEFAULT_MODEL) -> str:
    """
    Read a model name from an environment variable and validate it.

    Args:
        env_var: Environment variable name (e.g. "TAX_STRATEGY_MODEL").
        fallback: Default model if env var is not set or invalid.

    Returns:
        Validated model string.
    """
    model = os.getenv(env_var, fallback)
    return validate_model(model, fallback)


# ---------------------------------------------------------------------------
# Jurisdiction normalisation
# ---------------------------------------------------------------------------

_JURISDICTION_MAP = {
    "tanzania": "TZ",
    "tz": "TZ",
    "united states": "US",
    "us": "US",
    "usa": "US",
    "united_states": "US",
    "both": "BOTH",
    "cross-border": "BOTH",
    "cross_border": "BOTH",
}


def normalise_jurisdiction(raw: Optional[str], default: str = "TZ") -> str:
    """
    Normalise jurisdiction string to a standard code.

    Supported inputs (case-insensitive):
        Tanzania, TZ → "TZ"
        United States, US, USA → "US"
        Both, Cross-border → "BOTH"
        None / Unknown / empty → default

    Args:
        raw:     Raw jurisdiction string from caller or LLM output.
        default: Code to return when input is unrecognised. Default "TZ".

    Returns:
        Normalised jurisdiction code: "TZ", "US", or "BOTH".
    """
    if not raw or raw.strip().lower() in ("unknown", "none", ""):
        logger.debug("normalise_jurisdiction: empty/unknown input, defaulting to %s", default)
        return default

    key = raw.strip().lower()
    result = _JURISDICTION_MAP.get(key)
    if result is None:
        logger.warning(
            "normalise_jurisdiction: unrecognised jurisdiction '%s', defaulting to %s",
            raw, default,
        )
        return default
    return result


# ---------------------------------------------------------------------------
# Auto-escalation detection
# ---------------------------------------------------------------------------

def has_critical_flag(result: dict) -> bool:
    """
    Return True if the agent result contains any CRITICAL severity flag.
    Works with both 'flags' list formats used across the codebase:
      - {"severity": "CRITICAL", ...}  (accounting/tax agents)
      - {"level": "CRITICAL", ...}     (audit/FP&A agents)

    Args:
        result: Agent output dict.

    Returns:
        True if any CRITICAL flag is present.
    """
    flags = result.get("flags", [])
    for f in flags:
        sev = f.get("severity") or f.get("level") or ""
        if sev.upper() == "CRITICAL":
            return True
    return False


def has_critical_risk(result: dict) -> bool:
    """
    Return True if the agent result contains any CRITICAL risk in tax_risk_register.
    Used by TaxStrategyManagerAgent.

    Args:
        result: Agent output dict.

    Returns:
        True if any CRITICAL risk score is present.
    """
    risks = result.get("tax_risk_register", [])
    return any(r.get("risk_score", "").upper() == "CRITICAL" for r in risks)


# ---------------------------------------------------------------------------
# Standard fallback result builders
# ---------------------------------------------------------------------------

def build_error_result(
    agent_name: str,
    error: str,
    tenant_id: str,
    extra_fields: dict = None,
) -> dict:
    """
    Build a standard error result dict for use in agent exception handlers.

    Args:
        agent_name:   Name of the agent (e.g. "CostAccountant").
        error:        Error message string.
        tenant_id:    Tenant identifier.
        extra_fields: Additional fields to merge into the result.

    Returns:
        Standard error dict with agent, error, tenant_id, auto_escalate, and flags.
    """
    result = {
        "agent": agent_name,
        "tenant_id": tenant_id,
        "error": error,
        "auto_escalate": True,
        "flags": [{
            "severity": "CRITICAL",
            "code": "AGENT_ERROR",
            "message": f"{agent_name} failed: {error}",
            "action_required": "Manual review required.",
        }],
    }
    if extra_fields:
        result.update(extra_fields)
    return result


def inject_metadata(
    result: dict,
    agent_name: str,
    tenant_id: str,
    model: str,
    elapsed_s: Optional[float] = None,
    analysis_type: Optional[str] = None,
    version: Optional[str] = None,
    extra: dict = None,
) -> dict:
    """
    Inject standard metadata fields into an agent result dict.
    Modifies result in-place and returns it.

    Args:
        result:        Agent output dict to enrich.
        agent_name:    Agent name string.
        tenant_id:     Tenant identifier.
        model:         Model string used for the call.
        elapsed_s:     Optional elapsed time in seconds.
        analysis_type: Optional analysis type string.
        version:       Optional agent version string.
        extra:         Optional additional key-value pairs.

    Returns:
        The enriched result dict.
    """
    result.setdefault("agent", agent_name)
    result["tenant_id"] = tenant_id
    result["analyzed_at"] = utc_iso()

    meta = result.setdefault("_meta", {})
    meta["model"] = model
    if elapsed_s is not None:
        meta["elapsed_s"] = elapsed_s
    if analysis_type is not None:
        meta["analysis_type"] = analysis_type

    if version:
        result[f"{agent_name.lower().replace(' ', '_')}_version"] = version

    if extra:
        result.update(extra)

    return result


# ---------------------------------------------------------------------------
# Token proximity warning
# ---------------------------------------------------------------------------

def warn_if_near_token_limit(
    output_tokens: int,
    max_tokens: int,
    agent_name: str,
    threshold_pct: float = 0.93,
) -> None:
    """
    Log a warning if output_tokens is close to max_tokens.
    Truncated responses cause silent JSON parse failures.

    Args:
        output_tokens:  Tokens used in the response.
        max_tokens:     The max_tokens limit set on the API call.
        agent_name:     Agent name for the log message.
        threshold_pct:  Fraction of max_tokens at which to warn. Default 0.93.
    """
    threshold = int(max_tokens * threshold_pct)
    if output_tokens >= threshold:
        logger.warning(
            "[%s] Output tokens (%d) near limit (%d) — response may be truncated. "
            "Consider increasing max_tokens or narrowing the input.",
            agent_name, output_tokens, max_tokens,
        )
