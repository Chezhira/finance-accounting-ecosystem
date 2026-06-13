"""
tax_agent_tz.py — Tanzania Tax Agent
====================================
Jurisdiction : Tanzania (Mainland + Zanzibar)
Regulator    : Tanzania Revenue Authority (TRA)
Standard     : IFRS (IAS 12, IAS 37 relevant)
Covers       : VAT returns, provisional tax, WHT remittance,
               AMT (Alternative Minimum Tax), reverse-charge VAT,
               Finance Act 2025 VAT withholding rules.

Plugs into existing escalation chain:
    TaxAgentTZ.analyze() → EscalationEngine.process() → Senior → Controller → Human
"""

import os
import json
import re
import anthropic
from datetime import date, datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Tanzania Tax Rules (baked in — agent can also research online)
# ---------------------------------------------------------------------------
TZ_TAX_RULES = {
    "corporate_tax_rate": 0.30,           # 30% resident companies
    "vat_standard_mainland": 0.18,        # 18% standard VAT (mainland)
    "vat_zanzibar": 0.15,                  # 15% Zanzibar
    "vat_b2c_electronic": 0.16,           # 16% B2C electronic services
    "vat_registration_threshold_tzs": 200_000_000,  # TZS 200M/year
    "vat_return_due_day": 20,             # 20th of following month
    "vat_withholding_goods": 0.03,        # Finance Act 2025 — 3% goods
    "vat_withholding_services": 0.06,     # Finance Act 2025 — 6% services
    "reverse_charge_digital": 0.18,       # Imported digital/software services
    "wht_dividends_resident": 0.05,
    "wht_dividends_non_resident": 0.10,
    "wht_interest_royalties": 0.15,
    "wht_imported_services": 0.15,        # Section 83 Income Tax Act
    "amt_rate": 0.01,                     # 1% of turnover (3+ years losses)
    "provisional_tax_quarters": 4,        # Quarterly
    "provisional_due_months_after_quarter": 3,
    "final_return_months_after_fy": 6,
}

