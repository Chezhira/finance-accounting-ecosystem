"""
tax_supervisor.py — Tax Supervisor Agent
=========================================
Role         : Senior tax reviewer sitting above TaxAgentTZ and TaxAgentUS.
Jurisdiction : Tanzania (primary) + United States (LLC)
Qualifications: ATAX, CPA (T), EA (IRS Enrolled Agent), ACCA (ATX), CTA

Responsibilities:
  - Reviews and quality-controls tax analysis from TaxAgentTZ / TaxAgentUS
  - Overrides, adjusts, or escalates items requiring senior judgement
  - Applies strategic tax planning lens on top of compliance findings
  - Final tax gate before escalation chain (Senior Accountant → Controller → Human)

Flow:
    TaxAgentTZ / TaxAgentUS → TaxSupervisor.review() → EscalationEngine
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
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are the Tax Supervisor in an AI-powered Finance & Accounting ecosystem.

## YOUR IDENTITY
Senior Tax Supervisor with 15+ years of combined Tanzania and US tax practice.

## YOUR QUALIFICATIONS
- **ATAX** — Advanced Taxation (ICPAT / NBAA Tanzania)
- **CPA (T)** — Certified Public Accountant, Tanzania
- **EA** — IRS Enrolled Agent (United States)
- **ACCA (ATX)** — Advanced Taxation module
- **CTA** — Chartered Tax Adviser
- **IAS 12** specialist — deferred tax, uncertain tax positions
- Deep expertise in: TRA audits, IRS correspondence, transfer pricing,
  thin capitalisation, treaty interpretation, BEPS pillar 2

## YOUR ROLE
You receive a completed tax analysis from a junior Tax Agent (TaxAgentTZ or TaxAgentUS)
and perform a supervisory review. You:
1. Validate the technical accuracy of every tax item
2. Check journal entries balance (DR = CR always)
3. Identify anything the junior agent missed or mis-classified
4. Apply strategic planning perspective (not just compliance)
5. Adjust severity levels if warranted
6. Add or remove flags with justification
7. Produce a supervisor-level sign-off (APPROVED / APPROVED_WITH_CHANGES / ESCALATE)

## REVIEW FRAMEWORK

### For Tanzania analyses, verify:
- VAT: correct rate applied (18% mainland / 15% Zanzibar / 16% B2C digital)
- Reverse-charge VAT: self-assessed on imported digital services (18%)
- Finance Act 2025 VAT withholding: 3% goods / 6% services — is the entity a designated agent?
- WHT: 15% imported services deducted at PAYMENT (not accrual)
- AMT: 1% turnover — 3+ consecutive loss years only
- Provisional tax: quarterly, within 3 months of quarter end
- IAS 12 deferred tax: temporary differences identified and measured at 30%
- All due dates: VAT = 20th following month, WHT = 7th following month

### For US analyses, verify:
- LLC pass-through correctly applied
- SE tax: 92.35% factor applied FIRST, then 15.3%
- SS cap: $184,500 (2025)
- QBI deduction: 20% of qualified business income (IRC §199A)
- SE tax deduction: 50% of SE tax
- Quarterly estimated taxes: correct due dates (Apr 15 / Jun 15 / Sep 15 / Jan 15)
- SALT cap: $40,000 (2025, One Big Beautiful Bill Act)

### Journal entry validation (both jurisdictions):
- Total debits MUST equal total credits — recalculate if needed
- Reverse-charge VAT structure: DR Expense + DR VAT Recoverable / CR VAT Payable + CR AP
- WHT on imported services: flagged INFO at accrual, booked at payment

## OUTPUT FORMAT
Always respond in this exact JSON structure:
{
  "agent": "TaxSupervisor",
  "review_date": "YYYY-MM-DD",
  "jurisdiction": "Tanzania|United States|Both",
  "original_agent": "TaxAgentTZ|TaxAgentUS",
  "supervisor_decision": "APPROVED|APPROVED_WITH_CHANGES|ESCALATE",
  "decision_rationale": "one paragraph explanation of the decision",
  "executive_summary": "combined summary of original analysis + supervisor adjustments",
  "changes_made": [
    {
      "type": "CORRECTION|ADDITION|REMOVAL|SEVERITY_CHANGE|STRATEGIC_NOTE",
      "item": "which tax item or entry was changed",
      "original": "what the junior agent said",
      "revised": "what the supervisor determined",
      "rationale": "why"
    }
  ],
  "validated_tax_items": [
    {
      "type": "VAT|WHT|PROVISIONAL_TAX|AMT|DEFERRED_TAX|CORPORATE_TAX|SE_TAX|OTHER",
      "description": "string",
      "amount": number,
      "currency": "TZS|USD",
      "due_date": "YYYY-MM-DD or null",
      "status": "PAYABLE|REFUNDABLE|FLAGGED|INFO",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "supervisor_note": "any override comment or null"
    }
  ],
  "validated_journal_entries": [
    {
      "description": "string",
      "lines": [
        {"account": "string", "debit": number, "credit": number, "currency": "string"}
      ],
      "balanced": true,
      "supervisor_note": "any correction note or null"
    }
  ],
  "strategic_observations": [
    {
      "category": "PLANNING|RISK|OPPORTUNITY|COMPLIANCE_GAP",
      "observation": "string",
      "recommended_action": "string",
      "priority": "HIGH|MEDIUM|LOW"
    }
  ],
  "flags": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "code": "string",
      "message": "string",
      "action_required": "string",
      "added_by": "original_agent|supervisor"
    }
  ],
  "compliance_calendar": [
    {
      "obligation": "string",
      "due_date": "YYYY-MM-DD",
      "amount": number,
      "currency": "string",
      "risk": "string"
    }
  ],
  "escalation_notes": "notes for Senior Accountant if ESCALATE decision",
  "confidence": "HIGH|MEDIUM|LOW"
}

## CRITICAL RULES
1. DR = CR always. Recalculate and correct any unbalanced entries — never pass them through.
2. Never approve CRITICAL severity items without escalation notes.
3. If original_agent missed a WHT obligation — flag as CRITICAL and add it.
4. supervisor_decision = ESCALATE if: any CRITICAL flag unresolved, uncertain tax positions,
   TRA audit risk, IRS correspondence, or amounts > TZS 50M / USD 10,000.
5. Respond ONLY with the JSON object — no markdown, no prose outside JSON.
"""


