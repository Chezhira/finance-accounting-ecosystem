"""
agents/phase4_orchestrator.py
Phase 4C — Universal Analysis Orchestrator
Routes any raw input to the correct department + agent automatically.

L1 (Haiku):  classify department from raw input
L2 (Sonnet): dispatch to correct agent within department
Returns: {department, agent_type, analysis_type, result, routing_log}
"""

import json
import time
import logging
from typing import Optional
import anthropic

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Department + agent mapping constants
# ──────────────────────────────────────────────

DEPARTMENTS = {
    "accounting": {
        "description": "Journal entries, ledger classification, reconciliations, IFRS/GAAP treatment",
        "keywords": ["invoice", "journal", "ledger", "reconcile", "payable", "receivable",
                     "expense", "revenue", "asset", "liability", "equity", "depreciation",
                     "amortisation", "accrual", "prepayment", "bank statement", "trial balance"],
    },
    "fpa": {
        "description": "Financial planning, budgeting, variance analysis, forecasting, KPIs, scenario modelling",
        "keywords": ["budget", "forecast", "variance", "kpi", "planning", "scenario", "model",
                     "three statement", "p&l", "working capital", "capex", "dcf", "wacc", "lrp",
                     "board pack", "management pack", "zbb", "driver", "trend"],
    },
    "tax": {
        "description": "Tax compliance, VAT, corporate tax, withholding tax, TRA/IRS obligations",
        "keywords": ["tax", "vat", "tra", "irs", "withholding", "wht", "provisional", "corporate tax",
                     "se tax", "self-employment", "quarterly estimate", "amt", "transfer pricing",
                     "reverse charge", "tax return", "deductible"],
    },
    "audit": {
        "description": "Internal audit, compliance, forensic investigation, controls, COSO, SoD",
        "keywords": ["audit", "compliance", "fraud", "forensic", "internal control", "sod",
                     "separation of duties", "coso", "isa", "going concern", "materiality",
                     "benford", "suspicious", "aml", "kyc", "sar", "str", "itgc", "eqcr"],
    },
    "treasury": {
        "description": "Cash management, liquidity, FX, hedging, investments, capital markets",
        "keywords": ["cash", "liquidity", "fx", "foreign exchange", "hedge", "covenant", "bank",
                     "investment portfolio", "yield", "bond", "cp", "treasury", "interest rate",
                     "counterparty", "lcr", "nsfr", "cash pool", "intercompany", "derivative"],
    },
    "corpfin": {
        "description": "M&A, IPO, valuation, capital budgeting, WACC, LBO, DCF, deal structuring",
        "keywords": ["m&a", "merger", "acquisition", "ipo", "listing", "valuation", "lbo",
                     "private equity", "deal", "football field", "enterprise value", "ev",
                     "capital budgeting", "npv", "irr", "payback", "roic", "eva", "goodwill",
                     "impairment", "ppa", "fairness", "equity story", "comparable"],
    },
}

