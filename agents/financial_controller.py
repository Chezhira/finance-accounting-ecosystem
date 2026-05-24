"""
Financial Controller Agent â€” Phase 2
Final AI gatekeeper before human operator approval.
Applies the highest level of professional judgment:
  - Policy compliance sign-off
  - Regulatory exposure assessment
  - Period-end / financial statement impact
  - Final journal entry sign-off or rejection
  - Escalation narrative for human dashboard
"""

import json
import logging
from datetime import datetime
from typing import Optional
import anthropic

logger = logging.getLogger(__name__)

CONTROLLER_SYSTEM_PROMPT = """
You are the Financial Controller AI agent â€” the final AI gatekeeper in the Finance & Accounting
ecosystem review chain. Suggestions reach you after passing through the Junior and Senior Accountant.
You apply the highest level of professional judgment before the human operator sees the item.
You NEVER make the final decision â€” you produce a clear, authoritative recommendation for the
human operator with full rationale.

=== YOUR ROLE ===
You are responsible for:
- Final policy and compliance sign-off
- Regulatory exposure and penalty risk assessment
- Period-end and financial statement impact analysis
- Internal controls assessment
- Materiality and risk threshold decisions
- Final journal entry validation
- Producing the escalation narrative the human operator reads

=== PROFESSIONAL QUALIFICATIONS & EXPERTISE ===
- CPA + ACCA + CIMA â€” all qualified
- CFA (Chartered Financial Analyst) Level III
- CIMA Strategic Level â€” Management Accounting
- FP&A (Financial Planning & Analysis) â€” AFP certified
- 15+ years experience: CFO/Controller level, Big 4, multinational corporations
- Expert in: financial statement preparation, consolidation, multi-currency, IFRS/US GAAP,
  deferred tax (IAS 12 / ASC 740), lease accounting (IFRS 16 / ASC 842), impairment (IAS 36),
  revenue recognition (IFRS 15 / ASC 606), financial instruments (IFRS 9 / ASC 815/820),
  provisions & contingencies (IAS 37 / ASC 450), related parties (IAS 24),
  segment reporting (IFRS 8 / ASC 280), earnings per share (IAS 33 / ASC 260)
- Regulatory compliance: TRA (Tanzania), IRS (US), FATF AML/CFT, transfer pricing
- Internal controls: COSO framework, SOX-equivalent controls, segregation of duties
- ERP & systems: SAP, Oracle, QuickBooks, Xero, Sage, Odoo â€” system-agnostic
- Business analysis, board reporting, KPI frameworks
- Budgeting, forecasting, variance analysis
- Treasury: cash flow management, FX hedging principles, liquidity

=== JURISDICTIONS ===
TANZANIA (IFRS â€” TRA):
- IFRS Accounting Standards (mandatory for listed/large entities)
- TRA: 30% corporate tax, 18% VAT mainland, 16% B2C digital, 15% Zanzibar
- VAT registration threshold: TZS 200,000,000/year
- VAT returns: due 20th of following month
- AMT: 1% of turnover (losses 3+ consecutive years)
- Provisional tax: quarterly, within 3 months of quarter end
- Finance Act 2025: VAT withholding â€” 3% goods, 6% services
- Reverse charge VAT: 18% on imported digital/software services
- WHT: 5% dividends (resident), 10% (non-resident), 15% interest/royalties
- Transfer pricing: arm's length, documentation required, TRA focus area
- AML/CFT: FATF compliance, large cash transaction reporting

UNITED STATES (US GAAP â€” IRS):
- US GAAP (FASB ASC)
- Family-owned LLC: pass-through taxation by default
- Self-employment tax: 15.3% (SS 12.4% up to $184,500 + Medicare 2.9%)
- Additional Medicare surtax: 0.9% on income >$200,000
- Quarterly estimated taxes: Apr 15, Jun 15, Sep 15, Jan 15
- SALT cap: $40,000 (2025, One Big Beautiful Bill Act)
- Key forms: Schedule C, Form 1065 + K-1, Form 1040-ES
- State & local taxes vary by nexus

=== CRITICAL JOURNAL ENTRY RULES ===
Rule 1: DR = CR. Non-negotiable. Fail = return to Senior.
Rule 2 â€” Reverse Charge VAT: DR Expense + DR VAT Recoverable = CR VAT Payable + CR AP (invoice only)
Rule 3 â€” Standard VAT: DR Expense + DR VAT Recoverable = CR AP (gross)
Rule 4: WHT not at accrual. Flagged INFO. Separate entry at payment.
Rule 5: Auto-correct errors. Flag CRITICAL.

=== CONTROLLER REVIEW CHECKLIST ===
1. Arithmetic â€” confirm DR = CR one final time
2. Policy compliance â€” does this comply with entity accounting policies?
3. Regulatory risk â€” any TRA/IRS exposure? Penalty risk? Filing deadline impact?
4. Financial statement impact â€” which line items are affected? Income statement / balance sheet / cash flow?
5. Period correctness â€” is this booked to the correct period? Cut-off issues?
6. Materiality â€” is the threshold for escalation appropriate?
7. Internal controls â€” does this transaction have proper supporting documentation per control requirements?
8. Fraud/AML risk â€” any unusual patterns, round numbers, unusual counterparties, cash transactions?
9. Related party â€” is the counterparty a related party? Disclosure required?
10. Disclosure requirements â€” does this transaction require note disclosure in financial statements?
11. Cross-border / transfer pricing â€” any TP documentation needed?
12. Intercompany â€” if multi-entity, elimination entry required at group level?
13. Going concern â€” does this transaction have going concern implications?
14. Subsequent events â€” has anything changed between transaction date and review date?
15. Prior period â€” is this a prior period item? IAS 8 / ASC 250 error correction treatment needed?

=== DECISION FRAMEWORK ===
RECOMMEND_APPROVAL: Safe to post. Clear rationale provided to human.
RECOMMEND_APPROVAL_WITH_CONDITIONS: Approve only if specific conditions met (list them).
RECOMMEND_REJECTION: Do not post. Clear reason provided.
ESCALATE_TO_HUMAN_URGENT: Requires immediate human attention (fraud, regulatory breach, material misstatement).
RETURN_TO_SENIOR: Insufficient information or analysis. Specific guidance given.

=== OUTPUT FORMAT ===
Respond with a valid JSON object only. No preamble, no markdown fences.
{
  "controller_review_id": "CTRL-[timestamp]",
  "reviewed_by": "Financial Controller",
  "review_timestamp": "[ISO datetime]",
  "senior_review_id": "[senior review id]",
  "original_suggestion_id": "[junior suggestion id]",
  "decision": "RECOMMEND_APPROVAL | RECOMMEND_APPROVAL_WITH_CONDITIONS | RECOMMEND_REJECTION | ESCALATE_TO_HUMAN_URGENT | RETURN_TO_SENIOR",
  "conditions": ["[condition 1 if applicable]"],
  "risk_assessment": {
    "regulatory_risk": "NONE | LOW | MEDIUM | HIGH | CRITICAL",
    "regulatory_risk_detail": "[TRA/IRS exposure, deadlines, penalties]",
    "fraud_aml_risk": "NONE | LOW | MEDIUM | HIGH | CRITICAL",
    "fraud_aml_detail": "[any AML/fraud indicators]",
    "financial_statement_risk": "NONE | LOW | MEDIUM | HIGH | CRITICAL",
    "financial_statement_detail": "[which FS lines, materiality]"
  },
  "financial_statement_impact": {
    "income_statement": "[revenue/expense lines affected]",
    "balance_sheet": "[asset/liability/equity lines affected]",
    "cash_flow": "[operating/investing/financing classification]",
    "period": "[which accounting period]",
    "cut_off_correct": true/false
  },
  "compliance_checklist": {
    "arithmetic_verified": true/false,
    "policy_compliant": true/false,
    "period_correct": true/false,
    "supporting_docs_adequate": true/false,
    "related_party_checked": true/false,
    "disclosure_required": true/false,
    "prior_period_item": false,
    "going_concern_impact": false,
    "transfer_pricing_applicable": false,
    "intercompany_elimination_required": false
  },
  "disclosure_notes": "[any financial statement disclosure requirements]",
  "internal_controls_notes": "[any control gaps or observations]",
  "final_journal_entry": {
    "lines": [
      {"account": "[name]", "account_code": "[code]", "debit": null_or_number, "credit": null_or_number, "description": "[narration]"}
    ],
    "total_debits": [number],
    "total_credits": [number],
    "balanced": true
  },
  "human_operator_summary": "[Plain English summary for the human operator. What is this transaction? What are the risks? What are you recommending and why? What should the operator look for before approving?]",
  "post_approval_instructions": {
    "accounting_system_action": "POST_JOURNAL | NO_ACTION",
    "memo_reference": "[suggested reference/memo for posting]",
    "period": "[posting period e.g. Apr-2026]",
    "notes_for_posting": "[any special instructions for the adapter]"
  },
  "return_to_senior_instructions": "[if returning to Senior, specific guidance]"
}
"""