SYSTEM_PROMPT = """You are the Tanzania Tax Agent in an AI-powered Finance & Accounting ecosystem.

## YOUR IDENTITY
Senior Tax Specialist with deep expertise in:
- Tanzania Revenue Authority (TRA) compliance
- IFRS (IAS 12 Deferred Tax, IAS 37 Tax Provisions, IAS 21 FX on tax liabilities)
- VAT Act (Cap. 148) — Tanzania Mainland & Zanzibar
- Income Tax Act (Cap. 332) — Section 83 WHT, Section 54 Provisional Tax
- Finance Act 2025 — VAT withholding agent rules (3% goods / 6% services)
- Transfer pricing, thin capitalisation rules
- CPA (T) / ACCA / CIMA level knowledge

## YOUR QUALIFICATIONS
- ACCA (Advanced Taxation — ATX)
- CPA (T) — certified in Tanzania tax practice
- CIMA — management accounting and tax provisioning
- IAS 12 specialist — deferred tax asset/liability computation
- TRA compliance — VAT, PAYE, SDL, WHT, Provisional Tax, AMT

## YOUR ROLE
You analyze raw financial data and produce structured tax compliance suggestions.
You NEVER make final decisions — you produce strong, well-reasoned suggestions
for review by Senior Accountant → Financial Controller → Human Operator.

## WHAT YOU ANALYZE
1. **VAT Compliance**
   - Output VAT on sales (18% mainland, 15% Zanzibar, 16% B2C digital)
   - Input VAT on purchases (recoverable vs. blocked input tax)
   - Reverse-charge VAT on imported digital/software services (self-assess 18%)
   - VAT withholding agent obligations (Finance Act 2025): 3% on goods, 6% on services
   - Net VAT payable / refundable
   - Due date: 20th of following month

2. **Provisional Tax**
   - Quarterly instalment computation (based on estimated annual income × 30%)
   - Due: within 3 months of each quarter end
   - Compare actual vs. estimated — flag underpayment risk
   - IAS 37 provision for tax shortfall

3. **Withholding Tax (WHT)**
   - 15% on imported services (Section 83) — deducted AT PAYMENT not accrual
   - 5% dividends (resident), 10% (non-resident)
   - 15% interest and royalties
   - Remittance to TRA: 7th of following month
   - Flag any missed WHT deductions as CRITICAL

4. **Alternative Minimum Tax (AMT)**
   - 1% of annual turnover
   - Applies when company has losses for 3+ consecutive years
   - Compute if data indicates consecutive losses

5. **Deferred Tax (IAS 12)**
   - Identify temporary differences
   - Compute deferred tax asset/liability at 30%
   - Flag if DTAs may not be recoverable (IAS 12.24)

6. **Journal Entries**
   - All suggested journal entries must balance (DR = CR)
   - Multi-currency entries use IAS 21 spot rate
   - WHT entries: flag at invoice stage (INFO), record at payment stage (DEBIT WHT Payable)

## OUTPUT FORMAT
Always respond in this exact JSON structure:
{
  "agent": "TaxAgentTZ",
  "jurisdiction": "Tanzania",
  "analysis_date": "YYYY-MM-DD",
  "tax_period": "string",
  "summary": "one paragraph executive summary",
  "tax_items": [
    {
      "type": "VAT|WHT|PROVISIONAL_TAX|AMT|DEFERRED_TAX|OTHER",
      "description": "string",
      "amount": number,
      "currency": "TZS|USD|EUR|GBP",
      "due_date": "YYYY-MM-DD or null",
      "status": "PAYABLE|REFUNDABLE|FLAGGED|INFO",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "regulatory_basis": "e.g. VAT Act s.XX / Income Tax Act s.83"
    }
  ],
  "journal_entries": [
    {
      "description": "string",
      "lines": [
        {"account": "string", "debit": number, "credit": number, "currency": "TZS"}
      ],
      "notes": "string"
    }
  ],
  "compliance_calendar": [
    {
      "obligation": "string",
      "due_date": "YYYY-MM-DD",
      "amount": number,
      "currency": "TZS",
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
  "escalation_notes": "notes for Senior Accountant reviewer"
}

## CRITICAL RULES
1. DR = CR always. Never output an unbalanced journal entry.
2. WHT at Section 83 is deducted AT PAYMENT — not at invoice accrual.
   At invoice: flag as INFO. At payment: record WHT Payable entry.
3. Reverse-charge VAT (imported digital services):
   DR Expense, DR VAT Recoverable, CR VAT Payable, CR AP (invoice amount only — NOT gross)
4. Finance Act 2025 VAT withholding: you WITHHOLD from supplier payment.
   DR AP [gross], CR VAT Withholding Payable [3% or 6%], CR Bank [net]
5. If you detect >3 consecutive loss years in the data → compute AMT at 1% turnover.
6. Always cite the regulatory basis for each item.
7. Flag CRITICAL if: WHT not deducted, VAT return overdue, AMT triggers undetected.
8. Output raw JSON only — no markdown, no preamble.
"""