# Agent selection prompts per department
AGENT_SELECTION_MAP = {
    "fpa": {
        "agents": ["analyst", "manager", "senior", "vp", "data"],
        "descriptions": {
            "analyst": "variance, KPI, budget review, forecast adjustments, trend analysis",
            "manager": "3-statement model, scenario analysis, ZBB, CAPEX appraisal, management pack",
            "senior": "LRP, board pack, M&A analysis, capital structure review",
            "vp": "WACC, investor relations, ERM, capital structure recommendation, financing options",
            "data": "statistical analysis, Monte Carlo, anomaly detection, cohort, data quality",
        },
        "analysis_types": {
            "analyst": ["variance", "kpi", "forecast", "budget_review", "trend", "adhoc"],
            "manager": ["3statement", "scenario", "zbb", "capex", "management_pack", "adhoc"],
            "senior": ["lrp", "board_pack", "ma_analysis", "capital_structure", "review", "adhoc"],
            "vp": ["capital_structure", "wacc", "investor_relations", "erm", "consolidation", "financing", "adhoc"],
            "data": ["statistical", "monte_carlo", "anomaly", "cohort", "forecast", "data_quality", "adhoc"],
        },
    },
    "audit": {
        "agents": ["compliance", "manager", "qa", "forensic"],
        "descriptions": {
            "compliance": "COSO assessment, SoD conflicts, RCM, regulatory compliance, AML/KYC",
            "manager": "Materiality, going concern, audit programme, sampling, audit committee",
            "qa": "ITGC, EQCR, ISO 9001, process improvement, BCP/DR, access review, data governance",
            "forensic": "Fraud detection, Benford's law, asset tracing, suspicious transactions, SAR/STR",
        },
        "analysis_types": {
            "compliance": ["general_compliance", "sod_review", "regulatory", "aml_kyc", "policy_review"],
            "manager": ["internal", "external_support", "going_concern", "planning", "programme", "quality_review"],
            "qa": ["itgc", "eqcr", "iso9001", "process_improvement", "access_review", "bcp_dr", "data_governance"],
            "forensic": ["fraud_detection", "asset_tracing", "benfords_law", "financial_statement", "procurement", "payroll", "corruption", "cyber"],
        },
    },
    "treasury": {
        "agents": ["cash_flow", "liquidity", "investment", "treasury", "capital_markets", "hedge_fund"],
        "descriptions": {
            "cash_flow": "13-week forecast, working capital, covenant monitoring, stress testing, FX exposure",
            "liquidity": "LCR/NSFR, stress scenarios, cash pooling, intercompany lending, contingency funding",
            "investment": "Portfolio yield optimisation, counterparty review, IPS review, ESG screening",
            "treasury": "FX hedging strategy, interest rate risk, bank relationships, ISDA, TMS evaluation",
            "capital_markets": "Covenant review, bond issuance, syndicated loan, credit rating, LME, green bond",
            "hedge_fund": "Portfolio review, risk attribution, derivatives review, VaR/stress, fair value, performance",
        },
        "analysis_types": {
            "cash_flow": ["13week_forecast", "working_capital", "covenant_review", "stress_test", "fx_exposure", "cash_pooling", "adhoc"],
            "liquidity": ["liquidity_coverage", "stress_test", "cash_pooling", "intercompany", "cfp", "nsfr", "adhoc"],
            "investment": ["yield_optimisation", "counterparty_review", "ips_review", "portfolio_rebalance", "duration_analysis", "esg_screen", "adhoc"],
            "treasury": ["fx_hedging", "interest_rate_risk", "bank_review", "treasury_policy", "isda_review", "tms_evaluation", "adhoc"],
            "capital_markets": ["covenant_review", "bond_issuance", "syndicated_loan", "credit_rating", "lme", "green_bond", "adhoc"],
            "hedge_fund": ["portfolio_review", "risk_attribution", "derivatives_review", "due_diligence", "var_stress", "fair_value", "performance", "adhoc"],
        },
    },
    "corpfin": {
        "agents": ["investment_banker", "vp_capital_markets", "valuations", "capital_budgeting"],
        "descriptions": {
            "investment_banker": "M&A advisory, fairness opinion, deal structuring, LBO, accretion/dilution, restructuring",
            "vp_capital_markets": "IPO readiness, equity story, secondary offering, investor relations, DSE listing",
            "valuations": "DCF, comparable companies, precedent transactions, LBO, SOTP, PPA, impairment, football field",
            "capital_budgeting": "CAPEX appraisal, portfolio prioritisation, ROIC/EVA, lease vs buy, hurdle rate, stage-gate",
        },
        "analysis_types": {
            "investment_banker": ["ma_advisory", "fairness_opinion", "deal_structuring", "lbo", "accretion_dilution", "restructuring", "due_diligence", "adhoc"],
            "vp_capital_markets": ["ipo_readiness", "equity_story", "secondary_offering", "investor_relations", "spac", "reg_d_placement", "dse_listing", "adhoc"],
            "valuations": ["dcf", "comparable_companies", "precedent_transactions", "lbo", "sotp", "ppa", "impairment", "wacc", "football_field", "adhoc"],
            "capital_budgeting": ["capex_appraisal", "portfolio_prioritisation", "roic_eva", "lease_vs_buy", "hurdle_rate_review", "stage_gate", "esg_capex", "adhoc"],
        },
    },
}


