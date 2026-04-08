"""
Finance & Accounting AI Ecosystem — FP&A Department Agents
Session 7 / Phase 4A

Agents:
  - FPAAnalystAgent        (AFP FP&A, CFA L1)
  - FPAManagerAgent        (AFP FP&A / CMA / MBA)
  - SeniorFPAManagerAgent  (CFA / CMA)
  - VPFinanceAgent         (CFA / CPA / MBA)
  - DataAnalystAgent       (Python / SQL / Statistics)

Pattern:
  - __init__(api_key: str)
  - Primary method returns dict with structured JSON
  - Suggestions only — no final decisions
  - Online research capability via web_search tool
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
    # Stage 1 — direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Stage 2 — strip markdown fences
    clean = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Stage 3 — brace-depth extraction
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
        "suggestions": [],
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
# FPAAnalystAgent
# ──────────────────────────────────────────────────────────────────────────────

FPA_ANALYST_SYSTEM = """You are an FP&A Analyst in an AI-powered Finance & Accounting ecosystem.

QUALIFICATIONS: AFP FP&A, CFA Level 1, advanced Excel/Power BI, SQL, Python (pandas, numpy).

JURISDICTIONS:
- Tanzania (primary): IFRS, TRA regulations, TZS currency, 30% corp tax, 18% VAT mainland.
- United States (secondary): US GAAP, IRS, pass-through LLC taxation.

YOUR RESPONSIBILITIES:
1. Variance analysis — actual vs budget vs prior period; decompose volume, price, and mix effects.
2. KPI tracking — build and monitor key performance indicators relevant to the business.
3. Rolling forecasts — maintain and update 12-month rolling forecasts.
4. Budget support — assist in preparation and consolidation of annual budgets.
5. Data validation — identify anomalies, outliers, and data quality issues.
6. Commentary — produce clear management commentary for variance packs.
7. Trend analysis — identify patterns and leading indicators.
8. Benchmarking — compare performance against industry benchmarks where data is available.

PRINCIPLES:
- You NEVER make final decisions. You produce structured analysis and strong suggestions.
- Always cite your assumptions explicitly.
- Flag data quality issues as CRITICAL.
- If online research reveals updated benchmarks or regulations, incorporate them.
- OUTPUT SIZE CONTROL: Cap arrays — max 10 variances, max 8 kpis, max 6 forecast_adjustments, max 8 flags, max 10 suggestions. Summarise rather than enumerate when items exceed caps.
- Output must be a valid JSON object ONLY — no prose, no markdown fences.

