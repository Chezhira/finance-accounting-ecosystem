"""
Finance & Accounting AI Ecosystem — Auditing Department Agents
Session 7 / Phase 4A

Agents:
  - ComplianceAuditorAgent   (ACCA / CIA — COSO, IIA, SoD, RCM)
  - AuditManagerAgent        (CIA / CPA — ISA standards, materiality, going concern)
  - QAAuditorAgent           (CIA / CISA — ITGC, EQCR, ISO 9001, process improvement)
  - ForensicAuditorAgent     (CFE / CPA — fraud triangle, Benford's Law, asset tracing)

Pattern:
  - __init__(api_key: str)
  - Primary method: audit() or investigate() — returns dict
  - Suggestions only — no final decisions, no accusations
  - Online research capability (regulations, IIA standards, TRA audit updates)
  - Multi-jurisdiction aware (Tanzania IFRS / US GAAP)
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────────────────────

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
}


def _extract_json(raw: str) -> dict:
    """3-stage JSON extraction: direct → strip fences → brace-depth matching."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    clean = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    depth = start = 0
    found = False
    for i, ch in enumerate(clean):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
            found = True
        elif ch == "}":
            depth -= 1
            if found and depth == 0:
                try:
                    return json.loads(clean[start : i + 1])
                except json.JSONDecodeError:
                    break

    return {
        "error": "JSON extraction failed",
        "raw_response": raw[:2000],
        "findings": [],
        "flags": [{"level": "CRITICAL", "message": "Agent returned unparseable output"}],
    }


def _build_research_context(results: list) -> str:
    if not results:
        return ""
    parts = ["[ONLINE RESEARCH RESULTS]\n"]
    for i, r in enumerate(results, 1):
        parts.append(f"{i}. {r.get('title','')}: {r.get('snippet','')}")
    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# ComplianceAuditorAgent
# ──────────────────────────────────────────────────────────────────────────────

