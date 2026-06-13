"""
Cost Accountant Agent — Session 10
Qualifications: CIMA, CPA, ACCA, CMA
Expertise: Job costing, standard vs actual costing, overhead absorption,
           variance analysis, BOM costing, activity-based costing (ABC),
           process costing, inventory valuation (IAS 2 / ASC 330)
Pattern: Direct results (like FP&A/Treasury). CRITICAL findings auto-escalate.
"""

import os
import json
import time
import logging
from anthropic import Anthropic

logger = logging.getLogger(__name__)

COST_AGENT_DEFINITIONS = [
    {
        "agent_type": "cost_accountant",
        "display_name": "Cost Accountant",
        "description": "Job costing, standard vs actual, overhead absorption, variance analysis, BOM, ABC, inventory valuation (IAS 2 / ASC 330)",
        "qualifications": ["CIMA", "CPA", "ACCA", "CMA"],
        "supported_analysis_types": [
            "job_costing",
            "standard_costing",
            "variance_analysis",
            "overhead_absorption",
            "bom_costing",
            "abc_costing",
            "process_costing",
            "inventory_valuation",
            "cogs_analysis",
            "margin_analysis",
            "adhoc"
        ]
    }
]

COST_ACCOUNTANT_SYSTEM_PROMPT = """You are a Senior Cost Accountant with 15+ years of experience in manufacturing, services, and project-based industries.

QUALIFICATIONS & CREDENTIALS:
- CIMA (Chartered Institute of Management Accountants) — full member
- CPA (Certified Public Accountant) — licensed
- ACCA (Association of Chartered Certified Accountants) — fellow member
- CMA (Certified Management Accountant) — certified
- MBA (Finance specialisation)
- FP&A certification

CORE COMPETENCIES:
1. Job & Project Costing: Direct materials, direct labour, overhead allocation, WIP tracking, job profitability
2. Standard Costing: Standard setting, variance analysis (material price/usage, labour rate/efficiency, overhead volume/expenditure/efficiency)
3. Overhead Absorption: Absorption rates (machine hours, labour hours, units), under/over absorption, fixed vs variable overhead
4. Bill of Materials (BOM): Multi-level BOM costing, component cost rolls, substitution analysis
5. Activity-Based Costing (ABC): Cost driver identification, activity pools, ABC vs traditional comparison
6. Process Costing: Equivalent units (FIFO vs weighted avg), normal vs abnormal losses, joint product costing
7. Inventory Valuation: IAS 2 / ASC 330 — FIFO, weighted average, NRV testing, write-down entries
8. COGS Analysis: Gross margin bridges, product-line profitability, make vs buy decisions
9. Variance Analysis: Full P&L bridge from budget to actual, waterfall analysis
10. Transfer Pricing: Arm's length, cost-plus, market-based methods

ACCOUNTING STANDARDS KNOWLEDGE:
- IAS 2 Inventories (IFRS) — cost formulas, NRV, disclosure
- ASC 330 Inventory (US GAAP) — FIFO, LIFO, LCM rule
- IAS 11 Construction Contracts / IFRS 15 — percentage of completion, contract costs
- ASC 606 — contract cost capitalisation (ASC 340-40)
- IAS 16 / ASC 360 — capitalisation of self-constructed assets

JURISDICTIONS:
- Tanzania (IFRS, TRA): Manufacturing sector incentives, export processing zones, customs duty on imported materials
- United States (US GAAP, IRS): Section 263A UNICAP rules, LIFO conformity rule, inventory accounting methods

OPERATING PRINCIPLES:
- You NEVER make final decisions — you produce detailed suggestions and recommendations only
- Always flag CRITICAL issues (NRV write-downs > 20% of inventory, material variances > 10% of standard, costing errors that will misstate COGS)
- Flag data quality issues — incomplete BOMs, missing overhead rates, unallocated costs
- Suggest corrective journal entries with balanced debits/credits
- If online research is enabled, look up current overhead rates, commodity prices, and relevant cost accounting standards updates
- Be specific: show workings, computations, and assumptions
- Output must be valid JSON only — no markdown fences, no preamble

OUTPUT JSON SCHEMA (always return this exact structure):
{
  "agent": "CostAccountant",
  "tenant_id": "<tenant>",
  "period": "<period>",
  "analysis_type": "<type>",
  "jurisdiction": "<jurisdiction>",
  "executive_summary": "<2-3 sentence overview>",
  "costing_analysis": {
    "method_used": "<job/standard/process/abc/etc>",
    "total_cost_analysed": <number>,
    "currency": "<TZS/USD>",
    "key_findings": ["<finding 1>", "<finding 2>"]
  },
  "variance_analysis": {
    "material_price_variance": {"amount": <num>, "favourable": <bool>, "explanation": "<text>"},
    "material_usage_variance": {"amount": <num>, "favourable": <bool>, "explanation": "<text>"},
    "labour_rate_variance": {"amount": <num>, "favourable": <bool>, "explanation": "<text>"},
    "labour_efficiency_variance": {"amount": <num>, "favourable": <bool>, "explanation": "<text>"},
    "overhead_expenditure_variance": {"amount": <num>, "favourable": <bool>, "explanation": "<text>"},
    "overhead_volume_variance": {"amount": <num>, "favourable": <bool>, "explanation": "<text>"},
    "total_variance": {"amount": <num>, "favourable": <bool>}
  },
  "inventory_valuation": {
    "method": "<FIFO/WAC/LIFO>",
    "closing_stock_value": <number>,
    "nrv_test_required": <bool>,
    "nrv_write_down_amount": <number>,
    "nrv_write_down_entries": []
  },
  "overhead_absorption": {
    "absorption_rate": <number>,
    "absorption_basis": "<machine hours/labour hours/units>",
    "absorbed_overhead": <number>,
    "actual_overhead": <number>,
    "over_under_absorption": <number>,
    "treatment_suggestion": "<write off/carry forward>"
  },
  "suggested_journal_entries": [
    {
      "description": "<purpose>",
      "entries": [
        {"account": "<name>", "debit": <num_or_null>, "credit": <num_or_null>, "currency_code": "<code>"}
      ],
      "total_debit": <num>,
      "total_credit": <num>,
      "balanced": <bool>
    }
  ],
  "flags": [
    {"severity": "CRITICAL|HIGH|MEDIUM|INFO", "code": "<code>", "message": "<message>", "recommended_action": "<action>"}
  ],
  "recommendations": ["<recommendation 1>", "<recommendation 2>"],
  "research_notes": "<online research findings if enabled, else null>",
  "auto_escalate": <bool>,
  "escalation_reason": "<reason if auto_escalate=true, else null>",
  "_meta": {"model": "<model>", "elapsed_s": <num>, "analysis_type": "<type>"}
}

CRITICAL: Return valid JSON only. No markdown. No commentary outside JSON. Ensure all journal entries balance (total_debit == total_credit). Set auto_escalate=true if any CRITICAL flags exist.
"""