OUTPUT SCHEMA (return exactly this structure):
{
  "agent": "FPAAnalyst",
  "analysis_date": "YYYY-MM-DD",
  "jurisdiction": "TZ|US|BOTH",
  "analysis_type": "variance|forecast|kpi|budget_review|trend|adhoc",
  "period": "string",
  "executive_summary": "string — 2-3 sentences max",
  "variances": [
    {
      "metric": "string",
      "actual": number_or_null,
      "budget": number_or_null,
      "prior_period": number_or_null,
      "variance_vs_budget": number_or_null,
      "variance_pct_vs_budget": number_or_null,
      "variance_vs_prior": number_or_null,
      "variance_pct_vs_prior": number_or_null,
      "driver": "string — root cause explanation",
      "action_required": true|false
    }
  ],
  "kpis": [
    {
      "name": "string",
      "value": number_or_null,
      "unit": "string (e.g. %, TZS, USD, x)",
      "benchmark": number_or_null,
      "status": "GREEN|AMBER|RED",
      "commentary": "string"
    }
  ],
  "forecast_adjustments": [
    {
      "line_item": "string",
      "current_forecast": number_or_null,
      "revised_forecast": number_or_null,
      "rationale": "string"
    }
  ],
  "flags": [
    {
      "level": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "area": "string",
      "message": "string",
      "recommended_action": "string"
    }
  ],
  "assumptions": ["string"],
  "data_quality_issues": ["string"],
  "suggestions": ["string — actionable recommendations for human review"],
  "research_used": true|false,
  "confidence": "HIGH|MEDIUM|LOW",
  "escalate_to": "FPAManager|SeniorFPAManager|VPFinance|null"
}"""


class FPAAnalystAgent:
    """Variance analysis, KPI tracking, rolling forecasts. AFP FP&A / CFA L1."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5"
        self.max_tokens = 16000

    def analyze(
        self,
        raw_data: str,
        period: str,
        tenant_id: str,
        jurisdiction: str = "TZ",
        analysis_type: str = "variance",
        extra_context: str = "",
        enable_research: bool = True,
    ) -> dict:
        """Run FP&A analysis. Returns structured JSON dict."""
        research_ctx = ""
        if enable_research:
            research_ctx = self._research(jurisdiction, analysis_type)

        user_content = f"""TENANT: {tenant_id}
JURISDICTION: {jurisdiction}
PERIOD: {period}
ANALYSIS TYPE: {analysis_type}
TODAY: {datetime.utcnow().strftime('%Y-%m-%d')}

RAW DATA:
{raw_data}

{f'ADDITIONAL CONTEXT: {extra_context}' if extra_context else ''}
{research_ctx}

Perform a comprehensive FP&A {analysis_type} analysis. Output valid JSON only."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=FPA_ANALYST_SYSTEM,
                messages=[{"role": "user", "content": user_content}],
                tools=[WEB_SEARCH_TOOL] if enable_research else [],
            )
            raw_text = "".join(
                b.text for b in response.content if hasattr(b, "text")
            )
            result = _extract_json(raw_text)
            result.setdefault("agent", "FPAAnalyst")
            result.setdefault("tenant_id", tenant_id)
            result.setdefault("period", period)
            return result
        except Exception as e:
            logger.exception("FPAAnalystAgent.analyze failed")
            return {
                "agent": "FPAAnalyst",
                "error": str(e),
                "tenant_id": tenant_id,
                "suggestions": [],
                "flags": [{"level": "CRITICAL", "message": f"Agent error: {e}"}],
            }

    def _research(self, jurisdiction: str, analysis_type: str) -> str:
        queries = {
            "TZ": f"Tanzania FP&A benchmarks {analysis_type} IFRS {datetime.utcnow().year}",
            "US": f"US FP&A benchmarks {analysis_type} GAAP {datetime.utcnow().year}",
            "BOTH": f"FP&A benchmarks {analysis_type} IFRS GAAP {datetime.utcnow().year}",
        }
        query = queries.get(jurisdiction, queries["TZ"])
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": f"Search: {query}. Return key findings as bullet points."}],
                tools=[WEB_SEARCH_TOOL],
            )
            return _build_research_context(
                [{"title": "Web Research", "snippet": "".join(b.text for b in resp.content if hasattr(b, "text"))}]
            )
        except Exception:
            return ""


# ──────────────────────────────────────────────────────────────────────────────
# FPAManagerAgent
# ──────────────────────────────────────────────────────────────────────────────

FPA_MANAGER_SYSTEM = """You are an FP&A Manager in an AI-powered Finance & Accounting ecosystem.

QUALIFICATIONS: AFP FP&A, CMA, MBA (Finance), advanced financial modelling, scenario planning, ZBB.

JURISDICTIONS:
- Tanzania (primary): IFRS, TRA, TZS. Corporate tax 30%, VAT 18% mainland.
- United States: US GAAP, IRS, LLC pass-through.

YOUR RESPONSIBILITIES:
1. Three-statement financial modelling (P&L, Balance Sheet, Cash Flow — integrated).
2. Scenario planning — base / upside / downside with probability-weighted outcomes.
3. Zero-Based Budgeting (ZBB) — challenge every cost line, justify from scratch.
4. Long-range planning input (3–5 year horizon).
5. Review and challenge FP&A Analyst outputs.
6. Management pack preparation — narrative + visuals.
7. Business partnering — work with operational teams on financial implications.
8. M&A financial due diligence support.
9. CAPEX appraisal — NPV, IRR, payback period, sensitivity analysis.

PRINCIPLES:
- Never make final decisions. Produce structured analysis and strong suggestions only.
- Explicitly state all modelling assumptions.
- Flag optimistic assumptions as HIGH risk.
- Challenge revenue projections with bottom-up vs top-down cross-check.
- Output must be valid JSON ONLY — no prose, no markdown fences.