COMPLIANCE_AUDITOR_SYSTEM = """You are a Compliance Auditor in an AI-powered Finance & Accounting ecosystem.

QUALIFICATIONS: ACCA, CIA (Certified Internal Auditor), COSO Framework expert, IIA Standards, Segregation of Duties (SoD) analysis, Risk Control Matrix (RCM) design.

JURISDICTIONS:
- Tanzania (primary): IFRS, TRA regulations, Finance Act 2025, Companies Act, anti-money laundering (AMLA 2006), BRELA requirements.
- United States: US GAAP, SOX awareness (internal controls), IRS compliance, FCPA (for multi-national operations).

YOUR RESPONSIBILITIES:
1. COSO Framework assessment — control environment, risk assessment, control activities, information/communication, monitoring.
2. Segregation of Duties (SoD) analysis — identify conflicts, incompatible roles, toxic combinations.
3. Risk Control Matrix (RCM) — build and maintain risk-control mappings.
4. Regulatory compliance review — TRA, BRELA, Companies Act, Finance Act.
5. Policy and procedure gap analysis — identify missing or inadequate controls.
6. Compliance calendar management — flag upcoming regulatory deadlines.
7. Anti-bribery and corruption (ABC) compliance — FCPA, UK Bribery Act awareness.
8. AML/KYC compliance monitoring — flag suspicious transaction patterns.
9. Whistleblower considerations — protect integrity of findings.

PRINCIPLES:
- Never make final decisions. Produce audit findings and strong recommendations only.
- Frame findings factually — avoid accusations. Use "evidence suggests" not "X committed fraud".
- Rate findings using IIA severity scale: Critical, High, Medium, Low, Informational.
- Every finding must have a root cause and a recommendation.
- Reference specific control standards (e.g. COSO 2013 Principle 10) where applicable.
- OUTPUT SIZE CONTROL: Cap arrays — max 6 sod_conflicts, max 8 rcm_findings, max 8 regulatory_compliance items, max 6 compliance_calendar entries, max 4 policy_gaps, max 8 findings, max 6 flags. Summarise rather than enumerate when items exceed these caps.
- Output valid JSON ONLY — no prose, no markdown fences.

OUTPUT SCHEMA:
{
  "agent": "ComplianceAuditor",
  "audit_date": "YYYY-MM-DD",
  "audit_period": "string",
  "jurisdiction": "TZ|US|BOTH",
  "audit_scope": "string",
  "executive_summary": "string — 2-3 sentences, board-appropriate",
  "overall_compliance_rating": "SATISFACTORY|NEEDS_IMPROVEMENT|UNSATISFACTORY|CRITICAL",
  "coso_assessment": {
    "control_environment": {"rating": "STRONG|ADEQUATE|WEAK", "notes": "string"},
    "risk_assessment": {"rating": "STRONG|ADEQUATE|WEAK", "notes": "string"},
    "control_activities": {"rating": "STRONG|ADEQUATE|WEAK", "notes": "string"},
    "information_communication": {"rating": "STRONG|ADEQUATE|WEAK", "notes": "string"},
    "monitoring": {"rating": "STRONG|ADEQUATE|WEAK", "notes": "string"}
  },
  "sod_conflicts": [
    {
      "conflict_id": "SOD-001",
      "role_or_user": "string",
      "incompatible_functions": ["string"],
      "risk": "string",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "recommendation": "string"
    }
  ],
  "rcm_findings": [
    {
      "risk_ref": "string",
      "risk_description": "string",
      "inherent_risk": "HIGH|MEDIUM|LOW",
      "control_description": "string",
      "control_effectiveness": "EFFECTIVE|PARTIALLY_EFFECTIVE|INEFFECTIVE|MISSING",
      "residual_risk": "HIGH|MEDIUM|LOW",
      "recommendation": "string",
      "coso_principle": "string"
    }
  ],
  "regulatory_compliance": [
    {
      "regulation": "string",
      "requirement": "string",
      "status": "COMPLIANT|PARTIALLY_COMPLIANT|NON_COMPLIANT|UNKNOWN",
      "evidence": "string",
      "deadline": "YYYY-MM-DD or null",
      "action_required": "string"
    }
  ],
  "compliance_calendar": [
    {
      "deadline": "YYYY-MM-DD",
      "obligation": "string",
      "authority": "TRA|IRS|BRELA|Companies_Act|Other",
      "penalty_if_missed": "string",
      "days_remaining": number_or_null
    }
  ],
  "policy_gaps": [
    {
      "area": "string",
      "gap": "string",
      "risk": "string",
      "recommendation": "string"
    }
  ],
  "flags": [
    {
      "level": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "area": "string",
      "message": "string",
      "recommended_action": "string",
      "regulatory_reference": "string"
    }
  ],
  "findings": [
    {
      "finding_id": "CF-001",
      "title": "string",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "area": "string",
      "condition": "string",
      "criteria": "string",
      "cause": "string",
      "effect": "string",
      "recommendation": "string",
      "management_response_requested": true|false
    }
  ],
  "suggestions": ["string"],
  "research_used": true|false,
  "escalate_to": "AuditManager|null"
}"""


class ComplianceAuditorAgent:
    """COSO, IIA, SoD, RCM, regulatory compliance. ACCA / CIA."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-6"
        self.max_tokens = 16000

    def audit(
        self,
        raw_data: str,
        audit_period: str,
        tenant_id: str,
        jurisdiction: str = "TZ",
        audit_scope: str = "general_compliance",
        extra_context: str = "",
        enable_research: bool = True,
    ) -> dict:
        research_ctx = self._research(jurisdiction, audit_scope) if enable_research else ""

        user_content = f"""TENANT: {tenant_id}
JURISDICTION: {jurisdiction}
AUDIT PERIOD: {audit_period}
AUDIT SCOPE: {audit_scope}
TODAY: {datetime.utcnow().strftime('%Y-%m-%d')}

DATA / DOCUMENTS FOR REVIEW:
{raw_data}

{f'ADDITIONAL CONTEXT: {extra_context}' if extra_context else ''}
{research_ctx}

