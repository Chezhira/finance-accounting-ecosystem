"""
tax_orchestrator.py — Tax Routing Layer
========================================
Routes incoming tax analysis requests to the correct jurisdiction agent:
    - Tanzania → TaxAgentTZ
    - United States → TaxAgentUS

Integrates with EscalationEngine for full Senior → Controller → Human review chain.
"""

import logging
from typing import Optional

from agents.tax_agent_tz import TaxAgentTZ
from agents.tax_agent_us import TaxAgentUS

logger = logging.getLogger(__name__)


class TaxOrchestrator:
    """
    Tax Orchestrator — instantiates the correct tax agent per jurisdiction
    and wraps the result in a format compatible with EscalationEngine.

    Supported jurisdictions (case-insensitive):
        "Tanzania", "TZ", "tz"  → TaxAgentTZ
        "United States", "US", "us", "USA" → TaxAgentUS
    """

    # Map jurisdiction strings to agent classes
    JURISDICTION_MAP = {
        "tanzania": "tz",
        "tz": "tz",
        "united states": "us",
        "us": "us",
        "usa": "us",
        "united_states": "us",
    }

    def __init__(self):
        # Lazy-init agents — only instantiate when needed
        self._tz_agent: Optional[TaxAgentTZ] = None
        self._us_agent: Optional[TaxAgentUS] = None

    def _get_tz_agent(self) -> TaxAgentTZ:
        if self._tz_agent is None:
            self._tz_agent = TaxAgentTZ()
        return self._tz_agent

    def _get_us_agent(self) -> TaxAgentUS:
        if self._us_agent is None:
            self._us_agent = TaxAgentUS()
        return self._us_agent

    def analyze(
        self,
        raw_input: str,
        tenant_id: str,
        jurisdiction: str,
        period: Optional[str] = None,
        extra_context: str = "",
        online_research_results: str = "",
    ) -> dict:
        """
        Route tax analysis to the correct agent.

        Args:
            raw_input    : Raw financial data
            tenant_id    : Tenant identifier
            jurisdiction : "Tanzania"|"TZ"|"United States"|"US"|"USA"
            period       : Tax period string (e.g. "Q1 2026")
            extra_context: Operator context
            online_research_results: Pre-fetched research

        Returns:
            dict — full tax analysis from the correct agent, escalation-engine compatible.

        Raises:
            ValueError: If jurisdiction is not supported.
        """
        key = jurisdiction.lower().strip()
        resolved = self.JURISDICTION_MAP.get(key)

        if resolved is None:
            raise ValueError(
                f"Unsupported jurisdiction: '{jurisdiction}'. "
                f"Supported: Tanzania (TZ), United States (US/USA)."
            )

        logger.info(
            "TaxOrchestrator routing — tenant=%s jurisdiction=%s resolved=%s",
            tenant_id, jurisdiction, resolved
        )

        if resolved == "tz":
            agent = self._get_tz_agent()
            result = agent.analyze(
                raw_input=raw_input,
                tenant_id=tenant_id,
                period=period,
                extra_context=extra_context,
                online_research_results=online_research_results,
            )
        else:  # us
            agent = self._get_us_agent()
            result = agent.analyze(
                raw_input=raw_input,
                tenant_id=tenant_id,
                period=period,
                extra_context=extra_context,
                online_research_results=online_research_results,
            )

        # Tag result with routing metadata
        result["tax_agent_routed_to"] = resolved
        result["tax_orchestrator_version"] = "1.0.0"

        return result


# Module-level singleton (safe — both agents are stateless between calls)
_orchestrator_instance: Optional[TaxOrchestrator] = None


def get_tax_orchestrator() -> TaxOrchestrator:
    """Return the module-level TaxOrchestrator singleton."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = TaxOrchestrator()
    return _orchestrator_instance