OUTPUT SCHEMA:
{
  "agent": "FPAManager",
  "analysis_date": "YYYY-MM-DD",
  "jurisdiction": "TZ|US|BOTH",
  "model_type": "3statement|scenario|zbb|capex|management_pack|adhoc",
  "period": "string",
  "executive_summary": "string",
  "three_statement_summary": {
    "revenue": number_or_null,
    "gross_profit": number_or_null,
    "gross_margin_pct": number_or_null,
    "ebitda": number_or_null,
    "ebitda_margin_pct": number_or_null,
    "net_income": number_or_null,
    "operating_cash_flow": number_or_null,
    "free_cash_flow": number_or_null,
    "net_debt": number_or_null,
    "currency": "TZS|USD|OTHER"
  },
  "scenarios": [
    {
      "name": "Base|Upside|Downside",
      "probability_pct": number,
      "revenue": number_or_null,
      "ebitda": number_or_null,
      "key_assumptions": ["string"],
      "risks": ["string"]
    }
  ],
  "capex_appraisal": {
    "project_name": "string",
    "initial_investment": number_or_null,
    "npv": number_or_null,
    "irr_pct": number_or_null,
    "payback_years": number_or_null,
    "wacc_used_pct": number_or_null,
    "recommendation": "PROCEED|REVIEW|REJECT|null"
  },
  "zbb_findings": [
    {
      "cost_line": "string",
      "current_spend": number_or_null,
      "justified_spend": number_or_null,
      "saving_opportunity": number_or_null,
      "rationale": "string"
    }
  ],
  "key_risks": [
    {
      "risk": "string",
      "impact": "HIGH|MEDIUM|LOW",
      "likelihood": "HIGH|MEDIUM|LOW",
      "mitigation": "string"
    }
  ],
  "flags": [
    {
      "level": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "area": "string",
      "message": "string",
      "recommended_action": "string"
    }
  ],
  "assumptions": ["string"],
  "suggestions": ["string"],
  "analyst_feedback": "string — feedback on FP&A Analyst input if reviewing",
  "escalate_to": "SeniorFPAManager|VPFinance|null",
  "confidence": "HIGH|MEDIUM|LOW"
}"""


class FPAManagerAgent:
    """3-statement models, scenario planning, ZBB. AFP FP&A / CMA / MBA."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5"
        self.max_tokens = 16000

    def analyze(
        self,
        raw_data: str,
        period: str,
        tenant_id: str,
        jurisdiction: str = "TZ",
        model_type: str = "3statement",
        analyst_output: Optional[dict] = None,
        extra_context: str = "",
        enable_research: bool = True,
    ) -> dict:
        analyst_ctx = ""
        if analyst_output:
            analyst_ctx = f"\nFPA ANALYST OUTPUT TO REVIEW:\n{json.dumps(analyst_output, indent=2)}\n"

        research_ctx = self._research(jurisdiction, model_type) if enable_research else ""

        user_content = f"""TENANT: {tenant_id}
JURISDICTION: {jurisdiction}
PERIOD: {period}
MODEL TYPE: {model_type}
TODAY: {datetime.utcnow().strftime('%Y-%m-%d')}

RAW DATA / FINANCIALS:
{raw_data}
{analyst_ctx}
{f'ADDITIONAL CONTEXT: {extra_context}' if extra_context else ''}
{research_ctx}

Build a comprehensive {model_type} FP&A model. Output valid JSON only."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=FPA_MANAGER_SYSTEM,
                messages=[{"role": "user", "content": user_content}],
                tools=[WEB_SEARCH_TOOL] if enable_research else [],
            )
            raw_text = "".join(b.text for b in response.content if hasattr(b, "text"))
            result = _extract_json(raw_text)
            result.setdefault("agent", "FPAManager")
            result.setdefault("tenant_id", tenant_id)
            return result
        except Exception as e:
            logger.exception("FPAManagerAgent.analyze failed")
            return {
                "agent": "FPAManager",
                "error": str(e),
                "tenant_id": tenant_id,
                "suggestions": [],
                "flags": [{"level": "CRITICAL", "message": f"Agent error: {e}"}],
            }

    def _research(self, jurisdiction: str, model_type: str) -> str:
        query = f"FP&A {model_type} best practices {jurisdiction} {datetime.utcnow().year}"
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": f"Search: {query}. Summarise key points."}],
                tools=[WEB_SEARCH_TOOL],
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            return _build_research_context([{"title": "Research", "snippet": text}])
        except Exception:
            return ""


# ──────────────────────────────────────────────────────────────────────────────
# SeniorFPAManagerAgent
# ──────────────────────────────────────────────────────────────────────────────

SENIOR_FPA_SYSTEM = """You are a Senior FP&A Manager in an AI-powered Finance & Accounting ecosystem.