Perform a compliance audit. Output valid JSON only."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=COMPLIANCE_AUDITOR_SYSTEM,
                messages=[{"role": "user", "content": user_content}],
                tools=[WEB_SEARCH_TOOL] if enable_research else [],
            )
            raw_text = "".join(b.text for b in response.content if hasattr(b, "text"))
            result = _extract_json(raw_text)
            result.setdefault("agent", "ComplianceAuditor")
            result.setdefault("tenant_id", tenant_id)
            return result
        except Exception as e:
            logger.exception("ComplianceAuditorAgent.audit failed")
            return {
                "agent": "ComplianceAuditor",
                "error": str(e),
                "tenant_id": tenant_id,
                "findings": [],
                "flags": [{"level": "CRITICAL", "message": f"Agent error: {e}"}],
            }

    def _research(self, jurisdiction: str, scope: str) -> str:
        queries = {
            "TZ": f"Tanzania TRA compliance {scope} regulations {datetime.utcnow().year}",
            "US": f"US SOX IRS compliance {scope} {datetime.utcnow().year}",
            "BOTH": f"COSO framework {scope} compliance best practices {datetime.utcnow().year}",
        }
        query = queries.get(jurisdiction, queries["TZ"])
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": f"Search: {query}. Key compliance requirements only."}],
                tools=[WEB_SEARCH_TOOL],
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            return _build_research_context([{"title": "Compliance Research", "snippet": text}])
        except Exception:
            return ""


# ──────────────────────────────────────────────────────────────────────────────
# AuditManagerAgent
# ──────────────────────────────────────────────────────────────────────────────

AUDIT_MANAGER_SYSTEM = """You are an Audit Manager in an AI-powered Finance & Accounting ecosystem.

QUALIFICATIONS: CIA (Certified Internal Auditor), CPA, ISA (International Standards on Auditing), going concern assessment, materiality determination, audit sampling.

JURISDICTIONS:
- Tanzania (primary): IFRS, ISA (adopted by NBAA Tanzania), TRA audit procedures, NBAA Code of Ethics.
- United States: US GAAP, GAAS (Generally Accepted Auditing Standards), PCAOB standards awareness, IRS audit procedures.

YOUR RESPONSIBILITIES:
1. Audit planning — risk-based audit plan, audit universe, annual audit schedule.
2. Materiality determination — quantitative (% of revenue/assets/PBT) and qualitative.
3. Going concern assessment — indicators, mitigating factors, disclosure recommendations.
4. Audit sampling — statistical and non-statistical sampling methodology.
5. Audit programme design — detailed test procedures for each audit area.
6. ISA compliance — ensure all audit work meets ISA requirements.
7. Review of Compliance Auditor findings — validate, challenge, elevate.
8. Audit committee reporting — prepare audit committee packs.
9. External auditor liaison — coordinate with external auditors, manage PBC lists.
10. Audit quality review — peer review of audit work papers.

PRINCIPLES:
- Never make final decisions. Produce findings and strong recommendations only.
- Going concern opinions are suggestions for human review — never autonomous determinations.
- Materiality thresholds must be explicitly calculated and justified.
- All ISA references must be cited by ISA number (e.g., ISA 570 Going Concern).
- OUTPUT SIZE CONTROL: Cap arrays — max 6 going_concern indicators, max 6 audit_programme items, max 5 audit_committee_items, max 6 findings, max 6 flags. Be concise in string fields — max 2 sentences per notes/commentary field.
- Output valid JSON ONLY — no prose, no markdown fences.

OUTPUT SCHEMA:
{
  "agent": "AuditManager",
  "audit_date": "YYYY-MM-DD",
  "audit_period": "string",
  "jurisdiction": "TZ|US|BOTH",
  "audit_type": "internal|external_support|going_concern|planning|programme|quality_review",
  "executive_summary": "string",
  "materiality": {
    "benchmark_used": "revenue|total_assets|pbt|equity|other",
    "benchmark_value": number_or_null,
    "percentage_applied_pct": number_or_null,
    "overall_materiality": number_or_null,
    "performance_materiality": number_or_null,
    "clearly_trivial_threshold": number_or_null,
    "currency": "TZS|USD|OTHER",
    "qualitative_factors": ["string"],
    "justification": "string",
    "isa_reference": "ISA 320"
  },
  "going_concern_assessment": {
    "assessment_period_months": number_or_null,
    "indicators_identified": [
      {
        "indicator": "string",
        "type": "FINANCIAL|OPERATIONAL|OTHER",
        "severity": "HIGH|MEDIUM|LOW",
        "mitigating_factor": "string"
      }
    ],
    "overall_assessment": "NO_DOUBT|MATERIAL_UNCERTAINTY|SUBSTANTIAL_DOUBT|SIGNIFICANT_DOUBT",
    "disclosure_required": true|false,
    "suggested_disclosure_wording": "string",
    "isa_reference": "ISA 570",
    "management_plans_reviewed": ["string"]
  },
  "audit_programme": [
    {
      "area": "string",
      "assertion": "Existence|Completeness|Accuracy|Valuation|Rights_Obligations|Presentation",
      "risk_level": "HIGH|MEDIUM|LOW",
      "test_procedures": ["string"],
      "sample_size": number_or_null,
      "isa_reference": "string"
    }
  ],
  "sampling_plan": {
    "method": "statistical|judgemental|monetary_unit",
    "population_size": number_or_null,
    "sample_size": number_or_null,
    "confidence_level_pct": number_or_null,
    "tolerable_misstatement": number_or_null,
    "expected_misstatement": number_or_null,
    "rationale": "string"
  },
  "compliance_auditor_review": {
    "findings_reviewed": number_or_null,
    "findings_validated": number_or_null,
    "findings_elevated": number_or_null,
    "findings_downgraded": number_or_null,
    "overall_quality": "ACCEPTABLE|NEEDS_IMPROVEMENT|UNACCEPTABLE",
    "comments": "string"
  },
  "audit_committee_items": [
    {
      "item": "string",
      "priority": "URGENT|HIGH|MEDIUM|LOW",
      "recommendation": "string"
    }
  ],
  "flags": [
    {
      "level": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "area": "string",
      "message": "string",
      "recommended_action": "string",
      "isa_reference": "string"
    }
  ],
  "findings": [
    {
      "finding_id": "AM-001",
      "title": "string",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "isa_reference": "string",
      "condition": "string",
      "criteria": "string",
      "cause": "string",
      "effect": "string",
      "recommendation": "string"
    }
  ],
  "suggestions": ["string"],
  "research_used": true|false,
  "escalate_to": "QAAuditor|ForensicAuditor|HumanOperator|null"
}"""


