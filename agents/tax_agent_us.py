"""
tax_agent_us.py — US Tax Agent (LLC / Pass-Through)
=====================================================
Jurisdiction : United States
Entity type  : Family-Owned LLC (pass-through taxation)
Regulator    : IRS
Standard     : US GAAP
Covers       : Pass-through income, self-employment tax,
               quarterly estimated taxes, Schedule C / Form 1065 / K-1,
               SALT deduction, QBI deduction, TaxJar sales tax.

Plugs into existing escalation chain:
    TaxAgentUS.analyze() → EscalationEngine.process() → Senior → Controller → Human
"""

import os
import json
import re
import anthropic
from datetime import date
from typing import Optional

# ---------------------------------------------------------------------------
# US Tax Rules (baked in — agent can also research online for updates)
# ---------------------------------------------------------------------------
US_TAX_RULES = {
    # LLC / pass-through
    "entity_type": "LLC (pass-through — Schedule C or Form 1065 + K-1)",
    "pass_through": True,
    # Self-employment tax
    "se_tax_rate": 0.153,                       # 15.3% total
    "ss_tax_rate": 0.124,                       # 12.4% Social Security
    "ss_wage_base_2025": 184_500,               # SS wage base 2025
    "medicare_tax_rate": 0.029,                 # 2.9% Medicare
    "additional_medicare_surtax_rate": 0.009,   # 0.9% over $200K
    "additional_medicare_threshold": 200_000,
    # SE tax deduction (50% of SE tax deductible from gross income)
    "se_tax_deduction_rate": 0.5,
    # Quarterly estimated tax dates 2026
    "quarterly_due_dates_2026": [
        "2026-04-15",   # Q1
        "2026-06-15",   # Q2
        "2026-09-15",   # Q3
        "2027-01-15",   # Q4
    ],
    # SALT cap (One Big Beautiful Bill Act 2025)
    "salt_deduction_cap_2025": 40_000,
    # QBI deduction (IRC §199A) — 20% of qualified business income
    "qbi_deduction_rate": 0.20,
    # Forms
    "key_forms": ["Schedule C", "Form 1065", "Schedule K-1", "Form 1040-ES", "Form SE"],
    # Federal income tax brackets 2025 (single filer, simplified)
    "federal_brackets_single_2025": [
        {"up_to": 11_925, "rate": 0.10},
        {"up_to": 48_475, "rate": 0.12},
        {"up_to": 103_350, "rate": 0.22},
        {"up_to": 197_300, "rate": 0.24},
        {"up_to": 250_525, "rate": 0.32},
        {"up_to": 626_350, "rate": 0.35},
        {"up_to": None,    "rate": 0.37},
    ],
    # Standard deduction 2025
    "standard_deduction_single_2025": 15_000,
    "standard_deduction_married_2025": 30_000,
    # Safe harbour thresholds (avoid underpayment penalty)
    "safe_harbour_prior_year_tax": 1.00,        # 100% of prior year tax
    "safe_harbour_high_income": 1.10,           # 110% if AGI > $150K
    "safe_harbour_agi_threshold": 150_000,
    # Underpayment penalty
    "underpayment_rate_annual": 0.08,           # 8% annual (2025 IRS rate)
}

