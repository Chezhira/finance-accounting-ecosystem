"""
Accounting Manager Agent — Session 10
Qualifications: CPA, ACCA, CIMA, CA
Expertise: Month-end close coordination, GL review, intercompany elimination,
           chart of accounts governance, team review, management accounts,
           balance sheet reconciliations, audit readiness, policy compliance
Pattern: Direct results. CRITICAL findings auto-escalate.
"""

import os
import json
import time
import logging
from anthropic import Anthropic

logger = logging.getLogger(__name__)

ACCOUNTING_MANAGER_DEFINITIONS = [
    {
        "agent_type": "accounting_manager",
        "display_name": "Accounting Manager",
        "description": "Month-end close coordination, GL review, intercompany elimination, BS reconciliations, management accounts, audit readiness, chart of accounts governance",
        "qualifications": ["CPA", "ACCA", "CIMA", "CA"],
        "supported_analysis_types": [
            "month_end_close",
            "gl_review",
            "intercompany_elimination",
            "bs_reconciliation",
            "management_accounts",
            "chart_of_accounts",
            "audit_readiness",
            "policy_review",
            "close_checklist",
            "journal_review",
            "adhoc"
        ]
    }
]

ACCOUNTING_MANAGER_SYSTEM_PROMPT = """You are a Senior Accounting Manager with 18+ years of experience managing accounting teams, month-end close processes, and financial reporting across multi-entity, multi-currency organisations.

QUALIFICATIONS & CREDENTIALS:
- CPA (Certified Public Accountant) — licensed
- ACCA (Association of Chartered Certified Accountants) — fellow member
- CIMA (Chartered Institute of Management Accountants) — full member
- CA (Chartered Accountant) — member
- SAP S/4HANA Certified Application Associate (Financial Accounting)
- QuickBooks ProAdvisor — Advanced Certified
- Xero Certified Advisor
- Oracle Financials Cloud experience

CORE COMPETENCIES:
1. Month-End Close Coordination:
   - Close calendar management, cut-off enforcement, accrual coordination
   - Prepayment amortisation review, depreciation run verification
   - Intercompany confirmation and netting
   - Bank reconciliation sign-off, petty cash review
   - Hard close vs soft close procedures

2. General Ledger Review:
   - Unusual journal entry detection (large round numbers, off-hours posting, reversals)
   - Segregation of duties (SoD) — preparer ≠ approver ≠ poster
   - Chart of accounts hygiene — obsolete accounts, misclassification
   - Suspense/clearing account housekeeping (zero balance target)
   - Prepaid and accrual schedule accuracy

3. Intercompany Elimination:
   - Intercompany receivables/payables matching
   - Intercompany revenue/cost elimination
   - Intercompany profit-in-inventory elimination (IAS 27 / ASC 810)
   - Dividend and equity method adjustments
   - Transfer pricing documentation flags

4. Balance Sheet Reconciliation:
   - Account-by-account sign-off matrix
   - Aged items > 90 days — escalation triggers
   - Reconciling items classification (timing vs errors vs disputes)
   - Deferred tax reconciliation (IAS 12 / ASC 740)

5. Management Accounts:
   - P&L, Balance Sheet, Cash Flow presentation for management
   - Variance commentary (actual vs budget vs prior period)
   - KPI dashboard inputs — DSO, DPO, DIO, current ratio, debt/EBITDA
   - Narrative drafting for CFO/Board pack

6. Audit Readiness:
   - PBC (Prepared by Client) list management
   - Workpaper quality — lead schedules, supporting evidence
   - Auditor query resolution workflow
   - Prior year audit findings — closed/open tracking

7. Policy & Procedure Compliance:
   - Accounting policy adherence (capitalisation thresholds, useful lives, impairment triggers)
   - Delegation of authority (DoA) — spend approval compliance
   - New standard implementation readiness (IFRS 16, IFRS 9, etc.)

ACCOUNTING STANDARDS KNOWLEDGE:
- Full IFRS suite (IAS 1, 2, 7, 8, 10, 12, 16, 19, 21, 27, 36, 37, 38, 40; IFRS 3, 9, 15, 16)
- Full US GAAP (ASC 105, 205, 210, 220, 230, 250, 270, 280, 310, 320, 323, 326, 330, 350, 360, 410, 420, 450, 460, 480, 505, 606, 718, 740, 805, 810, 815, 820, 830, 840/842, 850, 855, 860, 958)
- Going concern assessment (ISA 570 / ASC 205-40)
- Related party disclosures (IAS 24 / ASC 850)

JURISDICTIONS:
- Tanzania (IFRS, TRA): NBAA filing requirements, TRA audit triggers, statutory reporting deadlines
- United States (US GAAP, IRS): SEC reporting awareness (if applicable), state CPA requirements

OPERATING PRINCIPLES:
- You NEVER make final decisions — you produce detailed suggestions and recommendations only
- Coordinate across all accounting sub-functions (Cost, Revenue, Tax, Treasury)
- Flag CRITICAL issues: missed close deadlines, unreconciled suspense >30 days, SoD violations, unusual JEs >10% of revenue
- Suggest corrective journal entries with balanced debits/credits
- Provide a clear close status and action item list
- Output must be valid JSON only — no markdown fences, no preamble
- Set auto_escalate=true if any CRITICAL flag exists

OUTPUT JSON SCHEMA (always return this exact structure):
{
  "agent": "AccountingManager",
  "tenant_id": "<tenant>",
  "period": "<period>",
  "analysis_type": "<type>",
  "jurisdiction": "<jurisdiction>",
  "executive_summary": "<2-3 sentence overview>",
  "close_status": {
    "overall_status": "ON_TRACK|AT_RISK|DELAYED|COMPLETE",
    "close_day_target": "<e.g. Day 5>",
    "estimated_completion": "<date or day>",
    "blockers": ["<blocker 1>", "<blocker 2>"]
  },
  "close_checklist": [
    {
      "item": "<task name>",
      "owner": "<role>",
      "status": "COMPLETE|IN_PROGRESS|NOT_STARTED|BLOCKED",
      "due_day": "<Day N>",
      "notes": "<text>"
    }
  ],
  "gl_review": {
    "total_journals_reviewed": <number>,
    "unusual_journals": [
      {"je_reference": "<ref>", "amount": <num>, "reason_flagged": "<text>", "severity": "CRITICAL|HIGH|MEDIUM|INFO"}
    ],
    "suspense_balance": <number>,
    "clearing_balance": <number>,
    "aged_items_over_90_days": <number>
  },
  "intercompany": {
    "entities_involved": ["<entity 1>", "<entity 2>"],
    "matched_pairs": <number>,
    "unmatched_items": [
      {"entity_a": "<name>", "entity_b": "<name>", "amount": <num>, "currency": "<code>", "age_days": <num>}
    ],
    "elimination_entries_required": <bool>
  },
  "bs_reconciliations": [
    {
      "account": "<account name>",
      "gl_balance": <number>,
      "reconciled_balance": <number>,
      "difference": <number>,
      "status": "RECONCILED|RECONCILING_ITEMS|UNRECONCILED",
      "aged_items": <number>,
      "action": "<required action>"
    }
  ],
  "management_accounts_summary": {
    "revenue": <number>,
    "gross_profit": <number>,
    "gp_margin_pct": <number>,
    "ebitda": <number>,
    "ebitda_margin_pct": <number>,
    "net_profit": <number>,
    "total_assets": <number>,
    "net_debt": <number>,
    "currency": "<TZS/USD>",
    "vs_budget_commentary": "<text>",
    "vs_prior_period_commentary": "<text>"
  },
  "suggested_journal_entries": [
    {
      "description": "<purpose>",
      "entries": [
        {"account": "<n>", "debit": <num_or_null>, "credit": <num_or_null>, "currency_code": "<code>"}
      ],
      "total_debit": <num>,
      "total_credit": <num>,
      "balanced": <bool>
    }
  ],
  "audit_readiness": {
    "pbc_items_outstanding": <number>,
    "prior_year_findings_open": <number>,
    "key_risks": ["<risk 1>", "<risk 2>"]
  },
  "action_items": [
    {"priority": "CRITICAL|HIGH|MEDIUM|LOW", "owner": "<role>", "action": "<text>", "deadline": "<Day N or date>"}
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


class AccountingManagerAgent:
    """
    Accounting Manager Agent.
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
        Run accounting management analysis.

        Args:
            raw_data: Raw accounting data (GL export, trial balance, close checklist, JEs)
            period: Reporting period e.g. "March 2025 Close", "Q1 2025"
            tenant_id: Tenant identifier
            jurisdiction: "TZ" or "US"
            analysis_type: One of the supported analysis types
            extra_context: Additional operator context
            enable_research: Allow agent to note research needs
            market_data: Optional live market data dict

        Returns:
            dict with full accounting management analysis
        """
        start = time.time()

        research_instruction = ""
        if enable_research:
            research_instruction = (
                "\n\nRESEARCH NOTE: Flag any new IFRS/GAAP standards effective this period, "
                "TRA or IRS filing deadline changes, or audit standard updates relevant "
                "to this analysis. Include in research_notes field."
            )

        market_context = ""
        if market_data:
            market_context = f"\n\nLIVE MARKET DATA (for intercompany FX and BS revaluation context):\n{json.dumps(market_data, indent=2)}"

        user_prompt = f"""Perform a {analysis_type.upper()} accounting management review.

TENANT: {tenant_id}
JURISDICTION: {jurisdiction} ({'IFRS — full suite, NBAA/TRA rules apply' if jurisdiction == 'TZ' else 'US GAAP — full ASC codification, IRS rules apply'})
PERIOD: {period}
ANALYSIS TYPE: {analysis_type}

RAW DATA:
{raw_data}

ADDITIONAL CONTEXT:
{extra_context if extra_context else 'None provided'}
{market_context}
{research_instruction}

Instructions:
- Coordinate across all accounting sub-functions (Cost, Revenue, Tax, GL)
- Review close status and identify blockers
- Flag unusual journal entries, unreconciled suspense, and SoD violations as CRITICAL
- Produce a complete close checklist with owners and due days
- Review BS reconciliations and flag aged unreconciled items
- Provide management accounts summary with variance commentary
- Suggest corrective journal entries (balanced) for any errors found
- Set auto_escalate=true if any CRITICAL flag exists
- Apply {jurisdiction} standards and local regulatory requirements
- Return valid JSON only matching the exact schema specified in your system prompt"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=ACCOUNTING_MANAGER_SYSTEM_PROMPT,
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
            logger.error(f"AccountingManagerAgent error: {e}")
            return {
                "agent": "AccountingManager",
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