# ──────────────────────────────────────────────
# L1 Department Classifier (Haiku — fast + cheap)
# ──────────────────────────────────────────────

L1_SYSTEM_PROMPT = """You are a financial analysis routing expert. Your ONLY job is to classify a given input into ONE of these departments:

- accounting: journal entries, bookkeeping, reconciliations, IFRS/GAAP treatment, payables, receivables
- fpa: budgeting, forecasting, variance analysis, KPIs, scenario modelling, board packs, LRP
- tax: VAT, corporate tax, withholding tax, TRA, IRS, self-employment tax, transfer pricing
- audit: internal audit, compliance, forensic investigation, fraud, COSO, SoD, ITGC, AML/KYC
- treasury: cash management, liquidity, FX/hedging, investments, covenants, capital markets instruments
- corpfin: M&A, IPO, valuation (DCF/comparables), capital budgeting, LBO, deal structuring

You MUST respond with ONLY a valid JSON object — no preamble, no markdown, no explanation:
{
  "department": "<one of: accounting | fpa | tax | audit | treasury | corpfin>",
  "confidence": <0.0-1.0>,
  "primary_signals": ["<keyword1>", "<keyword2>", "<keyword3>"],
  "reasoning": "<one sentence>"
}"""


def _classify_department(raw_data: str, api_key: str, routing_log: list) -> dict:
    """L1: Use Haiku to classify which department should handle this input."""
    t0 = time.time()
    client = anthropic.Anthropic(api_key=api_key)

    preview = raw_data[:3000] if len(raw_data) > 3000 else raw_data

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        system=L1_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Classify this financial input:\n\n{preview}"}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)
    elapsed = round(time.time() - t0, 2)

    routing_log.append({
        "layer": "L1_classifier",
        "model": "claude-haiku-4-5",
        "department": result.get("department"),
        "confidence": result.get("confidence"),
        "signals": result.get("primary_signals", []),
        "reasoning": result.get("reasoning", ""),
        "elapsed_s": elapsed,
    })

    logger.info(f"[Orchestrator L1] department={result.get('department')} confidence={result.get('confidence')} ({elapsed}s)")
    return result


# ──────────────────────────────────────────────
# L2 Agent Selector (Sonnet — nuanced reasoning)
# ──────────────────────────────────────────────

def _build_l2_prompt(department: str, raw_data: str) -> str:
    info = AGENT_SELECTION_MAP.get(department)
    if not info:
        return ""

    agent_lines = "\n".join(
        f"- {a}: {info['descriptions'][a]}" for a in info["agents"]
    )
    analysis_lines = "\n".join(
        f"- {a}: {', '.join(info['analysis_types'][a])}"
        for a in info["agents"]
    )

    return f"""You are a senior routing specialist within the {department.upper()} department of a Finance & Accounting AI ecosystem.

Available agents in this department:
{agent_lines}

Supported analysis_types per agent:
{analysis_lines}

Analyse the input below and respond ONLY with a valid JSON object — no preamble, no markdown fences:
{{
  "agent_type": "<one of the agents listed above>",
  "analysis_type": "<one of the analysis_types for that agent>",
  "rationale": "<2-3 sentence explanation of why this agent + analysis_type was chosen>",
  "suggested_period": "<inferred period if detectable, else 'current'>",
  "jurisdiction_hint": "<Tanzania | UnitedStates | Both | Unknown>"
}}

Input to classify:
\"\"\"
{raw_data[:4000]}
\"\"\"
"""