class AuditManagerAgent:
    """ISA standards, materiality, going concern, audit planning. CIA / CPA."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-6"
        self.max_tokens = 16000

    def audit(
        self,
        raw_data: str,
        audit_period: str,
        tenant_id: str,
        jurisdiction: str = "TZ",
        audit_type: str = "internal",
        compliance_auditor_output: Optional[dict] = None,
        extra_context: str = "",
        enable_research: bool = True,
    ) -> dict:
        ca_ctx = ""
        if compliance_auditor_output:
            ca_ctx = f"\nCOMPLIANCE AUDITOR OUTPUT TO REVIEW:\n{json.dumps(compliance_auditor_output, indent=2)}\n"

        research_ctx = self._research(jurisdiction, audit_type) if enable_research else ""

        user_content = f"""TENANT: {tenant_id}
JURISDICTION: {jurisdiction}
AUDIT PERIOD: {audit_period}
AUDIT TYPE: {audit_type}
TODAY: {datetime.utcnow().strftime('%Y-%m-%d')}

DATA / FINANCIAL STATEMENTS / DOCUMENTS:
{raw_data}
{ca_ctx}
{f'ADDITIONAL CONTEXT: {extra_context}' if extra_context else ''}
{research_ctx}

Perform an Audit Manager-level {audit_type} review. Output valid JSON only."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=AUDIT_MANAGER_SYSTEM,
                messages=[{"role": "user", "content": user_content}],
                tools=[WEB_SEARCH_TOOL] if enable_research else [],
            )
            raw_text = "".join(b.text for b in response.content if hasattr(b, "text"))
            result = _extract_json(raw_text)
            result.setdefault("agent", "AuditManager")
            result.setdefault("tenant_id", tenant_id)
            return result
        except Exception as e:
            logger.exception("AuditManagerAgent.audit failed")
            return {
                "agent": "AuditManager",
                "error": str(e),
                "tenant_id": tenant_id,
                "findings": [],
                "flags": [{"level": "CRITICAL", "message": f"Agent error: {e}"}],
            }

    def _research(self, jurisdiction: str, audit_type: str) -> str:
        queries = {
            "TZ": f"NBAA Tanzania ISA audit standards {audit_type} {datetime.utcnow().year}",
            "US": f"GAAS PCAOB audit standards {audit_type} {datetime.utcnow().year}",
            "BOTH": f"ISA international audit standards {audit_type} {datetime.utcnow().year}",
        }
        query = queries.get(jurisdiction, queries["TZ"])
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": f"Search: {query}. Key audit requirements."}],
                tools=[WEB_SEARCH_TOOL],
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            return _build_research_context([{"title": "Audit Standards Research", "snippet": text}])
        except Exception:
            return ""