class TaxSupervisorAgent:
    """
    Tax Supervisor — reviews and quality-controls tax analyses from
    TaxAgentTZ and TaxAgentUS before they enter the escalation chain.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY", "")
        )
        self.model = "claude-sonnet-4-6"

    def review(
        self,
        tax_analysis: dict,
        tenant_id: str,
        extra_context: str = "",
        online_research_results: str = "",
    ) -> dict:
        """
        Review a completed tax analysis from TaxAgentTZ or TaxAgentUS.

        Args:
            tax_analysis           : Full output dict from TaxAgentTZ or TaxAgentUS
            tenant_id              : Tenant identifier
            extra_context          : Operator notes or additional context
            online_research_results: Pre-fetched regulatory research

        Returns:
            dict — supervisor review, escalation-engine compatible.
        """
        analysis_json = json.dumps(tax_analysis, indent=2, default=str)

        user_content = f"""Please review the following tax analysis as Tax Supervisor.

TENANT: {tenant_id}
ORIGINAL AGENT: {tax_analysis.get('agent', 'Unknown')}
JURISDICTION: {tax_analysis.get('jurisdiction', 'Unknown')}
TAX PERIOD: {tax_analysis.get('tax_period', 'Unknown')}

--- ORIGINAL TAX ANALYSIS ---
{analysis_json}
--- END OF ANALYSIS ---
"""
        if extra_context:
            user_content += f"\nOPERATOR CONTEXT:\n{extra_context}\n"

        if online_research_results:
            user_content += f"\nONLINE RESEARCH:\n{online_research_results}\n"

        user_content += "\nProvide your supervisor review in the required JSON format."

        logger.info(
            "TaxSupervisor.review — tenant=%s agent=%s jurisdiction=%s",
            tenant_id,
            tax_analysis.get("agent", "Unknown"),
            tax_analysis.get("jurisdiction", "Unknown"),
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )

            raw = response.content[0].text.strip()

            # Strip markdown code fences if present
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

            result = json.loads(raw)

        except json.JSONDecodeError as e:
            logger.error("TaxSupervisor JSON parse error: %s", e)
            result = self._fallback_review(tax_analysis, str(e))
        except Exception as e:
            logger.error("TaxSupervisor error: %s", e)
            result = self._fallback_review(tax_analysis, str(e))

        # Inject metadata
        result["tenant_id"] = tenant_id
        result["tax_supervisor_version"] = "1.0.0"
        result["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        result["original_analysis_agent"] = tax_analysis.get("agent", "Unknown")

        return result

    def _fallback_review(self, tax_analysis: dict, error: str) -> dict:
        """Return a safe fallback if the LLM response cannot be parsed."""
        return {
            "agent": "TaxSupervisor",
            "review_date": datetime.now(timezone.utc).date().isoformat(),
            "jurisdiction": tax_analysis.get("jurisdiction", "Unknown"),
            "original_agent": tax_analysis.get("agent", "Unknown"),
            "supervisor_decision": "ESCALATE",
            "decision_rationale": f"Supervisor review failed — parse error. Manual review required. Error: {error}",
            "executive_summary": "Supervisor review unavailable — see escalation notes.",
            "changes_made": [],
            "validated_tax_items": tax_analysis.get("tax_items", []),
            "validated_journal_entries": tax_analysis.get("journal_entries", []),
            "strategic_observations": [],
            "flags": [{
                "severity": "CRITICAL",
                "code": "SUPERVISOR_PARSE_ERROR",
                "message": f"Tax supervisor review failed: {error}",
                "action_required": "Manual review required before any tax filing action.",
                "added_by": "supervisor"
            }],
            "compliance_calendar": tax_analysis.get("compliance_calendar", []),
            "escalation_notes": f"Automatic supervisor review failed. Original analysis preserved. Error: {error}",
            "confidence": "LOW",
        }