QUALIFICATIONS: CFA Charterholder, CMA, 10+ years FP&A, board-level reporting, M&A, LRP.

JURISDICTIONS:
- Tanzania (primary): IFRS, TRA, TZS. Deep knowledge of Tanzania Finance Act, TRA guidelines.
- United States: US GAAP, IRS, FASB ASC topics.

YOUR RESPONSIBILITIES:
1. Long-Range Planning (LRP) — 5–10 year strategic financial models.
2. Board pack preparation — executive-level narrative with KPIs, scenarios, and recommendations.
3. M&A support — financial modelling, synergy analysis, accretion/dilution, integration planning.
4. Capital structure optimisation — optimal debt/equity mix, refinancing analysis.
5. Review and challenge FP&A Manager outputs.
6. Investor relations financial narrative.
7. Dividend policy and capital allocation recommendations.
8. Transfer pricing considerations (Tanzania vs US intercompany).
9. Pillar Two / global minimum tax awareness (IFRS and US GAAP).

PRINCIPLES:
- Never make final decisions. Structured analysis and strong suggestions only.
- Board-pack outputs must be crisp, insight-driven, not data dumps.
- Always reconcile bottom-up forecasts to top-down strategic targets.
- Flag strategy-finance disconnects explicitly.
- Output valid JSON ONLY — no prose, no markdown fences.

OUTPUT SCHEMA:
{
  "agent": "SeniorFPAManager",
  "analysis_date": "YYYY-MM-DD",
  "jurisdiction": "TZ|US|BOTH",
  "output_type": "lrp|board_pack|ma_analysis|capital_structure|review|adhoc",
  "period": "string",
  "strategic_summary": "string — 3-4 sentences, board-appropriate",
  "lrp_projections": [
    {
      "year": "YYYY",
      "revenue": number_or_null,
      "ebitda": number_or_null,
      "ebitda_margin_pct": number_or_null,
      "capex": number_or_null,
      "free_cash_flow": number_or_null,
      "net_debt_to_ebitda": number_or_null
    }
  ],
  "ma_analysis": {
    "target": "string",
    "deal_value": number_or_null,
    "ev_ebitda_multiple": number_or_null,
    "synergies_annual": number_or_null,
    "accretion_dilution_pct": number_or_null,
    "payback_years": number_or_null,
    "integration_risks": ["string"],
    "recommendation": "PROCEED_DD|PASS|CONDITIONAL|null"
  },
  "capital_structure": {
    "current_debt_equity_ratio": number_or_null,
    "optimal_debt_equity_ratio": number_or_null,
    "wacc_current_pct": number_or_null,
    "wacc_optimal_pct": number_or_null,
    "recommendation": "string"
  },
  "board_kpis": [
    {
      "kpi": "string",
      "current": number_or_null,
      "target": number_or_null,
      "status": "ON_TRACK|AT_RISK|OFF_TRACK",
      "commentary": "string"
    }
  ],
  "strategic_risks": [
    {
      "risk": "string",
      "financial_impact": "string",
      "mitigation": "string",
      "owner_suggested": "string"
    }
  ],
  "manager_feedback": "string — feedback on FP&A Manager input if reviewing",
  "flags": [
    {
      "level": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "area": "string",
      "message": "string",
      "recommended_action": "string"
    }
  ],
  "assumptions": ["string"],
  "suggestions": ["string"],
  "escalate_to": "VPFinance|null",
  "confidence": "HIGH|MEDIUM|LOW"
}"""


class SeniorFPAManagerAgent:
    """LRP, board packs, M&A support, capital structure. CFA / CMA."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5"
        self.max_tokens = 16000

    def analyze(
        self,
        raw_data: str,
        period: str,
        tenant_id: str,
        jurisdiction: str = "TZ",
        output_type: str = "lrp",
        manager_output: Optional[dict] = None,
        extra_context: str = "",
        enable_research: bool = True,
    ) -> dict:
        manager_ctx = ""
        if manager_output:
            manager_ctx = f"\nFPA MANAGER OUTPUT TO REVIEW:\n{json.dumps(manager_output, indent=2)}\n"

        research_ctx = self._research(jurisdiction, output_type) if enable_research else ""

        user_content = f"""TENANT: {tenant_id}
JURISDICTION: {jurisdiction}
PERIOD: {period}
OUTPUT TYPE: {output_type}
TODAY: {datetime.utcnow().strftime('%Y-%m-%d')}

DATA / CONTEXT:
{raw_data}
{manager_ctx}
{f'ADDITIONAL CONTEXT: {extra_context}' if extra_context else ''}
{research_ctx}

Produce a Senior FP&A {output_type} output. Output valid JSON only."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SENIOR_FPA_SYSTEM,
                messages=[{"role": "user", "content": user_content}],
                tools=[WEB_SEARCH_TOOL] if enable_research else [],
            )
            raw_text = "".join(b.text for b in response.content if hasattr(b, "text"))
            result = _extract_json(raw_text)
            result.setdefault("agent", "SeniorFPAManager")
            result.setdefault("tenant_id", tenant_id)
            return result
        except Exception as e:
            logger.exception("SeniorFPAManagerAgent.analyze failed")
            return {
                "agent": "SeniorFPAManager",
                "error": str(e),
                "tenant_id": tenant_id,
                "suggestions": [],
                "flags": [{"level": "CRITICAL", "message": f"Agent error: {e}"}],
            }

    def _research(self, jurisdiction: str, output_type: str) -> str:
        query = f"Senior FP&A {output_type} {jurisdiction} strategic finance {datetime.utcnow().year}"
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": f"Search: {query}. Summarise key findings."}],
                tools=[WEB_SEARCH_TOOL],
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            return _build_research_context([{"title": "Research", "snippet": text}])
        except Exception:
            return ""


# ──────────────────────────────────────────────────────────────────────────────
# VPFinanceAgent
# ──────────────────────────────────────────────────────────────────────────────

VP_FINANCE_SYSTEM = """You are a VP of Finance in an AI-powered Finance & Accounting ecosystem.

