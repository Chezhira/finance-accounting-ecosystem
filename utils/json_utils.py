"""
utils/json_utils.py
====================
Shared JSON extraction utility for all Finance & Accounting AI agents.

Replaces the copy-pasted _extract_json() method found in:
  - cost_accountant.py
  - revenue_accountant.py
  - accounting_manager.py
  - corp_finance_agents.py
  - fpa_agents.py
  - treasury_agents.py
  - audit_agents.py

Usage:
    from utils.json_utils import extract_json

    result = extract_json(raw_text)
"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def extract_json(raw: str, fallback_keys: dict = None) -> dict:
    """
    3-stage JSON extraction: direct → strip fences → brace-depth matching.

    Args:
        raw:           Raw string output from the LLM.
        fallback_keys: Dict of keys to include in the fallback error response.
                       Merged with the default error structure.

    Returns:
        Parsed dict on success.
        Error dict with 'error', 'raw_response', 'findings', 'flags' on failure.

    Stages:
        1. Direct json.loads — fastest path, handles clean outputs.
        2. Strip markdown code fences (```json ... ```) then retry.
        3. Brace-depth scan — finds the first complete JSON object even
           when the model emits preamble text before the opening brace.
    """
    # Stage 1 — direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Stage 2 — strip markdown fences
    clean = re.sub(r"```(?:json)?", "", raw).strip()
    # Also strip trailing fence if present
    clean = re.sub(r"```\s*$", "", clean).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Stage 3 — brace-depth matching
    depth = 0
    start = None
    for i, ch in enumerate(clean):
        if ch == "{":
            if start is None:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(clean[start: i + 1])
                except json.JSONDecodeError:
                    # Reset and keep scanning — there may be a valid object later
                    start = None
                    break

    logger.warning(
        "extract_json: all 3 extraction stages failed. "
        "Raw output (first 200 chars): %s",
        raw[:200],
    )

    base_error = {
        "error": "JSON extraction failed",
        "raw_response": raw[:2000],
        "findings": [],
        "flags": [{"level": "CRITICAL", "message": "Agent returned unparseable output"}],
    }
    if fallback_keys:
        base_error.update(fallback_keys)
    return base_error


def validate_journal_balance(journal_entry: dict) -> tuple[bool, float, float]:
    """
    Validate that a journal entry's lines balance (DR = CR).

    Args:
        journal_entry: Dict with 'entries' list of {'debit': ..., 'credit': ...}
                       OR 'lines' list of {'debit': ..., 'credit': ...}

    Returns:
        (balanced: bool, total_debit: float, total_credit: float)
    """
    lines = journal_entry.get("entries") or journal_entry.get("lines", [])
    total_dr = round(sum(float(l.get("debit") or 0) for l in lines), 2)
    total_cr = round(sum(float(l.get("credit") or 0) for l in lines), 2)
    return (total_dr == total_cr), total_dr, total_cr
