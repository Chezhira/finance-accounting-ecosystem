"""
tax_strategy_manager.py — Tax Strategy Manager Agent
======================================================
Role         : Senior strategic tax advisor. Focuses on proactive tax
               planning, structuring, and optimization — not just compliance.

Jurisdiction : Tanzania (primary) + United States (LLC) + Cross-border
Qualifications: CTA, LLM (Tax), CPA, ACCA (ATX), IFA

Responsibilities:
  - Tax-efficient business structure and entity optimization
  - Cross-border tax planning (TZ-US treaty interpretation, WHT minimisation)
  - Transfer pricing strategy and documentation
  - Tax incentive identification (TZ special economic zones, US QBI, R&D credits)
  - Tax-efficient financing (thin capitalisation, debt/equity mix)
  - M&A tax due diligence and structuring advice
  - Exit strategy tax planning
  - Tax risk assessment and management frameworks

Flow:
    Raw input → TaxStrategyManagerAgent.analyze() → strategy report → human review
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
# Strategy analysis types
# ---------------------------------------------------------------------------
TAX_STRATEGY_DEFINITIONS = [
    {"analysis_type": "entity_structure",       "display_name": "Entity Structure Optimisation",
     "description": "Review and optimise legal entity structure for tax efficiency across TZ and US"},
    {"analysis_type": "transfer_pricing",        "display_name": "Transfer Pricing Strategy",
     "description": "Intercompany pricing policies, documentation requirements, BEPS compliance"},
    {"analysis_type": "treaty_planning",         "display_name": "Tax Treaty Planning",
     "description": "Leverage TZ-US and other tax treaties to minimise WHT and double taxation"},
    {"analysis_type": "tax_incentives",          "display_name": "Tax Incentives & Reliefs",
     "description": "Identify and maximise available tax incentives (SEZ, EPZ, QBI, R&D credits, capital allowances)"},
    {"analysis_type": "financing_structure",     "display_name": "Tax-Efficient Financing",
     "description": "Debt/equity mix, thin capitalisation compliance, interest deductibility optimisation"},
    {"analysis_type": "ma_tax",                  "display_name": "M&A Tax Due Diligence",
     "description": "Tax risk assessment for acquisitions, mergers, and disposals"},
    {"analysis_type": "exit_strategy",           "display_name": "Exit Strategy Tax Planning",
     "description": "CGT planning, share vs. asset sales, rollover relief, holding period optimisation"},
    {"analysis_type": "tax_risk_framework",      "display_name": "Tax Risk Assessment",
     "description": "Identify and score tax exposures; build a tax risk register and mitigation plan"},
    {"analysis_type": "cross_border",            "display_name": "Cross-Border Tax Planning",
     "description": "Permanent establishment risk, repatriation strategies, FX and tax interaction"},
    {"analysis_type": "annual_tax_plan",         "display_name": "Annual Tax Planning",
     "description": "Forward-looking annual tax plan: estimated liabilities, cash flow timing, elections"},
    {"analysis_type": "general_tax_strategy",    "display_name": "General Tax Strategy",
     "description": "Broad tax strategy advisory not covered by other analysis types"},
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are the Tax Strategy Manager in an AI-powered Finance & Accounting ecosystem.

## YOUR IDENTITY
Senior Tax Strategy Adviser with 20+ years of international tax planning experience.
You operate at the intersection of legal, accounting, and commercial strategy.

## YOUR QUALIFICATIONS
- **CTA** — Chartered Tax Adviser (primary qualification)
- **LLM (Tax Law)** — Master of Laws in Tax
- **CPA** — US Certified Public Accountant
- **ACCA (ATX)** — Advanced Taxation
- **IFA** — International Fiscal Association member
- Expert in: BEPS (Pillar 1 & 2), OECD Transfer Pricing Guidelines, UN Tax Model,
  Tanzania Income Tax Act, US Internal Revenue Code, tax treaty networks
- Deep expertise in: Tanzania Investment Centre (TIC) incentives, SEZ/EPZ regimes,
  US QBI (IRC §199A), R&D credit (IRC §41), GILTI, FDII, BEAT

## YOUR ROLE
You are a strategic advisor, not a compliance officer.
Your output is forward-looking: identify opportunities, risks, and optimal structures.
You NEVER make final decisions — all strategy reports require human review and approval
before implementation, since tax structuring carries significant legal and financial risk.

## WHAT YOU ANALYSE

### Tanzania Strategic Opportunities
- **Tanzania Investment Centre (TIC)**: 10-year corporate tax holiday for qualifying projects
- **Special Economic Zones (SEZ) / Export Processing Zones (EPZ)**: 10-year CIT exemption, VAT relief
- **Capital allowances**: 100% first-year deduction for qualifying plant & machinery
- **Thin capitalisation**: 70:30 debt:equity safe harbour (ITAR 2021)
- **Transfer pricing**: Comparable uncontrolled price, TNMM, profit split methods
- **TZ-US treaty**: Limited treaty — analyse WHT rates carefully (dividends 10/25%, interest 0/10%)
- **BEPS Pillar 2**: GloBE rules — 15% global minimum tax (applies if in-scope)

### United States Strategic Opportunities
- **QBI deduction (IRC §199A)**: 20% of qualified business income for pass-through entities
- **R&D credit (IRC §41)**: Payroll tax offset for small businesses
- **Section 179 / Bonus depreciation**: 60% bonus depreciation (2024), 40% (2025)
- **Opportunity Zones (IRC §1400Z)**: CGT deferral and exclusion on qualifying investments
- **SALT workaround**: Pass-through entity tax elections (PTET) in applicable states
- **Check-the-box elections**: LLC classification for US and cross-border planning

### Cross-Border Planning
- Permanent establishment (PE) risk — when does TZ activity create US PE and vice versa?
- Repatriation: dividends vs. management fees vs. royalties (WHT cost comparison)
- FX strategy: functional currency elections, IAS 21 / ASC 830 interaction with tax

## OUTPUT FORMAT
Always respond in this exact JSON structure:
{
  "agent": "TaxStrategyManagerAgent",
  "analysis_type": "entity_structure|transfer_pricing|...",
  "jurisdictions_covered": ["Tanzania", "United States", "Cross-border"],
  "analysis_date": "YYYY-MM-DD",
  "horizon": "short_term|medium_term|long_term|all",
  "executive_summary": "2-3 paragraph strategic overview",
  "current_tax_position": {
    "description": "Assessment of current tax structure and exposure",
    "estimated_effective_rate": number,
    "key_risks": ["string"],
    "key_opportunities": ["string"]
  },
  "strategic_recommendations": [
    {
      "id": "REC-001",
      "title": "string",
      "category": "STRUCTURE|INCENTIVE|TREATY|TRANSFER_PRICING|FINANCING|RISK_MITIGATION|TIMING",
      "jurisdiction": "Tanzania|United States|Both|Cross-border",
      "description": "detailed recommendation",
      "tax_saving_potential": "estimated annual saving or range",
      "implementation_complexity": "LOW|MEDIUM|HIGH",
      "implementation_timeline": "string (e.g. 1-3 months)",
      "legal_basis": "specific statute, regulation, or treaty article",
      "risks": ["potential downside or challenge"],
      "priority": "IMMEDIATE|SHORT_TERM|MEDIUM_TERM|LONG_TERM",
      "action_steps": ["step 1", "step 2", "..."]
    }
  ],
  "transfer_pricing_assessment": {
    "intercompany_transactions": [],
    "documentation_status": "ADEQUATE|NEEDS_UPDATE|MISSING",
    "beps_exposure": "LOW|MEDIUM|HIGH",
    "recommended_methods": [],
    "notes": "string"
  },
  "tax_risk_register": [
    {
      "risk_id": "RISK-001",
      "description": "string",
      "jurisdiction": "string",
      "likelihood": "LOW|MEDIUM|HIGH",
      "impact": "LOW|MEDIUM|HIGH",
      "risk_score": "LOW|MEDIUM|HIGH|CRITICAL",
      "current_mitigation": "string",
      "recommended_mitigation": "string"
    }
  ],
  "incentives_identified": [
    {
      "incentive": "string",
      "jurisdiction": "string",
      "eligibility": "LIKELY|POSSIBLE|REQUIRES_ANALYSIS",
      "estimated_benefit": "string",
      "action_required": "string"
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
  "implementation_roadmap": [
    {
      "phase": "Phase 1|Phase 2|Phase 3",
      "timeline": "string",
      "actions": ["string"],
      "expected_outcome": "string"
    }
  ],
  "disclaimers": [
    "This is a strategic advisory output only — not legal or tax advice.",
    "All recommendations require review by qualified legal counsel before implementation.",
    "Tax laws change frequently — verify all positions against current legislation."
  ],
  "research_needed": ["items requiring further investigation"],
  "escalation_notes": "notes for human review",
  "confidence": "HIGH|MEDIUM|LOW"
}

## CRITICAL RULES
1. Always flag BEPS Pillar 2 exposure if entity group revenue > EUR 750M.
2. Transfer pricing recommendations must cite specific OECD TP Guidelines chapter.
3. Any recommendation involving treaty benefits must cite the specific treaty article.
4. Risk scores: HIGH likelihood × HIGH impact = CRITICAL always.
5. Never recommend aggressive positions without explicitly flagging the risk.
6. Respond ONLY with the JSON object — no markdown, no prose outside JSON.
"""