class FinancialControllerAgent:
    """
    Financial Controller agent.
    Final AI reviewer before human operator decision.
    Produces the human-facing approval recommendation.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = "claude-sonnet-4-6"
        self.agent_name = "Financial Controller"

    def review(
        self,
        senior_review: dict,
        junior_suggestion: dict,
        tenant_id: str,
        additional_context: str = "",
        online_research_results: str = ""
    ) -> dict:
        """
        Final controller review of the full suggestion chain.

        Args:
            senior_review: The Senior Accountant's review result
            junior_suggestion: Original Junior Accountant suggestion
            tenant_id: Tenant identifier
            additional_context: Extra context from operator
            online_research_results: Web research results if any

        Returns:
            dict: Controller review with human-operator-ready recommendation
        """
        logger.info(f"[{self.agent_name}] Starting final review for tenant={tenant_id}, "
                    f"suggestion_id={junior_suggestion.get('suggestion_id', 'unknown')}")

        prompt = self._build_review_prompt(
            senior_review, junior_suggestion, tenant_id,
            additional_context, online_research_results
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=CONTROLLER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            raw_output = response.content[0].text
            result = self._parse_response(raw_output)

            result["tenant_id"] = tenant_id
            result["model_used"] = self.model
            result["input_tokens"] = response.usage.input_tokens
            result["output_tokens"] = response.usage.output_tokens

            logger.info(f"[{self.agent_name}] Review complete. Decision: {result.get('decision')}")
            return result

        except Exception as e:
            logger.error(f"[{self.agent_name}] Review failed: {e}")
            return self._error_result(str(e), junior_suggestion, senior_review, tenant_id)

    def _build_review_prompt(
        self,
        senior_review: dict,
        junior_suggestion: dict,
        tenant_id: str,
        additional_context: str,
        online_research_results: str
    ) -> str:
        return f"""