SYSTEM_PROMPT = """You are the US Tax Agent in an AI-powered Finance & Accounting ecosystem.

## YOUR IDENTITY
Senior US Tax Specialist with deep expertise in:
- IRS compliance for LLCs (single-member and multi-member)
- Pass-through taxation — Schedule C, Form 1065, Schedule K-1
- Self-employment tax (IRC §1401), QBI deduction (IRC §199A)
- Quarterly estimated tax calculations and safe-harbour rules
- US GAAP — ASC 740 Income Taxes (deferred tax, uncertain tax positions)
- SALT deduction rules (One Big Beautiful Bill Act 2025)
- TaxJar integration for sales tax nexus and filing
- CPA / EA / CFA level knowledge

## YOUR QUALIFICATIONS
- CPA (US) — licensed with IRS representation rights
- EA (Enrolled Agent) — IRS examinations expertise
- ACCA — international accounting overlay
- CFA Level II — financial statement analysis, tax efficiency
- CFP — personal financial tax planning (LLC owner distributions)
- Expertise: LLC structuring, S-corp election analysis, self-employment tax reduction strategies

## YOUR ROLE
Analyze raw financial data and produce structured US tax compliance suggestions.
You NEVER make final decisions — strong suggestions only.
All suggestions flow to Senior Accountant → Financial Controller → Human Operator.

## WHAT YOU ANALYZE

### 1. Self-Employment Tax (IRC §1401)
- Compute net self-employment income (net profit from LLC)
- 92.35% of net SE income is subject to SE tax (because you deduct the "employer half")
- SE tax = (net SE income × 0.9235) × 15.3%
  - But SS portion (12.4%) only applies up to wage base ($184,500 in 2025)
  - Medicare (2.9%) applies to all SE income
  - Additional 0.9% Medicare surtax on income over $200,000
- 50% of SE tax is deductible from gross income (Schedule 1, Line 15)

### 2. Quarterly Estimated Taxes (Form 1040-ES)
- Estimate annual tax liability (federal income tax + SE tax)
- Divide by 4 for quarterly instalments
- Due dates: Apr 15, Jun 15, Sep 15, Jan 15
- Safe harbour: Pay ≥ 100% of prior year tax (110% if prior-year AGI > $150K)
- Flag underpayment risk — 8% annual penalty rate

### 3. Pass-Through Income & K-1 (Form 1065)
- Allocate LLC income/loss per K-1 to each member per operating agreement
- Identify: ordinary business income, rental income, capital gains, §179 deductions
- QBI deduction (§199A): 20% of qualified business income (subject to W-2 wage and UBIA limits)
- Basis tracking: increases for income/contributions, decreases for losses/distributions

### 4. SALT Deduction (State & Local Taxes)
- Cap: $40,000 per One Big Beautiful Bill Act 2025
- Flag if state tax + property tax > $40,000

### 5. US GAAP — ASC 740 Deferred Tax
- Identify temporary differences (depreciation timing, accruals)
- Note: LLCs are pass-through — deferred tax appears on OWNER's return, not LLC's books
  (Unless LLC has elected corporate tax treatment)
- Flag if S-corp election might be beneficial (SE tax reduction strategy)

### 6. TaxJar — Sales Tax Nexus
- Flag states where nexus may be established (economic nexus threshold: $100K sales or 200 transactions)
- Ensure TaxJar is configured for all nexus states
- Monthly/quarterly filing deadlines vary by state

### 7. Journal Entries (US GAAP)
- LLC books: record income, expenses, owner draws, member equity
- SE tax liability: DR SE Tax Expense, CR SE Tax Payable
- Estimated tax payments: DR Estimated Tax Payments (asset), CR Bank
- SALT: DR SALT Expense (up to $40K cap), CR SALT Payable

## OUTPUT FORMAT
Always respond in this exact JSON structure:
{
  "agent": "TaxAgentUS",
  "jurisdiction": "United States",
  "analysis_date": "YYYY-MM-DD",
  "tax_period": "string",
  "entity_type": "LLC (pass-through)",
  "summary": "one paragraph executive summary",
  "tax_items": [
    {
      "type": "SE_TAX|ESTIMATED_TAX|K1_ALLOCATION|QBI_DEDUCTION|SALT|SALES_TAX|DEFERRED_TAX|OTHER",
      "description": "string",
      "amount": number,
      "currency": "USD",
      "due_date": "YYYY-MM-DD or null",
      "status": "PAYABLE|REFUNDABLE|FLAGGED|INFO",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "irc_basis": "e.g. IRC §1401 / ASC 740 / §199A"
    }
  ],
  "se_tax_computation": {
    "net_llc_income": number,
    "se_net_earnings": number,
    "ss_taxable_portion": number,
    "ss_tax": number,
    "medicare_tax": number,
    "additional_medicare": number,
    "total_se_tax": number,
    "se_tax_deduction_50pct": number
  },
  "quarterly_estimates": [
    {
      "quarter": "Q1|Q2|Q3|Q4",
      "due_date": "YYYY-MM-DD",
      "estimated_amount": number,
      "paid": number,
      "balance_due": number,
      "status": "CURRENT|OVERDUE|UPCOMING"
    }
  ],
  "k1_allocations": [
    {
      "member": "string",
      "ownership_pct": number,
      "ordinary_income": number,
      "guaranteed_payments": number,
      "capital_gains": number,
      "section_179": number,
      "distributions": number,
      "basis_adjustment": number
    }
  ],
  "journal_entries": [
    {
      "description": "string",
      "lines": [
        {"account": "string", "debit": number, "credit": number, "currency": "USD"}
      ],
      "notes": "string"
    }
  ],
  "compliance_calendar": [
    {
      "obligation": "string",
      "due_date": "YYYY-MM-DD",
      "amount": number,
      "currency": "USD",
      "risk": "string"
    }
  ],
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
  "research_needed": ["list of items to look up online"],
  "escalation_notes": "notes for Senior Accountant reviewer",
  "strategic_suggestions": ["e.g. S-corp election analysis, QBID optimisation"]
}

## CRITICAL RULES
1. DR = CR always. Never output an unbalanced journal entry.
2. SE tax is 15.3% — but ONLY on 92.35% of net earnings (not 100%). 
   Many people get this wrong. Always show the computation step.
3. SS portion (12.4%) is CAPPED at $184,500 wage base. Medicare has no cap.
4. 50% of SE tax is always a deduction from gross income before computing income tax.
5. QBI deduction (§199A) is 20% of QBI — but limited by W-2 wages + UBIA for higher earners.
   Flag if income > $191,950 (single) or $383,900 (MFJ) as phase-out applies.
6. SALT cap is $40,000 (2025). Flag if state/local taxes exceed this.
7. Safe harbour estimated tax = 100% of prior year tax (110% if prior AGI > $150K).
8. Output raw JSON only — no markdown, no preamble.
"""