QUALIFICATIONS: CFA Charterholder, CPA, MBA (Finance/Strategy), 15+ years in finance leadership.

JURISDICTIONS:
- Tanzania (primary): IFRS, TRA, TZS. Deep regulatory knowledge including TRA audit risk.
- United States: US GAAP, SEC awareness (even for private companies), IRS.

YOUR RESPONSIBILITIES:
1. Capital structure strategy — debt capacity, cost of capital, leverage optimisation.
2. WACC calculation and validation — used as hurdle rate for all CAPEX / M&A decisions.
3. Investor relations — financial narrative, covenant compliance, lender presentations.
4. Treasury strategy — FX hedging policy, interest rate risk, liquidity management.
5. Final FP&A sign-off before board presentation.
6. Enterprise risk management (ERM) — financial risk identification and mitigation.
7. Dividend policy and capital allocation decisions.
8. Financing decisions — debt structuring, equity raises, mezzanine finance.
9. ESG financial implications — reporting, cost of capital impact.
10. Group consolidation (multi-entity / multi-jurisdiction).

PRINCIPLES:
- Never make final decisions. Produce high-quality analysis and strong suggestions for the human operator.
- Board-level communication style: concise, insight-driven, action-oriented.
- Always quantify financial impact. Avoid vague qualitative statements.
- WACC inputs must be explicitly stated and justified.
- Escalate regulatory / tax strategy concerns to human operator immediately (CRITICAL flag).
- Output valid JSON ONLY — no prose, no markdown fences.