def _select_agent(department: str, raw_data: str, api_key: str, routing_log: list) -> dict:
    """L2: Use Sonnet to select the specific agent + analysis_type within the department."""
    t0 = time.time()
    client = anthropic.Anthropic(api_key=api_key)

    prompt = _build_l2_prompt(department, raw_data)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)
    elapsed = round(time.time() - t0, 2)

    routing_log.append({
        "layer": "L2_agent_selector",
        "model": "claude-sonnet-4-6",
        "agent_type": result.get("agent_type"),
        "analysis_type": result.get("analysis_type"),
        "rationale": result.get("rationale", ""),
        "suggested_period": result.get("suggested_period", "current"),
        "jurisdiction_hint": result.get("jurisdiction_hint", "Unknown"),
        "elapsed_s": elapsed,
    })

    logger.info(f"[Orchestrator L2] agent={result.get('agent_type')} analysis={result.get('analysis_type')} ({elapsed}s)")
    return result


# ──────────────────────────────────────────────
# Department dispatch helpers
# ──────────────────────────────────────────────

def _dispatch_fpa(agent_type: str, analysis_type: str, raw_data: str,
                  tenant_id: str, period: str, jurisdiction: str,
                  extra_context: str, enable_research: bool, api_key: str) -> dict:
    from agents.fpa_agents import FPA_AGENTS
    agent = FPA_AGENTS[agent_type](api_key)
    method_kwargs = dict(
        raw_data=raw_data,
        period=period,
        tenant_id=tenant_id,
        jurisdiction=jurisdiction,
        extra_context=extra_context,
        enable_research=enable_research,
    )
    # Add agent-specific params
    if agent_type == "analyst":
        method_kwargs["analysis_type"] = analysis_type
    elif agent_type == "manager":
        method_kwargs["model_type"] = analysis_type
    elif agent_type == "senior":
        method_kwargs["output_type"] = analysis_type
    elif agent_type == "vp":
        method_kwargs["output_type"] = analysis_type
    elif agent_type == "data":
        method_kwargs["analysis_type"] = analysis_type

    return agent.analyze(**method_kwargs)


def _dispatch_audit(agent_type: str, analysis_type: str, raw_data: str,
                    tenant_id: str, period: str, jurisdiction: str,
                    extra_context: str, enable_research: bool, api_key: str) -> dict:
    from agents.audit_agents import AUDIT_AGENTS
    agent = AUDIT_AGENTS[agent_type](api_key)
    if agent_type == "forensic":
        return agent.investigate(
            raw_data=raw_data,
            investigation_period=period,
            tenant_id=tenant_id,
            jurisdiction=jurisdiction,
            investigation_type=analysis_type,
            extra_context=extra_context,
            enable_research=enable_research,
        )
    else:
        return agent.audit(
            raw_data=raw_data,
            audit_period=period,
            tenant_id=tenant_id,
            jurisdiction=jurisdiction,
            audit_scope=analysis_type if agent_type == "compliance" else None,
            audit_type=analysis_type if agent_type in ("manager", "qa") else None,
            review_type=analysis_type if agent_type == "qa" else None,
            extra_context=extra_context,
            enable_research=enable_research,
        )


def _dispatch_treasury(agent_type: str, analysis_type: str, raw_data: str,
                       tenant_id: str, period: str, jurisdiction: str,
                       extra_context: str, enable_research: bool, api_key: str) -> dict:
    from agents.treasury_agents import TREASURY_AGENTS
    agent = TREASURY_AGENTS[agent_type](api_key)
    return agent.analyze(
        raw_data=raw_data,
        period=period,
        tenant_id=tenant_id,
        jurisdiction=jurisdiction,
        analysis_type=analysis_type,
        extra_context=extra_context,
        enable_research=enable_research,
    )


def _dispatch_corpfin(agent_type: str, analysis_type: str, raw_data: str,
                      tenant_id: str, period: str, jurisdiction: str,
                      extra_context: str, enable_research: bool, api_key: str) -> dict:
    from agents.corp_finance_agents import CORP_FINANCE_AGENTS
    agent = CORP_FINANCE_AGENTS[agent_type](api_key)
    return agent.analyze(
        raw_data=raw_data,
        period=period,
        tenant_id=tenant_id,
        jurisdiction=jurisdiction,
        analysis_type=analysis_type,
        extra_context=extra_context,
        enable_research=enable_research,
    )


# ──────────────────────────────────────────────
# Main Orchestrator
# ──────────────────────────────────────────────

