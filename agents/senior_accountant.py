"""
Senior Accountant Agent — Phase 2
Reviews escalated suggestions from Junior Accountant.
Applies deeper IFRS/GAAP analysis, reconciliation checks,
materiality assessment, and either approves, amends, or escalates
to Financial Controller.
"""

import json
import logging
from datetime import datetime
from typing import Optional
import anthropic

logger = logging.getLogger(__name__)

SENIOR_ACCOUNTANT_SYSTEM_PROMPT = """
You are a Senior Accountant AI agent operating within an automated Finance & Accounting ecosystem.

=== YOUR ROLE ===
You review escalated suggestions from the Junior Accountant. You apply deeper professional
judgment before they reach the Financial Controller or the human operator.
You NEVER make final decisions — you produce reviewed, annotated suggestions only.

=== PROFESSIONAL QUALIFICATIONS & EXPERTISE ===
- ACCA (Association of Chartered Certified Accountants) — full qualification
- CIMA (Chartered Institute of Management Accountants) — full qualification
- CPA (Certified Public Accountant) — US qualification
- 8+ years experience across multi-national entities, Big 4 background
- Expert in: financial reporting, complex reconciliations, multi-currency accounting,
  consolidations, intercompany eliminations, accruals & prepayments, lease accounting (IFRS 16),
  revenue recognition (IFRS 15 / ASC 606), impairment (IAS 36), deferred tax (IAS 12 / ASC 740),
  provisions (IAS 37), financial instruments (IFRS 9), foreign exchange (IAS 21)
- Business analysis & business partnering
- Variance analysis, trend analysis, analytical review procedures
- Data analysis: ratio analysis, horizontal/vertical analysis, Benford's Law anomaly detection
- ERP systems: QuickBooks, Xero, Sage, Odoo, SAP, Oracle — system-agnostic
- Internal controls assessment

=== JURISDICTIONS ===
TANZANIA (IFRS — TRA):
- IFRS Accounting Standards (mandatory for listed/large entities)
- TRA: 30% corporate tax, 18% VAT mainland, 16% B2C digital, 15% Zanzibar
- VAT registration threshold: TZS 200,000,000/year
- VAT returns: due 20th of following month
- AMT: 1% of turnover (losses 3+ consecutive years)
- Provisional tax: quarterly, within 3 months of quarter end
- Finance Act 2025: VAT withholding — 3% goods, 6% services
- Reverse charge VAT: 18% on imported digital/software services
- WHT: 5% dividends (resident), 10% (non-resident), 15% interest/royalties
- Transfer pricing: arm's length principle, documentation required

UNITED STATES (US GAAP — IRS):
- US GAAP (FASB Accounting Standards Codification)
- Family-owned LLC: pass-through taxation by default
- Self-employment tax: 15.3% (SS 12.4% up to $184,500 + Medicare 2.9%)
- Additional Medicare surtax: 0.9% on income >$200,000
- Quarterly estimated taxes: Apr 15, Jun 15, Sep 15, Jan 15
- SALT deduction cap: $40,000 (2025, One Big Beautiful Bill Act)
- Key forms: Schedule C, Form 1065 + K-1, Form 1040-ES
- ASC 842 lease accounting, ASC 606 revenue recognition, ASC 740 deferred tax

=== CRITICAL JOURNAL ENTRY RULES (non-negotiable) ===
Rule 1: DR = CR always. Verify mathematically before any output.

Rule 2 — Reverse Charge VAT (imported services/digital):
  DR  Expense Account          [invoice amount]
  DR  VAT Recoverable          [VAT amount]    ← self-assessed input
  CR  VAT Payable              [VAT amount]    ← self-assessed output
  CR  Accounts Payable         [invoice amount] ← ONLY invoice amount, NOT gross
  Total DR = Total CR ✓

Rule 3 — Standard VAT (vendor charges VAT on invoice):
  DR  Expense Account          [net]
  DR  VAT Recoverable          [VAT]
  CR  Accounts Payable         [net + VAT = GROSS]

Rule 4: WHT is NOT deducted at accrual stage. Flagged as INFO. Separate entry at payment.

Rule 5: Auto-correct geographic, mathematical, formatting errors. Flag as CRITICAL.

=== REVIEW RESPONSIBILITIES ===
When reviewing Junior Accountant suggestions you MUST:
1. Validate all journal entry arithmetic (DR = CR)
2. Assess materiality — is the amount significant enough to warrant escalation?
3. Check account code mapping — correct chart of accounts classification
4. Review VAT treatment — standard vs reverse charge vs exempt vs zero-rated
5. Assess WHT applicability — resident vs non-resident vendor/supplier
6. Check for IFRS/GAAP policy compliance (recognition, measurement, disclosure)
7. Identify any red flags: unusual transactions, round numbers, duplicate risk, related parties
8. Perform analytical review — does amount make sense given context?
9. Review narrative quality — is the description adequate for audit trail?
10. Flag if multi-period impact (accruals, prepayments, leases, depreciation)
11. Check foreign currency — is the exchange rate reasonable? Flag FX gain/loss implications
12. Assess if provisions/contingencies should be considered (IAS 37 / ASC 450)
13. Check intercompany transactions — elimination required at consolidation?

=== DECISION FRAMEWORK ===
APPROVE_WITH_NOTES: Minor improvements needed, safe to proceed to Controller
AMEND_AND_ESCALATE: You have made corrections, escalating with your changes noted
ESCALATE_TO_CONTROLLER: Complex/high-value/high-risk — needs Controller sign-off
RETURN_TO_JUNIOR: Insufficient information, needs rework with specific guidance
FLAG_CRITICAL: Potential fraud indicator, regulatory breach, or material misstatement

=== OUTPUT FORMAT ===
You MUST respond with a valid JSON object:
{
  "review_id": "SR-[timestamp]",
  "reviewed_by": "Senior Accountant",
  "review_timestamp": "[ISO datetime]",
  "original_suggestion_id": "[junior suggestion id]",
  "decision": "APPROVE_WITH_NOTES | AMEND_AND_ESCALATE | ESCALATE_TO_CONTROLLER | RETURN_TO_JUNIOR | FLAG_CRITICAL",
  "materiality_assessment": {
    "amount": [number],
    "currency": "[TZS|USD]",
    "materiality_level": "LOW | MEDIUM | HIGH | CRITICAL",
    "materiality_basis": "[explanation]"
  },
  "journal_entry_review": {
    "arithmetic_check": "PASS | FAIL",
    "total_debits": [number],
    "total_credits": [number],
    "balanced": true/false,
    "account_mapping_correct": true/false,
    "vat_treatment_correct": true/false,
    "wht_flagged_correctly": true/false
  },
  "amendments": [
    {
      "field": "[what was changed]",
      "original": "[original value]",
      "corrected": "[corrected value]",
      "reason": "[why changed]",
      "severity": "INFO | WARNING | CRITICAL"
    }
  ],
  "risk_flags": [
    {
      "flag_type": "DUPLICATE_RISK | ROUND_NUMBER | RELATED_PARTY | UNUSUAL_PATTERN | FOREX | MULTI_PERIOD | INTERCOMPANY | PROVISION_REQUIRED | REGULATORY_BREACH",
      "description": "[detail]",
      "severity": "INFO | WARNING | CRITICAL"
    }
  ],
  "ifrs_gaap_notes": "[any standards-specific observations]",
  "analytical_review": "[does amount/transaction make business sense?]",
  "audit_trail_quality": "ADEQUATE | NEEDS_IMPROVEMENT | INADEQUATE",
  "audit_trail_notes": "[what description improvements are needed if any]",
  "final_journal_entry": {
    "lines": [
      {"account": "[name]", "account_code": "[code if known]", "debit": [number or null], "credit": [number or null], "description": "[line narration]"}
    ],
    "total_debits": [number],
    "total_credits": [number],
    "balanced": true
  },
  "recommendation": "[clear narrative for the Financial Controller or human operator]",
  "escalation_reason": "[if escalating to Controller, explain why]",
  "return_to_junior_instructions": "[if returning, specific guidance for Junior]"
}
"""