class TaxAgentUS:
    """
    US Tax Agent for LLC (pass-through entity).

    Usage:
        agent = TaxAgentUS()
        result = agent.analyze(raw_input, tenant_id, period, extra_context)
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = "claude-sonnet-4-5"     # Sonnet for core tax work
        self.rules = US_TAX_RULES
        self.today = date.today().isoformat()

    # ------------------------------------------------------------------
    def analyze(
        self,
        raw_input: str,
        tenant_id: str,
        period: Optional[str] = None,
        extra_context: str = "",
        online_research_results: str = "",
    ) -> dict:
        """
        Analyze raw financial data and produce US LLC tax compliance suggestions.

        Args:
            raw_input          : Raw financial data (P&L, bank statement, invoices, etc.)
            tenant_id          : Tenant identifier
            period             : e.g. "Q1 2026" or "Tax Year 2025"
            extra_context      : Additional operator context
            online_research_results : Results from web research (optional)

        Returns:
            dict — full tax analysis, compatible with EscalationEngine.
        """
        period_str = period or f"Period ending {self.today}"

        user_msg = f"""Analyze the following financial data for US LLC tax compliance.

TENANT ID: {tenant_id}
TAX PERIOD: {period_str}
ANALYSIS DATE: {self.today}

US TAX REFERENCE RULES:
{json.dumps(self.rules, indent=2)}

RAW INPUT DATA:
{raw_input}

{"ADDITIONAL CONTEXT:" + extra_context if extra_context else ""}
{"ONLINE RESEARCH RESULTS:" + online_research_results if online_research_results else ""}

Produce a full US LLC tax compliance analysis. Include:
1. Self-employment tax computation (show 92.35% step clearly)
2. Quarterly estimated tax schedule — what is owed and when
3. K-1 allocation if multi-member LLC
4. QBI deduction (§199A) assessment
5. SALT deduction check (cap $40,000)
6. Sales tax nexus flags (TaxJar integration)
7. Strategic suggestions (S-corp election, QBID optimisation, etc.)
8. Compliance calendar with all due dates
9. Journal entries (US GAAP) — must balance

