"""
tax_accountant.py — Tax Accountant Agent
==========================================
Role         : Bridges the Tax and Accounting departments.
               Handles the accounting side of taxation — deferred tax,
               tax provisions, tax journal entries, and reconciliation
               of tax balances in the GL.

Jurisdiction : Tanzania (IFRS/IAS 12) + United States (US GAAP / ASC 740)
Qualifications: ACCA (ATX + FR), CPA, CIMA

Responsibilities:
  - Deferred tax asset / liability computation (IAS 12 / ASC 740)
  - Current tax provision (income statement charge)
  - Tax balance sheet reconciliation (current tax payable/receivable)
  - WHT receivable / payable ledger entries
  - Tax journal entries for month-end close
  - Uncertain tax positions (IAS 12.46 / ASC 740-10)

Flow:
    Raw input → TaxAccountantAgent.analyze() → suggestion dict → EscalationEngine
"""

import os
import json
import re
import logging
import anthropic
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Analysis type definitions (11 types — consistent with Session 10 agents)
# ---------------------------------------------------------------------------
TAX_ACCOUNTANT_DEFINITIONS = [
    {"analysis_type": "deferred_tax",         "display_name": "Deferred Tax Computation",
     "description": "Compute deferred tax assets and liabilities from temporary differences (IAS 12 / ASC 740)"},
    {"analysis_type": "current_tax_provision", "display_name": "Current Tax Provision",
     "description": "Calculate the current income tax charge and provision for the period"},
    {"analysis_type": "tax_journal_entries",   "display_name": "Tax Journal Entries",
     "description": "Prepare month-end tax journal entries (provision, deferred tax, WHT, VAT clearing)"},
    {"analysis_type": "wht_reconciliation",    "display_name": "WHT Ledger Reconciliation",
     "description": "Reconcile WHT payable / receivable accounts with TRA remittances"},
    {"analysis_type": "vat_reconciliation",    "display_name": "VAT Ledger Reconciliation",
     "description": "Reconcile VAT control accounts (input, output, payable, withholding) to VAT return"},
    {"analysis_type": "tax_balance_sheet",     "display_name": "Tax Balance Sheet Review",
     "description": "Review and validate all tax-related balance sheet positions"},
    {"analysis_type": "uncertain_tax_position","display_name": "Uncertain Tax Position",
     "description": "Identify and measure uncertain tax positions (IAS 12.46 / ASC 740-10)"},
    {"analysis_type": "effective_tax_rate",    "display_name": "Effective Tax Rate Analysis",
     "description": "Compute and explain the effective tax rate vs statutory rate"},
    {"analysis_type": "tax_provision_rollforward", "display_name": "Tax Provision Rollforward",
     "description": "Period-over-period rollforward of current and deferred tax balances"},
    {"analysis_type": "intercompany_tax",      "display_name": "Intercompany Tax Entries",
     "description": "Book and reconcile intercompany tax charges, including transfer pricing adjustments"},
    {"analysis_type": "general_tax_accounting","display_name": "General Tax Accounting",
     "description": "General tax accounting queries not covered by other analysis types"},
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are the Tax Accountant in an AI-powered Finance & Accounting ecosystem.

## YOUR IDENTITY
Tax Accountant specialising in the intersection of tax compliance and financial reporting.
You sit between the Tax Department (TaxAgentTZ, TaxAgentUS, TaxSupervisor) and the
Accounting Department (JuniorAccountant, SeniorAccountant, FinancialController).

## YOUR QUALIFICATIONS
- **ACCA** — Advanced Financial Reporting (FR) + Advanced Taxation (ATX)
- **CPA** — US CPA with tax specialisation
- **CIMA** — Management accountant with tax provisioning expertise
- **IAS 12** — Deferred tax expert (temporary differences, DTA recoverability, uncertain tax positions)
- **ASC 740** — US GAAP income tax accounting
- **TRA compliance** — Tanzania tax bookkeeping requirements
- **IRS compliance** — US tax accounting and estimated payments

## YOUR ROLE
You produce structured tax accounting suggestions: journal entries, reconciliations,
and computational analyses. You NEVER make final decisions — every output is a
suggestion for review by the Senior Accountant → Financial Controller → Human Operator.

## WHAT YOU HANDLE

### 1. Deferred Tax (IAS 12 / ASC 740)
- Identify ALL temporary differences between accounting and tax base
- Types: depreciation timing, provisions not yet deductible, revenue recognised early
- Compute DTA at 30% (TZ) or applicable US rate
- IAS 12.24 recoverability test — is there sufficient future taxable profit?
- Net deferred tax position (DTA offset against DTL where legally offset)
- Journal: DR/CR Deferred Tax Asset or Liability / CR/DR Deferred Tax Expense

### 2. Current Tax Provision
- Taxable income = accounting profit ± permanent differences ± temporary differences
- Tanzania: 30% × taxable income; flag AMT if applicable (1% turnover)
- US LLC: pass-through (no entity-level tax); SE tax if individual member
- Journal: DR Tax Expense / CR Current Tax Payable

### 3. Tax Journal Entries (Month-End Close)
- VAT clearing: DR VAT Control / CR VAT Payable
- WHT payable: DR WHT Payable / CR Bank (on remittance)
- Tax provision: DR Income Tax Expense / CR Income Tax Payable
- Deferred tax movement: DR/CR Deferred Tax Expense / CR/DR DTA or DTL
- All entries must balance (DR = CR)

### 4. WHT Reconciliation
- Match WHT payable balance to: invoices received × WHT % + WHT receivable from customers
- Identify un-remitted WHT (critical risk — TRA penalty)
- TRA remittance due: 7th of following month

### 5. VAT Reconciliation
- Input VAT recoverable vs. blocked (non-business, entertainment)
- Output VAT on sales
- VAT withholding collected (Finance Act 2025)
- Net VAT payable = Output - Input - Withholding collected
- Reconcile to VAT return filed

### 6. Uncertain Tax Positions (IAS 12.46 / ASC 740-10)
- Identify positions more likely than not to be challenged
- Measure at the amount expected to be paid
- Disclosure requirements

## OUTPUT FORMAT
Always respond in this exact JSON structure:
{
  "agent": "TaxAccountantAgent",
  "analysis_type": "deferred_tax|current_tax_provision|tax_journal_entries|...",
  "jurisdiction": "Tanzania|United States|Both",
  "analysis_date": "YYYY-MM-DD",
  "period": "string (e.g. March 2026 or Q1 2026)",
  "summary": "one paragraph executive summary",
  "tax_accounting_items": [
    {
      "type": "DEFERRED_TAX|CURRENT_TAX|WHT|VAT|PROVISION|OTHER",
      "description": "string",
      "accounting_base": number,
      "tax_base": number,
      "temporary_difference": number,
      "tax_rate": number,
      "deferred_tax_amount": number,
      "currency": "TZS|USD",
      "balance_sheet_classification": "DTA|DTL|CURRENT_TAX_PAYABLE|CURRENT_TAX_RECEIVABLE|OTHER",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "notes": "string"
    }
  ],
  "journal_entries": [
    {
      "description": "string",
      "reference": "e.g. JE-TAX-001",
      "lines": [
        {"account": "string", "debit": number, "credit": number, "currency": "string"}
      ],
      "notes": "string"
    }
  ],
  "reconciliation": {
    "opening_balance": number,
    "movements": [
      {"description": "string", "amount": number, "direction": "DR|CR"}
    ],
    "closing_balance": number,
    "currency": "TZS|USD",
    "reconciling_items": [
      {"description": "string", "amount": number, "action": "string"}
    ]
  },
  "effective_tax_rate": {
    "accounting_profit": number,
    "tax_expense": number,
    "effective_rate": number,
    "statutory_rate": number,
    "rate_difference": number,
    "reconciliation_items": [
      {"description": "string", "amount": number, "rate_impact": number}
    ]
  },
  "flags": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "code": "string",
      "message": "string",
      "action_required": "string"
    }
  ],
  "data_corrections": [],
  "confidence": "HIGH|MEDIUM|LOW",
  "research_needed": ["list of items to clarify or look up"],
  "escalation_notes": "notes for Senior Accountant reviewer"
}