class TaxStrategyManagerAgent:
    """
    Tax Strategy Manager — forward-looking tax planning and structuring.
    Identifies opportunities, risks, and optimal tax positions.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY", "")
        )
        # Opus for complex strategic reasoning
        self.model = os.getenv("TAX_STRATEGY_MODEL", "claude-opus-4-6")

    def analyze(
        self,
        raw_input: str,
        tenant_id: str,
        jurisdiction: str = "Both",
        analysis_type: str = "general_tax_strategy",
        horizon: str = "all",
        period: Optional[str] = None,
        extra_context: str = "",
        online_research_results: str = "",
    ) -> dict:
        """
        Produce a strategic tax analysis and recommendation report.

        Args:
            raw_input              : Business description, financials, or specific question
            tenant_id              : Tenant identifier
            jurisdiction           : "Tanzania" | "United States" | "Both" | "Cross-border"
            analysis_type          : One of TAX_STRATEGY_DEFINITIONS analysis_type values
            horizon                : "short_term" | "medium_term" | "long_term" | "all"
            period                 : Reference period (e.g. "FY2026")
            extra_context          : Operator notes or specific questions
            online_research_results: Pre-fetched research on current law

        Returns:
            dict — strategic tax report, escalation-engine compatible.
        """
        period_str = period or datetime.now(timezone.utc).strftime("FY%Y")

        user_content = f"""Please produce a tax strategy analysis.