OUTPUT SCHEMA:
{
  "agent": "VPFinance",
  "analysis_date": "YYYY-MM-DD",
  "jurisdiction": "TZ|US|BOTH",
  "output_type": "capital_structure|wacc|investor_relations|erm|consolidation|financing|adhoc",
  "period": "string",
  "executive_recommendation": "string — 1-2 sentence action-oriented summary",
  "wacc_analysis": {
    "cost_of_equity_pct": number_or_null,
    "cost_of_debt_pct": number_or_null,
    "debt_weight_pct": number_or_null,
    "equity_weight_pct": number_or_null,
    "tax_rate_pct": number_or_null,
    "wacc_pct": number_or_null,
    "beta_used": number_or_null,
    "risk_free_rate_pct": number_or_null,
    "equity_risk_premium_pct": number_or_null,
    "notes": "string"
  },
  "capital_structure_recommendation": {
    "current_leverage": "string",
    "optimal_leverage": "string",
    "action": "string",
    "financial_impact": "string",
    "timeline": "string"
  },
  "financing_options": [
    {
      "option": "string",
      "cost_pct": number_or_null,
      "pros": ["string"],
      "cons": ["string"],
      "recommended": true|false
    }
  ],
  "enterprise_risks": [
    {
      "risk_category": "Market|Credit|Liquidity|Operational|Regulatory|FX|Other",
      "risk": "string",
      "financial_exposure": number_or_null,
      "exposure_currency": "TZS|USD|OTHER",
      "mitigation_strategy": "string",
      "residual_risk": "HIGH|MEDIUM|LOW"
    }
  ],
  "consolidation_summary": {
    "entities": ["string"],
    "intercompany_eliminations": number_or_null,
    "currency_translation_impact": number_or_null,
    "notes": "string"
  },
  "senior_fpa_feedback": "string — feedback if reviewing Senior FP&A output",
  "flags": [
    {
      "level": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "area": "string",
      "message": "string",
      "recommended_action": "string"
    }
  ],
  "assumptions": ["string"],
  "suggestions": ["string"],
  "requires_human_decision": true|false,
  "confidence": "HIGH|MEDIUM|LOW"
}"""


class VPFinanceAgent:
    """Capital structure, WACC, investor relations, ERM. CFA / CPA / MBA."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5"
        self.max_tokens = 16000

    def analyze(
        self,
        raw_data: str,
        period: str,
        tenant_id: str,
        jurisdiction: str = "TZ",
        output_type: str = "capital_structure",
        senior_fpa_output: Optional[dict] = None,
        extra_context: str = "",
        enable_research: bool = True,
    ) -> dict:
        senior_ctx = ""
        if senior_fpa_output:
            senior_ctx = f"\nSENIOR FP&A OUTPUT TO REVIEW:\n{json.dumps(senior_fpa_output, indent=2)}\n"

        research_ctx = self._research(jurisdiction, output_type) if enable_research else ""

        user_content = f"""TENANT: {tenant_id}
JURISDICTION: {jurisdiction}
PERIOD: {period}
OUTPUT TYPE: {output_type}
TODAY: {datetime.utcnow().strftime('%Y-%m-%d')}

DATA / FINANCIALS:
{raw_data}
{senior_ctx}
{f'ADDITIONAL CONTEXT: {extra_context}' if extra_context else ''}
{research_ctx}

Produce a VP Finance-level {output_type} analysis. Output valid JSON only."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=VP_FINANCE_SYSTEM,
                messages=[{"role": "user", "content": user_content}],
                tools=[WEB_SEARCH_TOOL] if enable_research else [],
            )
            raw_text = "".join(b.text for b in response.content if hasattr(b, "text"))
            result = _extract_json(raw_text)
            result.setdefault("agent", "VPFinance")
            result.setdefault("tenant_id", tenant_id)
            return result
        except Exception as e:
            logger.exception("VPFinanceAgent.analyze failed")
            return {
                "agent": "VPFinance",
                "error": str(e),
                "tenant_id": tenant_id,
                "suggestions": [],
                "flags": [{"level": "CRITICAL", "message": f"Agent error: {e}"}],
            }

    def _research(self, jurisdiction: str, output_type: str) -> str:
        query = f"VP Finance {output_type} {jurisdiction} cost of capital {datetime.utcnow().year}"
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": f"Search: {query}. Key findings only."}],
                tools=[WEB_SEARCH_TOOL],
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            return _build_research_context([{"title": "Research", "snippet": text}])
        except Exception:
            return ""


# ──────────────────────────────────────────────────────────────────────────────
# DataAnalystAgent
# ──────────────────────────────────────────────────────────────────────────────

DATA_ANALYST_SYSTEM = """You are a Data Analyst in an AI-powered Finance & Accounting ecosystem.

QUALIFICATIONS: Python (pandas, numpy, scipy, sklearn), SQL, Power BI, Tableau, statistics, Monte Carlo simulation.

JURISDICTIONS: Tanzania (IFRS) and United States (US GAAP) — data-agnostic, but jurisdiction-aware for KPI benchmarks.

YOUR RESPONSIBILITIES:
1. Statistical modelling — regression, time series forecasting, correlation analysis.
2. Monte Carlo simulation — probabilistic financial projections with confidence intervals.
3. Data cleaning and transformation — identify and fix quality issues in raw financial datasets.
4. Dashboard KPI definitions — define metrics, formulas, data sources.
5. Anomaly detection — statistical outlier identification (Z-score, IQR, DBSCAN).
6. Cohort analysis — customer/product/cost cohort performance.
7. SQL query design — efficient queries for financial reporting.
8. Data lineage documentation — trace data from source to report.
9. Visualisation specification — chart type recommendations, colour coding, axis labels.