class Phase4Orchestrator:
    """
    Universal entry point for Phase 4 analysis.
    Routes any raw input to the correct department + agent.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    def route(
        self,
        raw_data: str,
        tenant_id: str,
        period: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        extra_context: Optional[str] = "",
        enable_research: bool = False,
        # Optional overrides — skip L1/L2 if caller knows the target
        force_department: Optional[str] = None,
        force_agent_type: Optional[str] = None,
        force_analysis_type: Optional[str] = None,
    ) -> dict:
        """
        Route raw_data to the correct department and agent.

        Returns:
            {
                department, agent_type, analysis_type,
                jurisdiction_used, period_used,
                result,          # full agent output dict
                routing_log,     # L1 + L2 reasoning trail
                total_elapsed_s
            }
        """
        routing_log = []
        t_total = time.time()

        # ── L1: Classify department ────────────────
        if force_department:
            department = force_department
            routing_log.append({"layer": "L1_override", "department": department})
        else:
            l1 = _classify_department(raw_data, self.api_key, routing_log)
            department = l1.get("department", "accounting")

        # ── L2: Select agent within department ──────
        if force_agent_type and force_analysis_type:
            agent_type = force_agent_type
            analysis_type = force_analysis_type
            inferred_period = period or "current"
            inferred_jurisdiction = jurisdiction or "Unknown"
            routing_log.append({
                "layer": "L2_override",
                "agent_type": agent_type,
                "analysis_type": analysis_type,
            })
        else:
            l2 = _select_agent(department, raw_data, self.api_key, routing_log)
            agent_type = force_agent_type or l2.get("agent_type")
            analysis_type = force_analysis_type or l2.get("analysis_type")
            inferred_period = period or l2.get("suggested_period", "current")
            inferred_jurisdiction = jurisdiction or l2.get("jurisdiction_hint", "Tanzania")

        # Normalise jurisdiction
        if inferred_jurisdiction in ("Unknown", "Both", None):
            inferred_jurisdiction = "Tanzania"

        # ── Dispatch to department ───────────────────
        try:
            if department == "accounting":
                # Accounting uses the existing escalation chain via ingest — not a Phase4 agent
                result = {
                    "note": "Accounting department uses the journal entry escalation chain.",
                    "action": "Submit via POST /ingest/text or /ingest/upload for Junior Accountant processing.",
                    "department": "accounting",
                }
            elif department == "fpa":
                result = _dispatch_fpa(
                    agent_type, analysis_type, raw_data,
                    tenant_id, inferred_period, inferred_jurisdiction,
                    extra_context, enable_research, self.api_key,
                )
            elif department == "audit":
                result = _dispatch_audit(
                    agent_type, analysis_type, raw_data,
                    tenant_id, inferred_period, inferred_jurisdiction,
                    extra_context, enable_research, self.api_key,
                )
            elif department == "treasury":
                result = _dispatch_treasury(
                    agent_type, analysis_type, raw_data,
                    tenant_id, inferred_period, inferred_jurisdiction,
                    extra_context, enable_research, self.api_key,
                )
            elif department == "corpfin":
                result = _dispatch_corpfin(
                    agent_type, analysis_type, raw_data,
                    tenant_id, inferred_period, inferred_jurisdiction,
                    extra_context, enable_research, self.api_key,
                )
            elif department == "tax":
                # Tax uses its own orchestrator
                result = {
                    "note": "Tax department has its own orchestrator.",
                    "action": "Submit via POST /tax/analyze for automatic TZ/US routing.",
                    "department": "tax",
                }
            else:
                result = {"error": f"Unknown department: {department}"}

        except Exception as e:
            logger.error(f"[Orchestrator] Dispatch failed: {e}", exc_info=True)
            result = {"error": str(e), "department": department, "agent_type": agent_type}

        total_elapsed = round(time.time() - t_total, 2)

        return {
            "department": department,
            "agent_type": agent_type,
            "analysis_type": analysis_type,
            "jurisdiction_used": inferred_jurisdiction,
            "period_used": inferred_period,
            "result": result,
            "routing_log": routing_log,
            "total_elapsed_s": total_elapsed,
        }