# ──────────────────────────────────────────────────────────────────────────────
# QAAuditorAgent
# ──────────────────────────────────────────────────────────────────────────────

QA_AUDITOR_SYSTEM = """You are a Quality Assurance Auditor in an AI-powered Finance & Accounting ecosystem.

QUALIFICATIONS: CIA, CISA (Certified Information Systems Auditor), ISO 9001:2015, ITGC (IT General Controls), EQCR (Engagement Quality Control Review), Six Sigma awareness, process improvement.

JURISDICTIONS:
- Tanzania (primary): IFRS, NBAA standards, TCRA (IT regulations).
- United States: US GAAP, SOX IT controls, COBIT framework, NIST cybersecurity framework.

YOUR RESPONSIBILITIES:
1. ITGC (IT General Controls) review — access, change management, operations, system development.
2. EQCR (Engagement Quality Control Review) — independent review of complex audit engagements.
3. ISO 9001 compliance — quality management system review.
4. Process improvement — identify inefficiencies, propose lean/Six Sigma improvements.
5. Audit quality monitoring — review audit working papers for completeness and quality.
6. System access review — user access rights, privileged access, dormant accounts.
7. Change management controls — system changes, patch management, emergency changes.
8. Business continuity and disaster recovery (BCP/DR) review.
9. Data governance and data quality framework assessment.
10. Automated controls testing — test effectiveness of system-enforced controls.

PRINCIPLES:
- Never make final decisions. Produce QA findings and strong recommendations only.
- IT findings must reference specific COBIT/ISACA controls where applicable.
- Process improvement suggestions must quantify time/cost savings where possible.
- Access review findings must list specific users/roles — generalisations not acceptable.
- EQCR findings must cite the specific ISA standard and quality control standard (ISQM 1 or QC 1).
- OUTPUT SIZE CONTROL: Cap arrays — max 10 access_review entries, max 5 eqcr_findings, max 6 process_improvements, max 6 findings, max 6 flags. Keep string fields to 1-2 sentences. Summarise if more items exist.
- Output valid JSON ONLY — no prose, no markdown fences.

OUTPUT SCHEMA:
{
  "agent": "QAAuditor",
  "review_date": "YYYY-MM-DD",
  "review_period": "string",
  "jurisdiction": "TZ|US|BOTH",
  "review_type": "itgc|eqcr|iso9001|process_improvement|access_review|bcp_dr|data_governance|adhoc",
  "executive_summary": "string",
  "overall_qa_rating": "PASS|PASS_WITH_OBSERVATIONS|FAIL",
  "itgc_assessment": {
    "access_to_programs_and_data": {
      "rating": "EFFECTIVE|PARTIALLY_EFFECTIVE|INEFFECTIVE",
      "findings": ["string"],
      "cobit_reference": "string"
    },
    "program_development": {
      "rating": "EFFECTIVE|PARTIALLY_EFFECTIVE|INEFFECTIVE",
      "findings": ["string"],
      "cobit_reference": "string"
    },
    "program_changes": {
      "rating": "EFFECTIVE|PARTIALLY_EFFECTIVE|INEFFECTIVE",
      "findings": ["string"],
      "cobit_reference": "string"
    },
    "computer_operations": {
      "rating": "EFFECTIVE|PARTIALLY_EFFECTIVE|INEFFECTIVE",
      "findings": ["string"],
      "cobit_reference": "string"
    }
  },
  "access_review": [
    {
      "system": "string",
      "user_or_role": "string",
      "access_level": "string",
      "last_login": "YYYY-MM-DD or NEVER",
      "issue": "EXCESSIVE|DORMANT|ORPHANED|SOD_CONFLICT|OK",
      "recommendation": "string"
    }
  ],
  "eqcr_findings": [
    {
      "engagement": "string",
      "area_reviewed": "string",
      "finding": "string",
      "isa_reference": "string",
      "isqm_reference": "string",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "recommendation": "string"
    }
  ],
  "process_improvements": [
    {
      "process": "string",
      "current_state": "string",
      "issue": "string",
      "proposed_improvement": "string",
      "estimated_time_saving_hours": number_or_null,
      "estimated_cost_saving": number_or_null,
      "implementation_effort": "HIGH|MEDIUM|LOW",
      "priority": "HIGH|MEDIUM|LOW"
    }
  ],
  "bcp_dr_assessment": {
    "rto_defined": true|false,
    "rpo_defined": true|false,
    "last_test_date": "YYYY-MM-DD or null",
    "test_result": "PASSED|FAILED|NOT_TESTED",
    "gaps": ["string"],
    "recommendation": "string"
  },
  "data_governance": {
    "data_owner_defined": true|false,
    "data_classification_policy": true|false,
    "retention_policy": true|false,
    "gdpr_pdpa_compliance": "COMPLIANT|PARTIAL|NON_COMPLIANT|NOT_ASSESSED",
    "gaps": ["string"]
  },
  "flags": [
    {
      "level": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "area": "string",
      "message": "string",
      "recommended_action": "string",
      "framework_reference": "string"
    }
  ],
  "findings": [
    {
      "finding_id": "QA-001",
      "title": "string",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "framework_reference": "string",
      "condition": "string",
      "criteria": "string",
      "cause": "string",
      "effect": "string",
      "recommendation": "string"
    }
  ],
  "suggestions": ["string"],
  "research_used": true|false,
  "escalate_to": "AuditManager|null"
}"""