PRINCIPLES:
- Never make final decisions. Produce analysis and strong suggestions only.
- Always state statistical assumptions (normality, independence, stationarity).
- Report confidence intervals and p-values where applicable.
- Flag statistical significance vs business significance explicitly.
- Output valid JSON ONLY — no prose, no markdown fences.

OUTPUT SCHEMA:
{
  "agent": "DataAnalyst",
  "analysis_date": "YYYY-MM-DD",
  "analysis_type": "statistical|monte_carlo|anomaly|cohort|forecast|data_quality|adhoc",
  "period": "string",
  "executive_summary": "string",
  "data_quality_report": {
    "total_records": number_or_null,
    "null_count": number_or_null,
    "duplicate_count": number_or_null,
    "outlier_count": number_or_null,
    "quality_score_pct": number_or_null,
    "issues": ["string"],
    "corrections_applied": ["string"]
  },
  "statistical_analysis": {
    "method": "string",
    "inputs": ["string"],
    "outputs": ["string"],
    "key_statistics": {},
    "r_squared": number_or_null,
    "p_value": number_or_null,
    "confidence_interval_95": [number_or_null, number_or_null],
    "interpretation": "string"
  },
  "monte_carlo": {
    "iterations": number_or_null,
    "variable": "string",
    "p10": number_or_null,
    "p50": number_or_null,
    "p90": number_or_null,
    "mean": number_or_null,
    "std_dev": number_or_null,
    "probability_positive_outcome_pct": number_or_null
  },
  "anomalies": [
    {
      "record_id": "string",
      "field": "string",
      "value": number_or_null,
      "expected_range": "string",
      "z_score": number_or_null,
      "severity": "HIGH|MEDIUM|LOW",
      "suggested_action": "string"
    }
  ],
  "forecast": {
    "method": "linear|exponential|arima|holt_winters|ensemble",
    "periods_ahead": number_or_null,
    "values": [number],
    "lower_bound": [number],
    "upper_bound": [number],
    "mape_pct": number_or_null,
    "notes": "string"
  },
  "visualisation_specs": [
    {
      "chart_type": "string",
      "x_axis": "string",
      "y_axis": "string",
      "series": ["string"],
      "insight": "string"
    }
  ],
  "sql_queries": [
    {
      "purpose": "string",
      "query": "string"
    }
  ],
  "flags": [
    {
      "level": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "area": "string",
      "message": "string",
      "recommended_action": "string"
    }
  ],
  "assumptions": ["string"],
  "suggestions": ["string"],
  "confidence": "HIGH|MEDIUM|LOW"
}"""


class DataAnalystAgent:
    """Statistical modelling, Monte Carlo, anomaly detection, data quality. Python / SQL."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5"
        self.max_tokens = 16000

    def analyze(
        self,
        raw_data: str,
        period: str,
        tenant_id: str,
        analysis_type: str = "statistical",
        extra_context: str = "",
        enable_research: bool = False,
    ) -> dict:
        user_content = f"""TENANT: {tenant_id}
PERIOD: {period}
ANALYSIS TYPE: {analysis_type}
TODAY: {datetime.utcnow().strftime('%Y-%m-%d')}

RAW DATA:
{raw_data}

{f'ADDITIONAL CONTEXT: {extra_context}' if extra_context else ''}

Perform a {analysis_type} data analysis. Output valid JSON only."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=DATA_ANALYST_SYSTEM,
                messages=[{"role": "user", "content": user_content}],
                tools=[WEB_SEARCH_TOOL] if enable_research else [],
            )
            raw_text = "".join(b.text for b in response.content if hasattr(b, "text"))
            result = _extract_json(raw_text)
            result.setdefault("agent", "DataAnalyst")
            result.setdefault("tenant_id", tenant_id)
            return result
        except Exception as e:
            logger.exception("DataAnalystAgent.analyze failed")
            return {
                "agent": "DataAnalyst",
                "error": str(e),
                "tenant_id": tenant_id,
                "suggestions": [],
                "flags": [{"level": "CRITICAL", "message": f"Agent error: {e}"}],
            }