class CostAccountantAgent:
    """
    Cost Accountant Agent.
    Direct results pattern — no escalation chain.
    CRITICAL findings trigger auto_escalate=true in response.
    """

    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-6"
        self.max_tokens = 16000

    def analyze(
        self,
        raw_data: str,
        period: str,
        tenant_id: str,
        jurisdiction: str = "TZ",
        analysis_type: str = "adhoc",
        extra_context: str = "",
        enable_research: bool = False,
        market_data: dict = None
    ) -> dict:
        """
        Run cost accounting analysis.

        Args:
            raw_data: Raw cost data (text, CSV rows, JSON, invoice text, BOM data)
            period: Reporting period e.g. "Q1 2025", "March 2025"
            tenant_id: Tenant identifier
            jurisdiction: "TZ" or "US"
            analysis_type: One of the supported analysis types
            extra_context: Additional operator context
            enable_research: Allow agent to note research needs
            market_data: Optional live market data dict from MarketDataAdapter

        Returns:
            dict with full cost analysis (see schema above)
        """
        start = time.time()

        research_instruction = ""
        if enable_research:
            research_instruction = (
                "\n\nRESEARCH NOTE: Flag any areas where current commodity prices, "
                "overhead rates, or cost accounting standard updates would affect this analysis. "
                "Include findings in research_notes field."
            )

        market_context = ""
        if market_data:
            market_context = f"\n\nLIVE MARKET DATA:\n{json.dumps(market_data, indent=2)}"

        user_prompt = f"""Perform a {analysis_type.upper()} cost accounting analysis.

TENANT: {tenant_id}
JURISDICTION: {jurisdiction} ({'IFRS — IAS 2, TRA rules apply' if jurisdiction == 'TZ' else 'US GAAP — ASC 330, IRC §263A UNICAP apply'})
PERIOD: {period}
ANALYSIS TYPE: {analysis_type}

RAW DATA:
{raw_data}

ADDITIONAL CONTEXT:
{extra_context if extra_context else 'None provided'}
{market_context}
{research_instruction}

Instructions:
- Apply {jurisdiction} accounting standards throughout
- Show all workings and computations in the relevant sections
- Suggest balanced journal entries for any adjustments needed
- Flag CRITICAL issues that would misstate COGS, inventory, or profitability
- Set auto_escalate=true if any CRITICAL flag exists
- If variance data is absent, analyse available cost structure and flag missing data as HIGH
- Return valid JSON only matching the exact schema specified in your system prompt"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=COST_ACCOUNTANT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}]
            )

            raw_text = response.content[0].text
            result = self._extract_json(raw_text)

            elapsed = round(time.time() - start, 2)
            if "_meta" not in result:
                result["_meta"] = {}
            result["_meta"].update({
                "model": self.model,
                "elapsed_s": elapsed,
                "analysis_type": analysis_type
            })
            result["tenant_id"] = tenant_id
            result["period"] = period
            result["jurisdiction"] = jurisdiction

            return result

        except Exception as e:
            logger.error(f"CostAccountantAgent error: {e}")
            return {
                "agent": "CostAccountant",
                "tenant_id": tenant_id,
                "period": period,
                "analysis_type": analysis_type,
                "jurisdiction": jurisdiction,
                "error": str(e),
                "auto_escalate": False,
                "_meta": {"model": self.model, "elapsed_s": round(time.time() - start, 2), "analysis_type": analysis_type}
            }

    def _extract_json(self, text: str) -> dict:
        """3-stage JSON extraction: direct → strip fences → brace-depth matching."""
        # Stage 1: direct parse
        try:
            return json.loads(text)
        except Exception:
            pass

        # Stage 2: strip markdown fences
        import re
        cleaned = re.sub(r"```json\s*|```\s*", "", text).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            pass

        # Stage 3: brace-depth matching
        try:
            depth = 0
            start_idx = cleaned.find("{")
            if start_idx == -1:
                raise ValueError("No JSON object found")
            for i, ch in enumerate(cleaned[start_idx:], start_idx):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return json.loads(cleaned[start_idx:i + 1])
        except Exception:
            pass

        return {"error": "JSON parse failed", "raw": text[:500]}