class QAAuditorAgent:
    """ITGC, EQCR, ISO 9001, process improvement, access review. CIA / CISA."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-6"
        self.max_tokens = 16000

    def audit(
        self,
        raw_data: str,
        review_period: str,
        tenant_id: str,
        jurisdiction: str = "TZ",
        review_type: str = "itgc",
        extra_context: str = "",
        enable_research: bool = True,
    ) -> dict:
        research_ctx = self._research(jurisdiction, review_type) if enable_research else ""

        user_content = f"""TENANT: {tenant_id}
JURISDICTION: {jurisdiction}
REVIEW PERIOD: {review_period}
REVIEW TYPE: {review_type}
TODAY: {datetime.utcnow().strftime('%Y-%m-%d')}

DATA / SYSTEM LOGS / DOCUMENTS FOR REVIEW:
{raw_data}

{f'ADDITIONAL CONTEXT: {extra_context}' if extra_context else ''}
{research_ctx}

Perform a QA Audit {review_type} review. Output valid JSON only."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=QA_AUDITOR_SYSTEM,
                messages=[{"role": "user", "content": user_content}],
                tools=[WEB_SEARCH_TOOL] if enable_research else [],
            )
            raw_text = "".join(b.text for b in response.content if hasattr(b, "text"))
            result = _extract_json(raw_text)
            result.setdefault("agent", "QAAuditor")
            result.setdefault("tenant_id", tenant_id)
            return result
        except Exception as e:
            logger.exception("QAAuditorAgent.audit failed")
            return {
                "agent": "QAAuditor",
                "error": str(e),
                "tenant_id": tenant_id,
                "findings": [],
                "flags": [{"level": "CRITICAL", "message": f"Agent error: {e}"}],
            }

    def _research(self, jurisdiction: str, review_type: str) -> str:
        queries = {
            "TZ": f"Tanzania ITGC COBIT audit standards {review_type} {datetime.utcnow().year}",
            "US": f"SOX COBIT CISA {review_type} IT controls {datetime.utcnow().year}",
            "BOTH": f"COBIT 2019 {review_type} IT audit controls {datetime.utcnow().year}",
        }
        query = queries.get(jurisdiction, queries["TZ"])
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": f"Search: {query}. Key QA control requirements."}],
                tools=[WEB_SEARCH_TOOL],
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            return _build_research_context([{"title": "QA Standards Research", "snippet": text}])
        except Exception:
            return ""


# ──────────────────────────────────────────────────────────────────────────────
# ForensicAuditorAgent
# ──────────────────────────────────────────────────────────────────────────────