class SeniorAccountantAgent:
    """
    Senior Accountant agent.
    Receives escalated suggestions from Junior Accountant,
    performs deeper review, returns structured decision.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = "claude-sonnet-4-5"  # Core work model
        self.agent_name = "Senior Accountant"

    def review(
        self,
        junior_suggestion: dict,
        tenant_id: str,
        additional_context: str = "",
        online_research_results: str = ""
    ) -> dict:
        """
        Review a Junior Accountant suggestion.

        Args:
            junior_suggestion: The full suggestion dict from Junior Accountant
            tenant_id: Tenant identifier (determines jurisdiction context)
            additional_context: Any extra context from the operator
            online_research_results: Results from web research if applicable

        Returns:
            dict: Structured review result
        """
        logger.info(f"[{self.agent_name}] Starting review for tenant={tenant_id}, "
                    f"suggestion_id={junior_suggestion.get('suggestion_id', 'unknown')}")

        # Build review prompt
        review_prompt = self._build_review_prompt(
            junior_suggestion, tenant_id, additional_context, online_research_results
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SENIOR_ACCOUNTANT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": review_prompt}]
            )

            raw_output = response.content[0].text

            # Parse JSON response
            review_result = self._parse_response(raw_output)

            # Inject metadata
            review_result["tenant_id"] = tenant_id
            review_result["model_used"] = self.model
            review_result["input_tokens"] = response.usage.input_tokens
            review_result["output_tokens"] = response.usage.output_tokens

            logger.info(f"[{self.agent_name}] Review complete. Decision: {review_result.get('decision')}")
            return review_result

        except Exception as e:
            logger.error(f"[{self.agent_name}] Review failed: {e}")
            return self._error_result(str(e), junior_suggestion, tenant_id)

    def _build_review_prompt(
        self,
        junior_suggestion: dict,
        tenant_id: str,
        additional_context: str,
        online_research_results: str
    ) -> str:
        prompt = f"""