Output raw JSON only."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": "{"},   # prefill forces JSON start
            ],
        )

        # Prepend the prefill character we injected
        raw_text = "{" + response.content[0].text.strip()

        # Warn if model was cut off mid-response
        if response.stop_reason == "max_tokens":
            import logging
            logging.getLogger(__name__).warning(
                "TaxAgentUS: Response hit max_tokens limit — JSON may be truncated. "
                "Consider increasing max_tokens or reducing input size."
            )

        result = self._extract_json(raw_text)

        # Normalise for escalation engine compatibility
        result.setdefault("tenant_id", tenant_id)
        result.setdefault("suggestion_type", "TAX_COMPLIANCE")
        result.setdefault("suggested_action", result.get("summary", "See US tax analysis"))
        result.setdefault("jurisdiction", "United States")
        result.setdefault("standard", "US GAAP + IRS")
        result.setdefault("source", "tax_agent_us")
        result.setdefault("tax_period", period_str)

        return result

    # ------------------------------------------------------------------
    def _extract_json(self, raw_text: str) -> dict:
        """
        Robustly extract JSON from model response.
        Handles markdown fences, preamble text, and trailing content.
        """
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        cleaned = re.sub(r"```(?:json)?", "", raw_text).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        start = cleaned.find("{")
        if start != -1:
            depth = 0
            for i, ch in enumerate(cleaned[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(cleaned[start:i+1])
                        except json.JSONDecodeError:
                            break

        return {
            "agent": "TaxAgentUS",
            "parse_error": True,
            "raw_response": raw_text[:8000],
            "summary": "Tax analysis produced but could not be parsed as JSON.",
            "confidence": "LOW",
            "flags": [{
                "severity": "HIGH",
                "code": "PARSE_ERROR",
                "message": "Agent response was not valid JSON. Raw response preserved.",
                "action_required": "Review raw_response field manually.",
            }],
            "tax_items": [],
            "journal_entries": [],
            "quarterly_estimates": [],
            "compliance_calendar": [],
        }

    # ------------------------------------------------------------------
    def compute_se_tax(self, net_llc_income: float) -> dict:
        """
        Quick self-employment tax helper.
        
        Applies the correct 92.35% factor before computing SE tax.
        SS portion is capped at the wage base.
        """
        rules = self.rules
        se_net = net_llc_income * 0.9235      # Statutory 92.35% factor

        # Social Security (capped at wage base)
        ss_taxable = min(se_net, rules["ss_wage_base_2025"])
        ss_tax = ss_taxable * rules["ss_tax_rate"]

        # Medicare (no cap)
        medicare_tax = se_net * rules["medicare_tax_rate"]

        # Additional Medicare surtax (0.9% over $200K of net LLC income)
        additional_medicare = 0.0
        if net_llc_income > rules["additional_medicare_threshold"]:
            additional_medicare = (
                (net_llc_income - rules["additional_medicare_threshold"])
                * rules["additional_medicare_surtax_rate"]
            )

        total_se_tax = ss_tax + medicare_tax + additional_medicare
        se_deduction = total_se_tax * rules["se_tax_deduction_rate"]  # 50% deductible

        return {
            "net_llc_income": net_llc_income,
            "se_net_earnings_92_35pct": round(se_net, 2),
            "ss_taxable_portion": round(ss_taxable, 2),
            "ss_wage_base": rules["ss_wage_base_2025"],
            "ss_tax": round(ss_tax, 2),
            "medicare_tax": round(medicare_tax, 2),
            "additional_medicare_surtax": round(additional_medicare, 2),
            "total_se_tax": round(total_se_tax, 2),
            "se_tax_deduction_50pct": round(se_deduction, 2),
            "basis": "IRC §1401 — 92.35% factor applied; SS capped at wage base",
        }

    # ------------------------------------------------------------------
    def quarterly_estimate(
        self,
        estimated_annual_federal_income_tax: float,
        estimated_annual_se_tax: float,
        paid_to_date: float = 0.0,
        quarter_number: int = 1,
    ) -> dict:
        """
        Quarterly estimated tax instalment calculator.
        """
        annual_total = estimated_annual_federal_income_tax + estimated_annual_se_tax
        per_quarter = annual_total / 4
        total_due_to_date = per_quarter * quarter_number
        balance = max(total_due_to_date - paid_to_date, 0.0)

        due_dates = self.rules["quarterly_due_dates_2026"]
        due_date = due_dates[quarter_number - 1] if 1 <= quarter_number <= 4 else "N/A"

        return {
            "estimated_annual_income_tax": estimated_annual_federal_income_tax,
            "estimated_annual_se_tax": estimated_annual_se_tax,
            "total_annual_tax": annual_total,
            "per_quarter": round(per_quarter, 2),
            "quarter": quarter_number,
            "due_date": due_date,
            "total_due_to_date": round(total_due_to_date, 2),
            "paid_to_date": paid_to_date,
            "balance_due": round(balance, 2),
            "form": "Form 1040-ES",
        }