FORENSIC_AUDITOR_SYSTEM = """You are a Forensic Auditor in an AI-powered Finance & Accounting ecosystem.

QUALIFICATIONS: CFE (Certified Fraud Examiner), CPA, fraud triangle analysis, Benford's Law, asset tracing, digital forensics awareness, financial statement fraud detection, corruption investigation methodology.

JURISDICTIONS:
- Tanzania (primary): Prevention and Combating of Corruption Act (PCCB), Anti-Money Laundering Act 2006 (AMLA), Proceeds of Crime Act, TRA tax evasion regulations, PCCB reporting requirements.
- United States: Foreign Corrupt Practices Act (FCPA), Bank Secrecy Act (BSA), wire fraud (18 USC §1343), mail fraud, False Claims Act.

FRAUD DETECTION SPECIALISATIONS:
1. Benford's Law analysis — digital frequency analysis for fabricated numbers.
2. Asset tracing — follow the money through layering and integration stages.
3. Shell company detection — UBO (Ultimate Beneficial Owner) red flags.
4. Financial statement fraud — revenue recognition manipulation (channel stuffing, premature recognition), expense fraud, off-balance-sheet schemes.
5. Procurement fraud — bid rigging, kickbacks, fictitious vendors, split purchases.
6. Payroll fraud — ghost employees, timesheet manipulation, expense reimbursement fraud.
7. Conflicts of interest — related-party transactions, undisclosed relationships.
8. Cybercrime — BEC (Business Email Compromise), invoice fraud, account takeover.

CRITICAL PRINCIPLES:
- NEVER make accusations. Frame all findings as "indicators suggest" or "evidence warrants further investigation."
- NEVER name suspects in AI output — refer to "Employee A", "Vendor X", etc.
- All findings must be supported by data evidence — no speculation.
- Preserve evidence integrity — document what was reviewed and how.
- Mandatory reporting obligations: flag SAR/STR requirements to human operator immediately.
- OUTPUT SIZE CONTROL: Cap arrays — max 8 fraud_indicators, max 6 asset_trace steps, max 8 suspicious_transactions, max 4 document_integrity items, max 6 findings, max 6 flags. Keep string fields concise (1-2 sentences). Summarise if more items exist.
- Output valid JSON ONLY — no prose, no markdown fences.

OUTPUT SCHEMA:
{
  "agent": "ForensicAuditor",
  "investigation_date": "YYYY-MM-DD",
  "investigation_period": "string",
  "jurisdiction": "TZ|US|BOTH",
  "investigation_type": "fraud_detection|asset_tracing|benfords_law|financial_statement|procurement|payroll|corruption|cyber|adhoc",
  "executive_summary": "string — factual, no accusations",
  "overall_risk_rating": "CRITICAL|HIGH|MEDIUM|LOW|CLEAR",
  "mandatory_reporting": {
    "sar_str_required": true|false,
    "authority": "PCCB|FinCEN|NBS|Other|null",
    "rationale": "string",
    "deadline": "YYYY-MM-DD or null",
    "note": "Human operator must make final STR/SAR filing decision"
  },
  "benfords_law_analysis": {
    "dataset_analysed": "string",
    "record_count": number_or_null,
    "chi_square_statistic": number_or_null,
    "p_value": number_or_null,
    "conformance": "CONFORMS|MINOR_DEVIATION|SIGNIFICANT_DEVIATION|DOES_NOT_CONFORM",
    "suspicious_digit_ranges": ["string"],
    "interpretation": "string"
  },
  "fraud_indicators": [
    {
      "indicator_id": "FI-001",
      "category": "FINANCIAL|BEHAVIOURAL|DOCUMENTARY|OPERATIONAL",
      "description": "string",
      "fraud_triangle_element": "PRESSURE|OPPORTUNITY|RATIONALISATION",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "evidence": "string",
      "amount_at_risk": number_or_null,
      "currency": "TZS|USD|OTHER",
      "recommended_investigation_step": "string"
    }
  ],
  "asset_trace": [
    {
      "step": number,
      "description": "string",
      "entity": "string (anonymised)",
      "amount": number_or_null,
      "currency": "TZS|USD|OTHER",
      "method": "LAYERING|PLACEMENT|INTEGRATION",
      "evidence": "string",
      "red_flag": "string"
    }
  ],
  "suspicious_transactions": [
    {
      "transaction_ref": "string",
      "date": "YYYY-MM-DD",
      "amount": number_or_null,
      "currency": "TZS|USD|OTHER",
      "counterparty": "string (anonymised)",
      "red_flags": ["string"],
      "further_investigation_required": true|false
    }
  ],
  "document_integrity": [
    {
      "document": "string",
      "integrity_issues": ["string"],
      "alteration_indicators": ["string"],
      "recommendation": "string"
    }
  ],
  "procurement_review": {
    "vendors_reviewed": number_or_null,
    "fictitious_vendor_indicators": number_or_null,
    "bid_rigging_indicators": number_or_null,
    "duplicate_payments": number_or_null,
    "split_purchase_orders": number_or_null,
    "total_amount_at_risk": number_or_null,
    "currency": "TZS|USD|OTHER"
  },
  "payroll_review": {
    "headcount_reviewed": number_or_null,
    "ghost_employee_indicators": number_or_null,
    "duplicate_bank_accounts": number_or_null,
    "overtime_anomalies": number_or_null,
    "expense_anomalies": number_or_null,
    "total_amount_at_risk": number_or_null
  },
  "flags": [
    {
      "level": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "area": "string",
      "message": "string",
      "recommended_action": "string",
      "legal_reference": "string"
    }
  ],
  "findings": [
    {
      "finding_id": "FF-001",
      "title": "string",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "condition": "string — factual, no accusations",
      "evidence": "string",
      "amount_at_risk": number_or_null,
      "currency": "TZS|USD|OTHER",
      "recommendation": "string",
      "requires_external_referral": true|false
    }
  ],
  "investigation_limitations": ["string"],
  "next_steps": ["string — for human operator"],
  "suggestions": ["string"],
  "research_used": true|false,
  "escalate_to": "AuditManager|HumanOperator|Legal|null",
  "legal_hold_recommended": true|false
}"""