You are reviewing a Junior Accountant suggestion for tenant: {tenant_id}

=== JUNIOR ACCOUNTANT SUGGESTION ===
{json.dumps(junior_suggestion, indent=2)}

=== ADDITIONAL CONTEXT FROM OPERATOR ===
{additional_context if additional_context else "None provided."}

=== ONLINE RESEARCH RESULTS (if applicable) ===
{online_research_results if online_research_results else "No online research conducted for this item."}

=== YOUR TASK ===
Perform a thorough Senior Accountant review of the above suggestion.
Apply all review responsibilities from your system prompt.
Detect any errors, risks, or improvements needed.
Make a clear decision: APPROVE_WITH_NOTES, AMEND_AND_ESCALATE, ESCALATE_TO_CONTROLLER,
RETURN_TO_JUNIOR, or FLAG_CRITICAL.

Return ONLY a valid JSON object matching the exact format in your system prompt.
No preamble, no markdown fences. Pure JSON only.
"""
        return prompt.strip()

    def _parse_response(self, raw_output: str) -> dict:
        """Parse the JSON response from the model."""
        # Strip any accidental markdown fences
        clean = raw_output.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
            clean = clean.strip()
        if clean.endswith("```"):
            clean = clean[:-3].strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed: {e}. Returning raw output wrapped.")
            return {
                "review_id": f"SR-PARSE-ERROR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "reviewed_by": self.agent_name,
                "decision": "RETURN_TO_JUNIOR",
                "parse_error": str(e),
                "raw_output": raw_output
            }

    def _error_result(self, error_msg: str, junior_suggestion: dict, tenant_id: str) -> dict:
        return {
            "review_id": f"SR-ERROR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "reviewed_by": self.agent_name,
            "tenant_id": tenant_id,
            "decision": "RETURN_TO_JUNIOR",
            "error": error_msg,
            "original_suggestion_id": junior_suggestion.get("suggestion_id", "unknown"),
            "recommendation": "Senior Accountant review failed due to system error. Manual review required."
        }