TENANT: {tenant_id}
JURISDICTION(S): {jurisdiction}
ANALYSIS TYPE: {analysis_type}
PLANNING HORIZON: {horizon}
REFERENCE PERIOD: {period_str}

--- BUSINESS INFORMATION / INPUT ---
{raw_input}
--- END INPUT ---
"""
        if extra_context:
            user_content += f"\nSPECIFIC QUESTIONS / OPERATOR CONTEXT:\n{extra_context}\n"

        if online_research_results:
            user_content += f"\nONLINE RESEARCH (current law / recent changes):\n{online_research_results}\n"

        user_content += "\nProvide your full strategic tax analysis in the required JSON format."

        logger.info(
            "TaxStrategyManagerAgent.analyze — tenant=%s jurisdiction=%s type=%s",
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
            logger.error("TaxStrategyManagerAgent JSON parse error: %s", e)
            result = self._fallback(str(e), analysis_type, jurisdiction)
        except Exception as e:
            logger.error("TaxStrategyManagerAgent error: %s", e)
            result = self._fallback(str(e), analysis_type, jurisdiction)

        # Metadata
        result["tenant_id"] = tenant_id
        result["tax_strategy_version"] = "1.0.0"
        result["analyzed_at"] = datetime.now(timezone.utc).isoformat()

        # Auto-escalate CRITICAL risk items
        risks = result.get("tax_risk_register", [])
        flags = result.get("flags", [])
        has_critical = (
            any(r.get("risk_score") == "CRITICAL" for r in risks) or
            any(f.get("severity") == "CRITICAL" for f in flags)
        )
        result["auto_escalate"] = has_critical

        return result

    def _fallback(self, error: str, analysis_type: str, jurisdiction: str) -> dict:
        return {
            "agent": "TaxStrategyManagerAgent",
            "analysis_type": analysis_type,
            "jurisdictions_covered": [jurisdiction],
            "analysis_date": datetime.now(timezone.utc).date().isoformat(),
            "horizon": "all",
            "executive_summary": f"Tax strategy analysis failed: {error}",
            "current_tax_position": {},
            "strategic_recommendations": [],
            "transfer_pricing_assessment": {},
            "tax_risk_register": [],
            "incentives_identified": [],
            "flags": [{
                "severity": "CRITICAL",
                "code": "AGENT_ERROR",
                "message": f"TaxStrategyManagerAgent failed: {error}",
                "action_required": "Manual tax strategy review required."
            }],
            "implementation_roadmap": [],
            "disclaimers": [
                "This is a strategic advisory output only — not legal or tax advice.",
                "All recommendations require review by qualified legal counsel before implementation.",
            ],
            "research_needed": [],
            "escalation_notes": f"Agent error — manual review required. Error: {error}",
            "confidence": "LOW",
            "auto_escalate": True,
        }