class ForensicAuditorAgent:
    """Fraud detection, Benford's Law, asset tracing, financial crime. CFE / CPA."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-6"
        self.max_tokens = 16000

    def investigate(
        self,
        raw_data: str,
        investigation_period: str,
        tenant_id: str,
        jurisdiction: str = "TZ",
        investigation_type: str = "fraud_detection",
        extra_context: str = "",
        enable_research: bool = True,
    ) -> dict:
        research_ctx = self._research(jurisdiction, investigation_type) if enable_research else ""

        user_content = f"""TENANT: {tenant_id}
JURISDICTION: {jurisdiction}
INVESTIGATION PERIOD: {investigation_period}
INVESTIGATION TYPE: {investigation_type}
TODAY: {datetime.utcnow().strftime('%Y-%m-%d')}

IMPORTANT: Do NOT name individuals. Use anonymised references (Employee A, Vendor X) only.
Frame all findings factually — "indicators suggest" not "X committed fraud".

DATA / TRANSACTIONS / DOCUMENTS FOR FORENSIC REVIEW:
{raw_data}

{f'ADDITIONAL CONTEXT: {extra_context}' if extra_context else ''}
{research_ctx}

Perform a forensic {investigation_type} investigation. Output valid JSON only."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=FORENSIC_AUDITOR_SYSTEM,
                messages=[{"role": "user", "content": user_content}],
                tools=[WEB_SEARCH_TOOL] if enable_research else [],
            )
            raw_text = "".join(b.text for b in response.content if hasattr(b, "text"))
            result = _extract_json(raw_text)
            result.setdefault("agent", "ForensicAuditor")
            result.setdefault("tenant_id", tenant_id)
            # Safety: always ensure mandatory_reporting defaults are present
            if "mandatory_reporting" not in result:
                result["mandatory_reporting"] = {
                    "sar_str_required": False,
                    "authority": None,
                    "rationale": "No indicators identified in this review",
                    "deadline": None,
                    "note": "Human operator must make final STR/SAR filing decision",
                }
            return result
        except Exception as e:
            logger.exception("ForensicAuditorAgent.investigate failed")
            return {
                "agent": "ForensicAuditor",
                "error": str(e),
                "tenant_id": tenant_id,
                "findings": [],
                "flags": [{"level": "CRITICAL", "message": f"Agent error: {e}"}],
                "mandatory_reporting": {
                    "sar_str_required": False,
                    "note": "Agent error — human operator must assess manually",
                },
            }

    def _research(self, jurisdiction: str, investigation_type: str) -> str:
        queries = {
            "TZ": f"Tanzania PCCB AMLA fraud {investigation_type} regulations {datetime.utcnow().year}",
            "US": f"FCPA FinCEN fraud {investigation_type} BSA regulations {datetime.utcnow().year}",
            "BOTH": f"CFE ACFE fraud {investigation_type} detection standards {datetime.utcnow().year}",
        }
        query = queries.get(jurisdiction, queries["TZ"])
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": f"Search: {query}. Key fraud investigation standards."}],
                tools=[WEB_SEARCH_TOOL],
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            return _build_research_context([{"title": "Forensic Research", "snippet": text}])
        except Exception:
            return ""
