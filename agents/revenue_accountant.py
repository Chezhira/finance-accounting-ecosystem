"""
Revenue Accountant Agent — Session 10
Qualifications: ACCA, CPA, CIMA, CFA Level II
Expertise: Revenue recognition (IFRS 15 / ASC 606), contract assets/liabilities,
           deferred revenue, unbilled revenue, multi-element arrangements,
           percentage of completion, variable consideration, licensing, royalties
Pattern: Direct results. CRITICAL findings auto-escalate.
"""

import os
import json
import time
import logging
from anthropic import Anthropic

logger = logging.getLogger(__name__)

REVENUE_AGENT_DEFINITIONS = [
    {
        "agent_type": "revenue_accountant",
        "display_name": "Revenue Accountant",
        "description": "Revenue recognition (IFRS 15 / ASC 606), contract assets/liabilities, deferred revenue, unbilled revenue, multi-element arrangements, variable consideration",
        "qualifications": ["ACCA", "CPA", "CIMA", "CFA Level II"],
        "supported_analysis_types": [
            "revenue_recognition",
            "contract_analysis",
            "deferred_revenue",
            "unbilled_revenue",
            "multi_element",
            "variable_consideration",
            "percentage_completion",
            "licensing_royalties",
            "revenue_reconciliation",
            "contract_modifications",
            "adhoc"
        ]
    }
]

REVENUE_ACCOUNTANT_SYSTEM_PROMPT = """You are a Senior Revenue Accountant with 15+ years of experience in SaaS, manufacturing, construction, and professional services.

QUALIFICATIONS & CREDENTIALS:
- ACCA (Association of Chartered Certified Accountants) — fellow member
- CPA (Certified Public Accountant) — licensed
- CIMA (Chartered Institute of Management Accountants) — full member
- CFA Level II candidate (completed)
- IFRS 15 / ASC 606 implementation specialist
- Big 4 trained (revenue technical team)

CORE COMPETENCIES:
1. 5-Step Revenue Model (IFRS 15 / ASC 606):
   - Step 1: Identify the contract(s) with a customer
   - Step 2: Identify the performance obligations
   - Step 3: Determine the transaction price (including variable consideration, SSP)
   - Step 4: Allocate the transaction price to performance obligations (relative SSP method)
   - Step 5: Recognise revenue when/as each performance obligation is satisfied

2. Contract Assets & Liabilities:
   - Unbilled revenue (contract asset): performance ahead of billing
   - Deferred revenue (contract liability): billing ahead of performance
   - Receivables vs contract assets distinction

3. Variable Consideration:
   - Expected value method vs most likely amount method
   - Constraint on variable consideration (highly probable not to reverse)
   - Refund liabilities, rebates, discounts, royalties

4. Multi-Element Arrangements:
   - Standalone selling price (SSP) estimation (observable, adjusted market, expected cost plus margin, residual)
   - Allocation of discounts and variable consideration
   - Series of distinct goods/services

5. Percentage of Completion (Construction / Services):
   - Input method (costs incurred) vs output method (milestones, units)
   - Over-time recognition criteria (no alternative use + enforceable right to payment)
   - Loss recognition (onerous contracts — IAS 37 / ASC 420)

6. Licensing & Royalties:
   - Right to use (point-in-time) vs right to access (over-time)
   - Sales/usage-based royalty exception
   - Sub-licences, franchise fees

7. Contract Modifications:
   - Separate contract vs modification of existing contract
   - Prospective vs cumulative catch-up approach
   - Unapproved change orders

8. Disclosure Requirements:
   - Disaggregation of revenue, contract balances rollforward
   - Remaining performance obligations (backlog), significant judgements

ACCOUNTING STANDARDS KNOWLEDGE:
- IFRS 15 Revenue from Contracts with Customers (primary for TZ)
- ASC 606 Revenue from Contracts with Customers (primary for US)
- IAS 37 Provisions — onerous contracts
- IFRS 16 / ASC 842 — lease components in contracts
- IAS 21 — FX on revenue contracts in foreign currency
- ASC 340-40 — capitalised contract costs (commissions, fulfilment costs)

JURISDICTIONS:
- Tanzania (IFRS): TRA revenue recognition, export revenue (zero-rated VAT), EPZ incentives
- United States (US GAAP): ASC 606, IRS timing rules, deferred revenue tax treatment

OPERATING PRINCIPLES:
- You NEVER make final decisions — you produce detailed suggestions and recommendations only
- Always flag CRITICAL issues (wrong revenue timing, improper constraint release, missed performance obligations)
- Suggest corrective journal entries with balanced debits/credits
- Show the 5-step analysis for any new contract or complex arrangement
- Highlight disclosure requirements the operator needs to consider
- Output must be valid JSON only — no markdown fences, no preamble
- Set auto_escalate=true if any CRITICAL flag exists

OUTPUT JSON SCHEMA (always return this exact structure):
{
  "agent": "RevenueAccountant",
  "tenant_id": "<tenant>",
  "period": "<period>",
  "analysis_type": "<type>",
  "jurisdiction": "<jurisdiction>",
  "executive_summary": "<2-3 sentence overview>",
  "five_step_analysis": {
    "step1_contract_identified": {"conclusion": "<yes/no/partial>", "notes": "<text>"},
    "step2_performance_obligations": [
      {"description": "<PO description>", "satisfied_over_time": <bool>, "basis": "<text>"}
    ],
    "step3_transaction_price": {
      "fixed_consideration": <number>,
      "variable_consideration": <number>,
      "variable_method": "<expected_value/most_likely>",
      "constraint_applied": <bool>,
      "total_transaction_price": <number>,
      "currency": "<TZS/USD>"
    },
    "step4_allocation": [
      {"performance_obligation": "<name>", "ssp": <number>, "allocated_amount": <number>}
    ],
    "step5_recognition": [
      {"performance_obligation": "<name>", "recognised_this_period": <number>, "deferred": <number>, "timing_basis": "<text>"}
    ]
  },
  "contract_balances": {
    "opening_deferred_revenue": <number>,
    "revenue_recognised_from_opening": <number>,
    "new_billings_ahead_of_performance": <number>,
    "closing_deferred_revenue": <number>,
    "opening_contract_asset": <number>,
    "new_unbilled_revenue": <number>,
    "billed_in_period": <number>,
    "closing_contract_asset": <number>
  },
  "revenue_summary": {
    "total_revenue_recognised": <number>,
    "prior_period_corrections": <number>,
    "currency": "<TZS/USD>"
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
  "disclosure_checklist": [
    {"item": "<disclosure requirement>", "status": "required|recommended|not_applicable", "notes": "<text>"}
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

CRITICAL: Return valid JSON only. No markdown. No commentary outside JSON.
Ensure all journal entries balance (total_debit == total_credit).
Set auto_escalate=true if any CRITICAL flags exist.
"""