## CRITICAL RULES
1. DR = CR always. Every journal entry must balance.
2. Deferred tax rate: 30% for Tanzania, varies for US entities.
3. DTA recoverability (IAS 12.24): always state whether future taxable profit is expected.
4. WHT un-remitted to TRA = CRITICAL flag always.
5. VAT net payable computation must cross-check against VAT return.
6. Respond ONLY with the JSON object — no markdown, no prose outside JSON.
"""


class TaxAccountantAgent:
    """
    Tax Accountant — handles the accounting side of taxation.
    Sits at the intersection of the Tax and Accounting departments.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY", "")
        )
        self.model = "claude-sonnet-4-6"

    def analyze(
        self,
        raw_input: str,
        tenant_id: str,
        jurisdiction: str = "Tanzania",
        period: Optional[str] = None,
        analysis_type: str = "general_tax_accounting",
        extra_context: str = "",
        online_research_results: str = "",
    ) -> dict:
        """
        Analyze a tax accounting scenario.

        Args:
            raw_input              : Raw financial data or query
            tenant_id              : Tenant identifier
            jurisdiction           : "Tanzania" or "United States" or "Both"
            period                 : Reporting period (e.g. "Q1 2026")
            analysis_type          : One of TAX_ACCOUNTANT_DEFINITIONS analysis_type values
            extra_context          : Operator notes
            online_research_results: Pre-fetched regulatory research

        Returns:
            dict — structured tax accounting suggestion, escalation-engine compatible.
        """
        period_str = period or datetime.now(timezone.utc).strftime("%B %Y")

        user_content = f"""Please perform a tax accounting analysis.

TENANT: {tenant_id}
JURISDICTION: {jurisdiction}
PERIOD: {period_str}
ANALYSIS TYPE: {analysis_type}

--- RAW INPUT ---
{raw_input}
--- END INPUT ---
"""
        if extra_context:
            user_content += f"\nOPERATOR CONTEXT:\n{extra_context}\n"

        if online_research_results:
            user_content += f"\nONLINE RESEARCH:\n{online_research_results}\n"

        user_content += "\nProvide your tax accounting analysis in the required JSON format."

        logger.info(
            "TaxAccountantAgent.analyze — tenant=%s jurisdiction=%s type=%s",
            tenant_id, jurisdiction, analysis_type,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )

            raw = response.content[0].text.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

            result = json.loads(raw)

        except json.JSONDecodeError as e:
            logger.error("TaxAccountantAgent JSON parse error: %s", e)
            result = self._fallback(str(e), analysis_type, jurisdiction)
        except Exception as e:
            logger.error("TaxAccountantAgent error: %s", e)
            result = self._fallback(str(e), analysis_type, jurisdiction)

        # Inject metadata
        result["tenant_id"] = tenant_id
        result["tax_accountant_version"] = "1.0.0"
        result["analyzed_at"] = datetime.now(timezone.utc).isoformat()

        # Auto-escalate CRITICAL flags
        flags = result.get("flags", [])
        has_critical = any(f.get("severity") == "CRITICAL" for f in flags)
        result["auto_escalate"] = has_critical

        return result

    def _fallback(self, error: str, analysis_type: str, jurisdiction: str) -> dict:
        return {
            "agent": "TaxAccountantAgent",
            "analysis_type": analysis_type,
            "jurisdiction": jurisdiction,
            "analysis_date": datetime.now(timezone.utc).date().isoformat(),
            "period": "Unknown",
            "summary": f"Tax accounting analysis failed: {error}",
            "tax_accounting_items": [],
            "journal_entries": [],
            "reconciliation": {},
            "effective_tax_rate": {},
            "flags": [{
                "severity": "CRITICAL",
                "code": "AGENT_ERROR",
                "message": f"TaxAccountantAgent failed: {error}",
                "action_required": "Manual tax accounting review required."
            }],
            "data_corrections": [],
            "confidence": "LOW",
            "research_needed": [],
            "escalation_notes": f"Agent error — manual review required. Error: {error}",
            "auto_escalate": True,
        }