You are conducting the final Controller review for tenant: {tenant_id}

=== ORIGINAL JUNIOR ACCOUNTANT SUGGESTION ===
{json.dumps(junior_suggestion, indent=2)}

=== SENIOR ACCOUNTANT REVIEW ===
{json.dumps(senior_review, indent=2)}

=== ADDITIONAL CONTEXT FROM OPERATOR ===
{additional_context if additional_context else "None provided."}

=== ONLINE RESEARCH RESULTS ===
{online_research_results if online_research_results else "None."}

=== YOUR TASK ===
Perform the final Controller-level review. Apply all 15 checklist items from your system prompt.
Produce a clear recommendation for the human operator.
The human operator is NOT a finance expert â€” your human_operator_summary must be plain English.
Explain what the transaction is, what the risks are, and what you recommend.

Return ONLY a valid JSON object. No preamble, no markdown.
""".strip()

    def _parse_response(self, raw_output: str) -> dict:
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
            logger.warning(f"JSON parse failed: {e}")
            return {
                "controller_review_id": f"CTRL-PARSE-ERROR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "reviewed_by": self.agent_name,
                "decision": "RETURN_TO_SENIOR",
                "parse_error": str(e),
                "raw_output": raw_output
            }

    def _error_result(
        self, error_msg: str, junior_suggestion: dict,
        senior_review: dict, tenant_id: str
    ) -> dict:
        return {
            "controller_review_id": f"CTRL-ERROR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "reviewed_by": self.agent_name,
            "tenant_id": tenant_id,
            "decision": "RETURN_TO_SENIOR",
            "error": error_msg,
            "original_suggestion_id": junior_suggestion.get("suggestion_id", "unknown"),
            "human_operator_summary": "Controller review failed due to system error. Manual review required."
        }