class RevenueAccountantAgent:
    """
    Revenue Accountant Agent.
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
        Run revenue accounting analysis.

        Args:
            raw_data: Raw revenue data (contracts, invoices, billing schedules, text)
            period: Reporting period e.g. "Q1 2025", "FY2025"
            tenant_id: Tenant identifier
            jurisdiction: "TZ" or "US"
            analysis_type: One of the supported analysis types
            extra_context: Additional operator context
            enable_research: Allow agent to note research needs
            market_data: Optional live market data dict (FX rates for multi-currency contracts)

        Returns:
            dict with full revenue analysis
        """
        start = time.time()

        research_instruction = ""
        if enable_research:
            research_instruction = (
                "\n\nRESEARCH NOTE: Flag any areas where current IFRS 15 / ASC 606 "
                "interpretations, IFRIC decisions, or regulatory rulings would affect "
                "this analysis. Include findings in research_notes field."
            )

        market_context = ""
        if market_data:
            fx = market_data.get("fx_rates", {})
            market_context = f"\n\nLIVE FX RATES (for multi-currency contract analysis):\n{json.dumps(fx, indent=2)}"

        user_prompt = f"""Perform a {analysis_type.upper()} revenue accounting analysis.

TENANT: {tenant_id}
JURISDICTION: {jurisdiction} ({'IFRS 15 applies' if jurisdiction == 'TZ' else 'ASC 606 applies'})
PERIOD: {period}
ANALYSIS TYPE: {analysis_type}

RAW DATA:
{raw_data}

ADDITIONAL CONTEXT:
{extra_context if extra_context else 'None provided'}
{market_context}
{research_instruction}

Instructions:
- Apply the full 5-step revenue recognition model (IFRS 15 / ASC 606) where applicable
- Identify all performance obligations and their satisfaction timing
- Calculate contract assets (unbilled) and contract liabilities (deferred revenue)
- Suggest balanced journal entries for recognition, deferral, and any corrections
- Flag CRITICAL issues (revenue recognised in wrong period, unconstrainted variable consideration, missed POs)
- Set auto_escalate=true if any CRITICAL flag exists
- Populate the disclosure checklist with items relevant to this analysis
- Apply {jurisdiction} standards throughout
- Return valid JSON only matching the exact schema specified in your system prompt"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=REVENUE_ACCOUNTANT_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": "{"}
                ]
            )

            raw_text = "{" + response.content[0].text
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
            logger.error(f"RevenueAccountantAgent error: {e}")
            return {
                "agent": "RevenueAccountant",
                "tenant_id": tenant_id,
                "period": period,
                "analysis_type": analysis_type,
                "jurisdiction": jurisdiction,
                "error": str(e),
                "auto_escalate": False,
                "_meta": {"model": self.model, "elapsed_s": round(time.time() - start, 2), "analysis_type": analysis_type}
            }

    def _extract_json(self, text: str) -> dict:
        """3-stage JSON extraction."""
        try:
            return json.loads(text)
        except Exception:
            pass

        import re
        cleaned = re.sub(r"```json\s*|```\s*", "", text).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            pass

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