class TaxAgentTZ:
    """
    Tanzania Tax Agent.

    Usage:
        agent = TaxAgentTZ()
        result = agent.analyze(raw_input, tenant_id, period, extra_context)
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = "claude-sonnet-4-6"     # Sonnet for core tax work
        self.rules = TZ_TAX_RULES
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
        Analyze raw financial data and produce Tanzania tax compliance suggestions.

        Args:
            raw_input          : Raw financial data (invoice, ledger, report, etc.)
            tenant_id          : Tenant identifier
            period             : e.g. "March 2026" or "Q1 FY2026"
            extra_context      : Additional operator context
            online_research_results : Results from web research (optional)

        Returns:
            dict with full tax analysis structured per SYSTEM_PROMPT output format.
            Includes top-level keys expected by EscalationEngine:
            - suggestion_type, suggested_action, confidence, flags, journal_entries
        """
        period_str = period or f"Period ending {self.today}"

        user_msg = f"""Analyze the following financial data for Tanzania tax compliance.

TENANT ID: {tenant_id}
TAX PERIOD: {period_str}
ANALYSIS DATE: {self.today}

TANZANIA TAX REFERENCE RATES:
{json.dumps(self.rules, indent=2)}

RAW INPUT DATA:
{raw_input}

{"ADDITIONAL CONTEXT:" + extra_context if extra_context else ""}
{"ONLINE RESEARCH RESULTS:" + online_research_results if online_research_results else ""}

Produce a full tax compliance analysis. Check for:
1. VAT obligations (output, input, reverse-charge, withholding agent)
2. WHT obligations (imported services, dividends, interest)
3. Provisional tax status
4. AMT applicability
5. Deferred tax (IAS 12) if P&L data is present
6. Compliance calendar — upcoming due dates
7. Any CRITICAL flags (missed WHT, overdue returns, AMT triggers)

Output raw JSON only."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        raw_text = response.content[0].text.strip()

        # Warn if model was cut off mid-response
        if response.stop_reason == "max_tokens":
            import logging
            logging.getLogger(__name__).warning(
                "TaxAgentTZ: Response hit max_tokens limit — JSON may be truncated. "
                "Consider increasing max_tokens or reducing input size."
            )

        result = self._extract_json(raw_text)

        # Normalise for escalation engine compatibility
        result.setdefault("tenant_id", tenant_id)
        result.setdefault("suggestion_type", "TAX_COMPLIANCE")
        result.setdefault("suggested_action", result.get("summary", "See tax analysis"))
        result.setdefault("jurisdiction", "Tanzania")
        result.setdefault("standard", "IFRS + TRA")
        result.setdefault("source", "tax_agent_tz")
        result.setdefault("tax_period", period_str)

        return result

    # ------------------------------------------------------------------
    def _extract_json(self, raw_text: str) -> dict:
        """
        Robustly extract JSON from model response.
        Handles markdown fences, preamble text, and trailing content.
        Uses brace-matching to find the outermost JSON object.
        """
        # 1. Try direct parse first
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        # 2. Strip markdown fences anywhere in the string
        cleaned = re.sub(r"```(?:json)?", "", raw_text).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 3. Find outermost { ... } by brace matching
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

        # 4. Give up — return error dict with raw response for debugging
        return {
            "agent": "TaxAgentTZ",
            "parse_error": True,
            "raw_response": raw_text[:2000],
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
            "compliance_calendar": [],
        }

    # ------------------------------------------------------------------
    def compute_vat_return(
        self,
        output_vat: float,
        input_vat: float,
        wht_vat_withheld: float = 0.0,
        currency: str = "TZS",
    ) -> dict:
        """
        Quick VAT return computation helper.

        output_vat      : Total output VAT collected on sales
        input_vat       : Total input VAT paid on purchases (recoverable)
        wht_vat_withheld: VAT withheld by VAT withholding agents (reduces payable)
        """
        net = output_vat - input_vat - wht_vat_withheld
        return {
            "output_vat": output_vat,
            "input_vat": input_vat,
            "wht_vat_withheld": wht_vat_withheld,
            "net_vat_payable": max(net, 0),
            "net_vat_refundable": max(-net, 0),
            "currency": currency,
        }

    # ------------------------------------------------------------------
    def compute_provisional_tax(
        self,
        estimated_annual_taxable_income: float,
        instalments_paid_to_date: float = 0.0,
        quarter_number: int = 1,
    ) -> dict:
        """
        Provisional tax instalment calculator.

        quarter_number: 1–4
        """
        annual_tax = estimated_annual_taxable_income * self.rules["corporate_tax_rate"]
        instalment_per_quarter = annual_tax / 4
        total_due_to_date = instalment_per_quarter * quarter_number
        balance_due = max(total_due_to_date - instalments_paid_to_date, 0)
        return {
            "estimated_annual_taxable_income": estimated_annual_taxable_income,
            "annual_tax_liability": annual_tax,
            "instalment_per_quarter": instalment_per_quarter,
            "total_due_to_date": total_due_to_date,
            "instalments_paid_to_date": instalments_paid_to_date,
            "balance_due_this_quarter": balance_due,
            "quarter": quarter_number,
        }

    # ------------------------------------------------------------------
    def compute_amt(self, annual_turnover: float, consecutive_loss_years: int) -> dict:
        """
        AMT computation — applies after 3+ consecutive loss years.
        """
        applicable = consecutive_loss_years >= 3
        amt = annual_turnover * self.rules["amt_rate"] if applicable else 0.0
        return {
            "applicable": applicable,
            "consecutive_loss_years": consecutive_loss_years,
            "annual_turnover": annual_turnover,
            "amt_payable": amt,
            "rate": self.rules["amt_rate"],
            "basis": "1% of annual turnover per Income Tax Act — AMT kicks in after 3+ loss years",
        }
