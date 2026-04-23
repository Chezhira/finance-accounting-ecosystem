"""
FinOps Ecosystem API — v5.1.0
Session 10: + CostAccountant, RevenueAccountant, AccountingManager agents
           + LiveMarketDataAdapter (/market/rates, ?include_market_data= flag)
All previous routes preserved exactly.
"""

import os
import json
import uuid
import logging
import threading
import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Depends
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Absolute paths — safe regardless of working directory at launch
_HERE = Path(__file__).parent          # api/
_ROOT = _HERE.parent                   # finops/
REPORTS_DIR = _ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Imports — all agents and adapters
# ---------------------------------------------------------------------------
from db.store import OfflineStore
from ingestion.ingestor import DataIngestor
from adapters.accounting_adapter import get_adapter, suggestion_to_journal_entry

# Phase 1
from agents.junior_accountant import JuniorAccountantAgent

# Phase 2
from agents.senior_accountant import SeniorAccountantAgent
from agents.financial_controller import FinancialControllerAgent
from api.escalation import (
    EscalationEngine, EscalationStore, EscalationEmailer,
    EscalationState
)

# Phase 3
from agents.tax_agent_tz import TaxAgentTZ, TZ_TAX_RULES
from agents.tax_agent_us import TaxAgentUS, US_TAX_RULES
from agents.tax_orchestrator import TaxOrchestrator

# Session 12 — Tax Supervisor + Tax Accountant + Tax Strategy Manager
from agents.tax_supervisor import TaxSupervisorAgent
from agents.tax_accountant import TaxAccountantAgent, TAX_ACCOUNTANT_DEFINITIONS
from agents.tax_strategy_manager import TaxStrategyManagerAgent, TAX_STRATEGY_DEFINITIONS

# Phase 4A
from agents.fpa_agents import (
    FPAAnalystAgent, FPAManagerAgent, SeniorFPAManagerAgent,
    VPFinanceAgent, DataAnalystAgent
)
from agents.audit_agents import (
    ComplianceAuditorAgent, AuditManagerAgent, QAAuditorAgent, ForensicAuditorAgent
)

# Phase 4B
from agents.treasury_agents import TREASURY_AGENTS, TREASURY_AGENT_DEFINITIONS
from agents.corp_finance_agents import CORP_FINANCE_AGENTS, CORP_FINANCE_AGENT_DEFINITIONS

# Phase 4C
from agents.phase4_orchestrator import Phase4Orchestrator

# Session 10 — new agents
from agents.cost_accountant import CostAccountantAgent, COST_AGENT_DEFINITIONS
from agents.revenue_accountant import RevenueAccountantAgent, REVENUE_AGENT_DEFINITIONS
from agents.accounting_manager import AccountingManagerAgent, ACCOUNTING_MANAGER_DEFINITIONS

# Session 10 — market data adapter
from adapters.market_data_adapter import get_market_data_adapter

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
RBAC_ENABLED = os.getenv("RBAC_ENABLED", "false").lower() == "true"
MARKET_DATA_LIVE = os.getenv("MARKET_DATA_LIVE", "true").lower() == "true"
TAX_SUPERVISOR_ENABLED = os.getenv("TAX_SUPERVISOR_ENABLED", "true").lower() == "true"

store = OfflineStore()
esc_store = EscalationStore()          # shared singleton — avoids per-request DB init
ingestor = DataIngestor()
market_adapter = get_market_data_adapter(live=MARKET_DATA_LIVE)

app = FastAPI(title="FinOps Ecosystem", version="5.4.0")

# ---------------------------------------------------------------------------
# FP&A agent registry (defined here — not exported from fpa_agents.py)
# ---------------------------------------------------------------------------
FPA_AGENTS = {
    "fpa_analyst": lambda: FPAAnalystAgent(API_KEY),
    "fpa_manager": lambda: FPAManagerAgent(API_KEY),
    "senior_fpa_manager": lambda: SeniorFPAManagerAgent(API_KEY),
    "vp_finance": lambda: VPFinanceAgent(API_KEY),
    "data_analyst": lambda: DataAnalystAgent(API_KEY),
}
FPA_AGENT_DEFINITIONS = [
    {"agent_type": "fpa_analyst", "display_name": "FP&A Analyst",
     "description": "Variance analysis, KPI tracking, budget review, forecasting, trend analysis",
     "supported_analysis_types": ["variance", "kpi", "forecast", "budget_review", "trend", "adhoc"]},
    {"agent_type": "fpa_manager", "display_name": "FP&A Manager",
     "description": "3-statement modelling, scenario analysis, ZBB, CAPEX appraisal, management packs",
     "supported_analysis_types": ["3statement", "scenario", "zbb", "capex", "management_pack", "adhoc"]},
    {"agent_type": "senior_fpa_manager", "display_name": "Senior FP&A Manager",
     "description": "Long-range planning, M&A analysis, capital structure, board packs",
     "supported_analysis_types": ["lrp", "board_pack", "ma_analysis", "capital_structure", "review", "adhoc"]},
    {"agent_type": "vp_finance", "display_name": "VP of Finance",
     "description": "WACC, capital structure recommendations, investor relations, ERM, consolidation",
     "supported_analysis_types": ["capital_structure", "wacc", "investor_relations", "erm", "consolidation", "financing", "adhoc"]},
    {"agent_type": "data_analyst", "display_name": "Data Analyst",
     "description": "Statistical analysis, Monte Carlo, anomaly detection, cohort analysis, data quality",
     "supported_analysis_types": ["statistical", "monte_carlo", "anomaly", "cohort", "forecast", "data_quality", "adhoc"]},
]

# Audit agent registry
AUDIT_AGENTS = {
    "compliance_auditor": lambda: ComplianceAuditorAgent(API_KEY),
    "audit_manager": lambda: AuditManagerAgent(API_KEY),
    "qa_auditor": lambda: QAAuditorAgent(API_KEY),
    "forensic_auditor": lambda: ForensicAuditorAgent(API_KEY),
}
AUDIT_AGENT_DEFINITIONS = [
    {"agent_type": "compliance_auditor", "display_name": "Compliance Auditor",
     "description": "COSO, SoD, regulatory compliance, RCM, compliance calendar",
     "supported_analysis_types": ["coso", "sod", "regulatory", "rcm", "calendar", "adhoc"]},
    {"agent_type": "audit_manager", "display_name": "Audit Manager",
     "description": "Materiality, going concern, audit programme, sampling, audit committee",
     "supported_analysis_types": ["materiality", "going_concern", "programme", "sampling", "committee", "adhoc"]},
    {"agent_type": "qa_auditor", "display_name": "QA Auditor",
     "description": "ITGC, access review, EQCR, BCP/DR, data governance",
     "supported_analysis_types": ["itgc", "access_review", "eqcr", "bcp_dr", "data_governance", "adhoc"]},
    {"agent_type": "forensic_auditor", "display_name": "Forensic Auditor",
     "description": "Benford's Law, fraud indicators, asset tracing, SAR/STR, AML",
     "supported_analysis_types": ["fraud", "benfords", "asset_trace", "aml", "sar", "adhoc"]},
]

# Session 10 — accounting specialist registry
ACCOUNTING_SPECIALIST_AGENTS = {
    "cost_accountant": lambda: CostAccountantAgent(API_KEY),
    "revenue_accountant": lambda: RevenueAccountantAgent(API_KEY),
    "accounting_manager": lambda: AccountingManagerAgent(API_KEY),
}
ACCOUNTING_SPECIALIST_DEFINITIONS = (
    COST_AGENT_DEFINITIONS + REVENUE_AGENT_DEFINITIONS + ACCOUNTING_MANAGER_DEFINITIONS
)

# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------
ROLE_PERMISSIONS = {
    "viewer": ["queue"],
    "analyst": ["queue", "fpa", "audit", "treasury", "corpfin", "reports", "ingest", "analyze", "accounting_specialist"],
    "senior": ["queue", "fpa", "audit", "treasury", "corpfin", "reports", "ingest", "analyze", "accounting_specialist", "escalations", "tax"],
    "admin": ["queue", "fpa", "audit", "treasury", "corpfin", "reports", "ingest", "analyze", "accounting_specialist", "escalations", "tenants", "tax", "market"],
}
ROLE_KEYS = {
    "viewer": os.getenv("RBAC_KEY_VIEWER", ""),
    "analyst": os.getenv("RBAC_KEY_ANALYST", ""),
    "senior": os.getenv("RBAC_KEY_SENIOR", ""),
    "admin": os.getenv("RBAC_KEY_ADMIN", ""),
}

def get_current_role(x_api_key: Optional[str] = Header(None)) -> dict:
    if not RBAC_ENABLED:
        return {"role": "admin", "permissions": ROLE_PERMISSIONS["admin"]}
    for role, key in ROLE_KEYS.items():
        if key and x_api_key == key:
            return {"role": role, "permissions": ROLE_PERMISSIONS[role]}
    raise HTTPException(status_code=401, detail="Invalid or missing API key")

def require_permission(permission: str):
    def checker(role_info: dict = Depends(get_current_role)):
        if permission not in role_info["permissions"]:
            raise HTTPException(status_code=403, detail=f"Permission '{permission}' required")
        return role_info

# ---------------------------------------------------------------------------
# Phase 4D — Shared escalation helper
# ---------------------------------------------------------------------------
def _phase4d_auto_escalate(result: dict, tenant_id: str, department: str) -> dict:
    """
    Phase 4D: Auto-escalate CRITICAL findings from FP&A, Audit, Treasury,
    and Corp Finance departments into the EscalationStore.

    Checks multiple result structures (flags[], findings[], risk_items[]) for
    CRITICAL severity. If found, creates an escalation and attaches the ID.
    Returns the result dict (mutated in-place with escalation metadata).
    """
    def _has_critical(obj: dict) -> bool:
        # Check top-level flags array
        for flag in obj.get("flags", []):
            if isinstance(flag, dict) and flag.get("severity") == "CRITICAL":
                return True
        # Check findings (audit agents)
        for finding in obj.get("findings", []):
            if isinstance(finding, dict) and finding.get("severity") == "CRITICAL":
                return True
        # Check risks (corp finance, treasury)
        for risk in obj.get("risks", []) + obj.get("risk_items", []):
            if isinstance(risk, dict) and risk.get("severity") == "CRITICAL":
                return True
        # Check explicit auto_escalate flag (accounting specialist pattern)
        if obj.get("auto_escalate"):
            return True
        # Check SAR/STR mandatory reporting (forensic auditor)
        if obj.get("_sar_alert") or obj.get("mandatory_reporting", {}).get("sar_str_required"):
            return True
        return False

    if not _has_critical(result):
        result["escalation_status"] = "not_required"
        return result

    try:
        esc_id = esc_store.create(
            tenant_id=tenant_id,
            junior_suggestion={
                **result,
                "_department": department,
                "_escalation_reason": "Phase 4D auto-escalation — CRITICAL finding detected",
            },
        )
        result["escalation_id"] = esc_id
        result["escalation_status"] = "auto_escalated"
        result["escalation_message"] = (
            f"CRITICAL finding auto-escalated to review queue. "
            f"Escalation ID: {esc_id}. See /escalations tab."
        )
        logger.info("Phase 4D auto-escalation — dept=%s tenant=%s esc_id=%s", department, tenant_id, esc_id)
    except Exception as exc:
        logger.warning("Phase 4D auto-escalation failed — dept=%s error=%s", department, exc)
        result["escalation_status"] = "escalation_failed"
        result["escalation_error"] = str(exc)

    return result
    return checker

# ---------------------------------------------------------------------------
# Escalation engine factory
# ---------------------------------------------------------------------------
def _get_escalation_engine() -> EscalationEngine:
    senior = SeniorAccountantAgent(API_KEY)
    controller = FinancialControllerAgent(API_KEY)
    adapter = get_adapter(os.getenv("ACCOUNTING_SYSTEM", "mock"))
    emailer = EscalationEmailer(
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_pass=os.getenv("SMTP_PASSWORD", ""),
        from_address=os.getenv("FROM_EMAIL", ""),
        operator_email=os.getenv("OPERATOR_EMAIL", "")
    )
    def junior_agent_factory(tenant_id: str = "default", jurisdiction: str = "TZ"):
        return JuniorAccountantAgent(tenant_id=tenant_id, jurisdiction=jurisdiction)

    return EscalationEngine(
        senior_agent=senior,
        controller_agent=controller,
        accounting_adapter=adapter,
        emailer=emailer,
        store=esc_store,               # use module-level singleton
        junior_agent_factory=junior_agent_factory,
        auto_post_on_approval=True
    )

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class TenantCreate(BaseModel):
    id: str
    display_name: str
    jurisdiction: str = "TZ"
    accounting_standard: str = "IFRS"
    country: str = "Tanzania"
    currency: str = "TZS"
    notes: str = ""

class IngestText(BaseModel):
    raw_text: str = Field(..., max_length=200_000)
    tenant_id: str
    jurisdiction: str = "TZ"
    source: str = "manual"

class IngestEmail(BaseModel):
    raw_email: str = Field(..., max_length=200_000)
    tenant_id: str
    jurisdiction: str = "TZ"

class IngestWebhook(BaseModel):
    payload: dict
    tenant_id: str
    jurisdiction: str = "TZ"

class DecideRequest(BaseModel):
    decision: str
    decided_by: str = "operator"
    notes: str = Field("", max_length=10_000)

class TaxAnalyzeRequest(BaseModel):
    raw_data: str = Field(..., max_length=200_000)
    tenant_id: str
    period: str
    jurisdiction: str = "TZ"
    extra_context: str = Field("", max_length=10_000)
    enable_research: bool = False

class FPAAnalyzeRequest(BaseModel):
    raw_data: str = Field(..., max_length=200_000)
    tenant_id: str
    period: str
    jurisdiction: str = "TZ"
    agent_type: str = "fpa_analyst"
    analysis_type: str = "adhoc"
    extra_context: str = Field("", max_length=10_000)
    enable_research: bool = False

class AuditAnalyzeRequest(BaseModel):
    raw_data: str = Field(..., max_length=200_000)
    tenant_id: str
    audit_period: str
    jurisdiction: str = "TZ"
    agent_type: str = "compliance_auditor"
    audit_scope: str = "adhoc"
    extra_context: str = Field("", max_length=10_000)
    enable_research: bool = False

class TreasuryAnalyzeRequest(BaseModel):
    raw_data: str = Field(..., max_length=200_000)
    tenant_id: str
    period: str
    jurisdiction: str = "TZ"
    agent_type: str = "cash_flow"
    analysis_type: str = "adhoc"
    extra_context: str = Field("", max_length=10_000)
    enable_research: bool = False

class CorpFinAnalyzeRequest(BaseModel):
    raw_data: str = Field(..., max_length=200_000)
    tenant_id: str
    period: str
    jurisdiction: str = "TZ"
    agent_type: str = "valuations"
    analysis_type: str = "adhoc"
    extra_context: str = Field("", max_length=10_000)
    enable_research: bool = False

class UniversalAnalyzeRequest(BaseModel):
    raw_data: str = Field(..., max_length=200_000)
    tenant_id: str
    period: str = ""
    jurisdiction: str = "TZ"
    extra_context: str = Field("", max_length=10_000)
    enable_research: bool = False
    force_department: str = ""
    force_agent_type: str = ""
    force_analysis_type: str = ""

class ResubmitRequest(BaseModel):
    operator_context: str = Field(..., max_length=10_000)

# Session 10 — new request models
class AccountingSpecialistRequest(BaseModel):
    raw_data: str = Field(..., max_length=200_000)
    tenant_id: str
    period: str
    jurisdiction: str = "TZ"
    agent_type: str = "cost_accountant"
    analysis_type: str = "adhoc"
    extra_context: str = Field("", max_length=10_000)
    enable_research: bool = False
    include_market_data: bool = False  # If True, fetches live FX rates before calling agent

class SEtaxRequest(BaseModel):
    net_llc_income: float
    period: str

class VATRequest(BaseModel):
    taxable_sales: float
    input_vat: float
    period: str

class AMTRequest(BaseModel):
    turnover: float
    period: str

class ProvisionalRequest(BaseModel):
    estimated_annual_income: float
    quarter: int
    year: int

class QuarterlyRequest(BaseModel):
    estimated_annual_income: float
    quarter: int
    year: int

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _run_ingest_and_process(raw_text: str, tenant_id: str, jurisdiction: str, source: str):
    suggestion_id = str(uuid.uuid4())
    agent = JuniorAccountantAgent(tenant_id=tenant_id, jurisdiction=jurisdiction)
    suggestion = agent.process(raw_input=raw_text, source=source, extra_context="")
    suggestion["id"] = suggestion_id
    store.save_suggestion(suggestion, tenant_id=tenant_id, jurisdiction=jurisdiction)
    return suggestion_id, suggestion

def _handle_accounting_specialist_escalation(result: dict, tenant_id: str):
    """If CRITICAL flags present and auto_escalate=true, save to escalation store."""
    if not result.get("auto_escalate"):
        return None
    try:
        agent_name = result.get("agent", "AccountingSpecialist")
        esc_id = esc_store.create(
            tenant_id=tenant_id,
            junior_suggestion={
                "agent": agent_name,
                "summary": result.get("executive_summary", ""),
                "flags": result.get("flags", []),
                "escalation_reason": result.get("escalation_reason", "CRITICAL flag detected"),
                "full_result": result,
            }
        )
        logger.warning(f"Auto-escalated {agent_name} CRITICAL finding — esc_id={esc_id}")
        return esc_id
    except Exception as e:
        logger.error(f"Auto-escalation failed: {e}")
        return None

# ===========================================================================
# ROUTES
# ===========================================================================

# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "5.1.0",
        "session": 10,
        "agents": {
            "accounting": ["JuniorAccountant", "SeniorAccountant", "FinancialController",
                           "CostAccountant", "RevenueAccountant", "AccountingManager"],
            "tax": ["TaxAgentTZ", "TaxAgentUS", "TaxOrchestrator", "TaxSupervisorAgent", "TaxAccountantAgent", "TaxStrategyManagerAgent"],
            "fpa": [d["display_name"] for d in FPA_AGENT_DEFINITIONS],
            "audit": [d["display_name"] for d in AUDIT_AGENT_DEFINITIONS],
            "treasury": [d.get("display_name") or d.get("class") or d["agent_type"] for d in TREASURY_AGENT_DEFINITIONS],
            "corp_finance": [d.get("display_name") or d.get("class") or d["agent_type"] for d in CORP_FINANCE_AGENT_DEFINITIONS],
            "accounting_specialists": [d["display_name"] for d in ACCOUNTING_SPECIALIST_DEFINITIONS],
        },
        "market_data_live": MARKET_DATA_LIVE,
        "rbac_enabled": RBAC_ENABLED
    }

@app.get("/auth/role")
def get_role(role_info: dict = Depends(get_current_role)):
    return role_info

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def dashboard():
    try:
        html = (_ROOT / "dashboard/index.html").read_text(encoding="utf-8")
        return HTMLResponse(content=html)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Dashboard not found</h1><p>Place dashboard/index.html in the project root.</p>")

# ---------------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------------
@app.get("/tenants")
def list_tenants(_: dict = Depends(require_permission("queue"))):
    return {"tenants": store.list_tenants()}

@app.post("/tenants")
def create_tenant(body: TenantCreate, _: dict = Depends(require_permission("tenants"))):
    store.create_tenant(
        tenant_id=body.id,
        display_name=body.display_name,
        jurisdiction=body.jurisdiction,
        accounting_standard=body.accounting_standard,
        country=body.country,
        currency=body.currency,
        notes=body.notes
    )
    return {"ok": True, "tenant_id": body.id}

@app.delete("/tenants/{tenant_id}")
def delete_tenant(tenant_id: str, _: dict = Depends(require_permission("tenants"))):
    store.delete_tenant(tenant_id)
    return {"ok": True}

@app.post("/tenants/detect")
def detect_tenant(body: IngestText, _: dict = Depends(require_permission("ingest"))):
    result = ingestor.from_raw_text(body.raw_text)
    text = result.get("text", "")
    tenants = store.list_tenants()
    for t in tenants:
        if t["id"].lower() in text.lower() or t.get("display_name", "").lower() in text.lower():
            return {"detected_tenant": t["id"], "confidence": "high"}
    return {"detected_tenant": None, "confidence": "none", "suggestion": "Create a new tenant or specify manually"}

# ---------------------------------------------------------------------------
# Mersi Health Check
# ---------------------------------------------------------------------------
@app.post("/mersi/health-check")
def mersi_health_check(
    period: Optional[str] = None,
    qbo_mode: str = "mock",
    fishbowl_mode: str = "mock",
    _: dict = Depends(require_permission("audit"))
):
    """
    Run the Mersi finance health check — pulls from QBO + Fishbowl,
    runs all reconciliation and integrity checks, returns structured findings.

    period:         YYYY-MM (defaults to current month)
    qbo_mode:       "mock" | "quickbooks" (use "quickbooks" when credentials are configured)
    fishbowl_mode:  "mock" | "live" (use "live" when Fishbowl credentials are configured)
    """
    from audits.mersi_health_check import MersiHealthCheck
    checker = MersiHealthCheck(qbo_mode=qbo_mode, fishbowl_mode=fishbowl_mode)
    report = checker.run(period=period)
    return report.to_dict()

@app.get("/mersi/health-check/latest")
def mersi_health_check_get(
    period: Optional[str] = None,
    _: dict = Depends(require_permission("audit"))
):
    """GET convenience wrapper — runs health check with mock data."""
    from audits.mersi_health_check import MersiHealthCheck
    checker = MersiHealthCheck()
    report = checker.run(period=period)
    return report.to_dict()

# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------
@app.post("/ingest/text")
def ingest_text(body: IngestText, _: dict = Depends(require_permission("ingest"))):
    result = ingestor.from_raw_text(body.raw_text)
    raw_text = result.get("text", "")
    suggestion_id, suggestion = _run_ingest_and_process(raw_text, body.tenant_id, body.jurisdiction, body.source)
    return {"suggestion_id": suggestion_id, "suggestion": suggestion}

@app.post("/ingest/email")
def ingest_email(body: IngestEmail, _: dict = Depends(require_permission("ingest"))):
    result = ingestor.from_email(body.raw_email)
    raw_text = result.get("text", "")
    suggestion_id, suggestion = _run_ingest_and_process(raw_text, body.tenant_id, body.jurisdiction, "email")
    return {"suggestion_id": suggestion_id, "suggestion": suggestion}

@app.post("/ingest/upload")
async def ingest_upload(
    file: UploadFile = File(...),
    tenant_id: str = "default",
    jurisdiction: str = "TZ",
    _: dict = Depends(require_permission("ingest"))
):
    content = await file.read()
    result = ingestor.from_file(content, file.filename)
    raw_text = result.get("text", "")
    warnings = result.get("warnings", [])
    suggestion_id, suggestion = _run_ingest_and_process(raw_text, tenant_id, jurisdiction, f"upload:{file.filename}")
    return {"suggestion_id": suggestion_id, "suggestion": suggestion, "ingestion_warnings": warnings}

@app.post("/ingest/webhook/{system}")
def ingest_webhook(system: str, body: IngestWebhook, _: dict = Depends(require_permission("ingest"))):
    result = ingestor.from_webhook(body.payload, system)
    raw_text = result.get("text", "")
    suggestion_id, suggestion = _run_ingest_and_process(raw_text, body.tenant_id, body.jurisdiction, f"webhook:{system}")
    return {"suggestion_id": suggestion_id, "suggestion": suggestion}

# ---------------------------------------------------------------------------
# Suggestions / Queue
# ---------------------------------------------------------------------------
@app.get("/suggestions/{tenant_id}")
def list_suggestions(tenant_id: str, status: Optional[str] = None, limit: int = 50,
                     _: dict = Depends(require_permission("queue"))):
    suggestions = store.list_suggestions(tenant_id=tenant_id, status=status, limit=limit)
    return {"suggestions": suggestions}

@app.get("/suggestions/{tenant_id}/{suggestion_id}")
def get_suggestion(tenant_id: str, suggestion_id: str, _: dict = Depends(require_permission("queue"))):
    s = store.get_suggestion(suggestion_id)
    if not s or s.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return {"suggestion": s}

@app.post("/suggestions/{tenant_id}/{suggestion_id}/decide")
def decide_suggestion(
    tenant_id: str,
    suggestion_id: str,
    body: DecideRequest,
    _: dict = Depends(require_permission("queue"))
):
    decision = body.decision.upper()

    if decision == "ESCALATE":
        suggestions = store.list_suggestions(tenant_id=tenant_id, limit=1000)
        suggestion = next((s for s in suggestions if s["id"] == suggestion_id), None)
        if not suggestion:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        suggestion["suggestion_id"] = suggestion.get("id", suggestion_id)
        engine = _get_escalation_engine()

        def _run():
            engine.process(suggestion, tenant_id, body.notes, "")

        threading.Thread(target=_run, daemon=True).start()
        store.update_decision(suggestion_id, "ESCALATED", body.decided_by, body.notes)
        return {"ok": True, "decision": "ESCALATED", "message": "Escalation chain started in background"}

    store.update_decision(suggestion_id, decision, body.decided_by, body.notes)
    return {"ok": True, "decision": decision}

@app.get("/stats/{tenant_id}")
def stats(tenant_id: str, _: dict = Depends(require_permission("queue"))):
    return {"stats": store.stats(tenant_id)}

# ---------------------------------------------------------------------------
# Escalations
# ---------------------------------------------------------------------------
@app.get("/escalations")
def list_escalations(tenant_id: Optional[str] = None, _: dict = Depends(require_permission("escalations"))):
    all_escs = esc_store.list_all()
    if tenant_id:
        all_escs = [e for e in all_escs if e.get("tenant_id") == tenant_id]
    return {"escalations": all_escs}

@app.get("/escalations/pending")
def list_pending(_: dict = Depends(require_permission("escalations"))):
    return {"escalations": esc_store.list_pending_human()}

@app.get("/escalations/rejected")
def list_rejected(_: dict = Depends(require_permission("escalations"))):
    return {"escalations": esc_store.list_rejected()}

@app.get("/escalations/{esc_id}")
def get_escalation(esc_id: str, _: dict = Depends(require_permission("escalations"))):
    esc = esc_store.get(esc_id)
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return {"escalation": esc}

@app.post("/escalations/{esc_id}/approve")
def approve_escalation(esc_id: str, body: DecideRequest, _: dict = Depends(require_permission("escalations"))):
    engine = _get_escalation_engine()
    engine.process_human_approval(esc_id, True, body.notes)
    return {"ok": True, "decision": "APPROVED"}

@app.post("/escalations/{esc_id}/reject")
def reject_escalation(esc_id: str, body: DecideRequest, _: dict = Depends(require_permission("escalations"))):
    engine = _get_escalation_engine()
    engine.process_human_approval(esc_id, False, body.notes)
    return {"ok": True, "decision": "REJECTED"}

@app.post("/escalations/{esc_id}/resubmit")
def resubmit_escalation(esc_id: str, body: ResubmitRequest, _: dict = Depends(require_permission("escalations"))):
    engine = _get_escalation_engine()
    esc = esc_store.get(esc_id)
    tenant_id = esc.get("tenant_id", "default") if esc else "default"
    engine.process_resubmit(esc_id, body.operator_context, tenant_id)
    return {"ok": True, "message": "Resubmitted — fresh escalation chain started"}

# ---------------------------------------------------------------------------
# Tax
# ---------------------------------------------------------------------------
@app.post("/tax/analyze")
def tax_analyze(body: TaxAnalyzeRequest, _: dict = Depends(require_permission("tax"))):
    orch = TaxOrchestrator()
    try:
        result = orch.analyze(
            raw_input=body.raw_data,
            tenant_id=body.tenant_id,
            period=body.period,
            jurisdiction=body.jurisdiction,
            extra_context=body.extra_context,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result

@app.post("/tax/analyze/tz")
def tax_analyze_tz(body: TaxAnalyzeRequest, _: dict = Depends(require_permission("tax"))):
    agent = TaxAgentTZ()
    return agent.analyze(
        raw_input=body.raw_data,
        tenant_id=body.tenant_id,
        period=body.period,
        extra_context=body.extra_context,
    )

@app.post("/tax/analyze/us")
def tax_analyze_us(body: TaxAnalyzeRequest, _: dict = Depends(require_permission("tax"))):
    agent = TaxAgentUS()
    return agent.analyze(
        raw_input=body.raw_data,
        tenant_id=body.tenant_id,
        period=body.period,
        extra_context=body.extra_context,
    )

@app.get("/tax/rules/tz")
def tax_rules_tz(_: dict = Depends(require_permission("tax"))):
    return {"rules": TZ_TAX_RULES}

@app.get("/tax/rules/us")
def tax_rules_us(_: dict = Depends(require_permission("tax"))):
    return {"rules": US_TAX_RULES}

@app.get("/tax/rates/config")
def tax_rates_config(_: dict = Depends(require_permission("tax"))):
    try:
        with open(_ROOT / "config/tax_rates.json") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="config/tax_rates.json not found")

@app.post("/tax/compute/se-tax")
def compute_se_tax(body: SEtaxRequest, _: dict = Depends(require_permission("tax"))):
    net = body.net_llc_income
    se_net = net * 0.9235
    ss_wage_base = 184500
    ss_tax = min(se_net, ss_wage_base) * 0.124
    medicare = se_net * 0.029
    add_medicare = max(0, net - 200000) * 0.009
    total_se = ss_tax + medicare + add_medicare
    deduction = total_se * 0.5
    return {
        "period": body.period,
        "net_llc_income": net,
        "se_net_income_92_35pct": round(se_net, 2),
        "ss_tax_12_4pct": round(ss_tax, 2),
        "medicare_2_9pct": round(medicare, 2),
        "additional_medicare_0_9pct": round(add_medicare, 2),
        "total_se_tax": round(total_se, 2),
        "se_tax_deduction_50pct": round(deduction, 2),
        "note": "SE tax deduction reduces gross income on Form 1040"
    }

@app.post("/tax/compute/vat")
def compute_vat(body: VATRequest, _: dict = Depends(require_permission("tax"))):
    output_vat = body.taxable_sales * 0.18
    net_vat = output_vat - body.input_vat
    return {
        "period": body.period,
        "taxable_sales": body.taxable_sales,
        "output_vat_18pct": round(output_vat, 2),
        "input_vat_claimed": round(body.input_vat, 2),
        "net_vat_payable": round(net_vat, 2),
        "due_date": "20th of following month",
        "note": "VAT return due to TRA by 20th of following month"
    }

@app.post("/tax/compute/amt")
def compute_amt(body: AMTRequest, _: dict = Depends(require_permission("tax"))):
    amt = body.turnover * 0.01
    return {
        "period": body.period,
        "turnover": body.turnover,
        "amt_1pct": round(amt, 2),
        "note": "AMT applies when company has losses 3+ consecutive years. Payable to TRA."
    }

@app.post("/tax/compute/provisional")
def compute_provisional(body: ProvisionalRequest, _: dict = Depends(require_permission("tax"))):
    quarterly = body.estimated_annual_income * 0.30 / 4
    return {
        "quarter": body.quarter,
        "year": body.year,
        "estimated_annual_taxable_income": body.estimated_annual_income,
        "corporate_tax_rate": "30%",
        "quarterly_provisional_tax": round(quarterly, 2),
        "due_date": "Within 3 months of quarter end"
    }

@app.post("/tax/compute/quarterly")
def compute_quarterly_us(body: QuarterlyRequest, _: dict = Depends(require_permission("tax"))):
    due_dates = {1: "April 15", 2: "June 15", 3: "September 15", 4: "January 15"}
    estimated_tax = body.estimated_annual_income * 0.25
    quarterly = estimated_tax / 4
    return {
        "quarter": body.quarter,
        "year": body.year,
        "estimated_annual_income": body.estimated_annual_income,
        "effective_rate_used": "25% (blended federal + SE estimate)",
        "quarterly_payment": round(quarterly, 2),
        "due_date": due_dates.get(body.quarter, "See IRS schedule"),
        "form": "Form 1040-ES",
        "note": "Use actual AGI projection for accuracy. Consult SE tax computation for full picture."
    }

# ---------------------------------------------------------------------------
# Tax Supervisor + Tax Accountant (Session 12)
# ---------------------------------------------------------------------------

class TaxSuperviseRequest(BaseModel):
    tax_analysis: dict                                   # full output from TaxAgentTZ/US
    tenant_id: str
    extra_context: str = Field("", max_length=10_000)

class TaxAccountingRequest(BaseModel):
    raw_data: str = Field(..., max_length=200_000)
    tenant_id: str
    jurisdiction: str = "Tanzania"
    period: Optional[str] = None
    analysis_type: str = "general_tax_accounting"
    extra_context: str = Field("", max_length=10_000)
    enable_research: bool = False

@app.post("/tax/supervise")
def tax_supervise(body: TaxSuperviseRequest, _: dict = Depends(require_permission("tax"))):
    """Run a completed tax analysis through the Tax Supervisor for quality review."""
    supervisor = TaxSupervisorAgent()
    return supervisor.review(
        tax_analysis=body.tax_analysis,
        tenant_id=body.tenant_id,
        extra_context=body.extra_context,
    )

@app.post("/tax/analyze/supervised")
def tax_analyze_supervised(body: TaxAnalyzeRequest, _: dict = Depends(require_permission("tax"))):
    """Run tax analysis through jurisdiction agent then automatically pass to Tax Supervisor."""
    orch = TaxOrchestrator()
    try:
        tax_result = orch.analyze(
            raw_input=body.raw_data,
            tenant_id=body.tenant_id,
            period=body.period,
            jurisdiction=body.jurisdiction,
            extra_context=body.extra_context,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not TAX_SUPERVISOR_ENABLED:
        tax_result["supervisor_skipped"] = True
        return tax_result

    supervisor = TaxSupervisorAgent()
    supervisor_review = supervisor.review(
        tax_analysis=tax_result,
        tenant_id=body.tenant_id,
        extra_context=body.extra_context,
    )
    supervisor_review["original_tax_analysis"] = tax_result
    return supervisor_review

@app.get("/tax/accounting/agents")
def tax_accounting_agents(_: dict = Depends(require_permission("tax"))):
    return {"agents": TAX_ACCOUNTANT_DEFINITIONS}

@app.post("/tax/accounting/analyze")
def tax_accounting_analyze(body: TaxAccountingRequest, _: dict = Depends(require_permission("tax"))):
    """Tax Accountant — deferred tax, provisions, tax journal entries, reconciliations."""
    agent = TaxAccountantAgent()
    result = agent.analyze(
        raw_input=body.raw_data,
        tenant_id=body.tenant_id,
        jurisdiction=body.jurisdiction,
        period=body.period,
        analysis_type=body.analysis_type,
        extra_context=body.extra_context,
    )
    # Auto-escalate CRITICAL items into the escalation store
    if result.get("auto_escalate"):
        try:
            esc_id = esc_store.create(
                tenant_id=body.tenant_id,
                junior_suggestion=result,
            )
            result["escalation_id"] = esc_id
            result["escalation_message"] = "Auto-escalated due to CRITICAL flag — see escalation queue."
        except Exception as exc:
            logger.warning("Tax accounting auto-escalation failed: %s", exc)
    return result

class TaxStrategyRequest(BaseModel):
    raw_data: str = Field(..., max_length=200_000)
    tenant_id: str
    jurisdiction: str = "Both"
    analysis_type: str = "general_tax_strategy"
    horizon: str = "all"
    period: Optional[str] = None
    extra_context: str = Field("", max_length=10_000)
    enable_research: bool = False

@app.get("/tax/strategy/agents")
def tax_strategy_agents(_: dict = Depends(require_permission("tax"))):
    return {"agents": TAX_STRATEGY_DEFINITIONS}

@app.post("/tax/strategy/analyze")
def tax_strategy_analyze(body: TaxStrategyRequest, _: dict = Depends(require_permission("tax"))):
    """Tax Strategy Manager — forward-looking tax planning, structuring, and risk assessment."""
    agent = TaxStrategyManagerAgent()
    result = agent.analyze(
        raw_input=body.raw_data,
        tenant_id=body.tenant_id,
        jurisdiction=body.jurisdiction,
        analysis_type=body.analysis_type,
        horizon=body.horizon,
        period=body.period,
        extra_context=body.extra_context,
    )
    if result.get("auto_escalate"):
        try:
            esc_id = esc_store.create(
                tenant_id=body.tenant_id,
                junior_suggestion=result,
            )
            result["escalation_id"] = esc_id
            result["escalation_message"] = "CRITICAL tax risk auto-escalated to review queue."
        except Exception as exc:
            logger.warning("Tax strategy auto-escalation failed: %s", exc)
    return result

# ---------------------------------------------------------------------------
# FP&A
# ---------------------------------------------------------------------------
@app.get("/fpa/agents")
def fpa_agents(_: dict = Depends(require_permission("fpa"))):
    return {"agents": FPA_AGENT_DEFINITIONS}

@app.post("/fpa/analyze")
def fpa_analyze(body: FPAAnalyzeRequest, _: dict = Depends(require_permission("fpa"))):
    if body.agent_type not in FPA_AGENTS:
        raise HTTPException(status_code=400, detail=f"Unknown FP&A agent: {body.agent_type}")
    agent = FPA_AGENTS[body.agent_type]()
    analysis_type_field = {
        "fpa_analyst": "analysis_type",
        "fpa_manager": "model_type",
        "senior_fpa_manager": "output_type",
        "vp_finance": "output_type",
        "data_analyst": "analysis_type"
    }.get(body.agent_type, "analysis_type")

    kwargs = {
        "raw_data": body.raw_data,
        "period": body.period,
        "tenant_id": body.tenant_id,
        "jurisdiction": body.jurisdiction,
        analysis_type_field: body.analysis_type,
        "extra_context": body.extra_context,
        "enable_research": body.enable_research
    }
    if body.agent_type == "fpa_manager":
        kwargs["analyst_output"] = body.extra_context
    elif body.agent_type == "senior_fpa_manager":
        kwargs["manager_output"] = body.extra_context
    elif body.agent_type == "vp_finance":
        kwargs["senior_fpa_output"] = body.extra_context

    result = agent.analyze(**kwargs)
    return _phase4d_auto_escalate(result, body.tenant_id, "fpa")

# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
@app.get("/audit/agents")
def audit_agents(_: dict = Depends(require_permission("audit"))):
    return {"agents": AUDIT_AGENT_DEFINITIONS}

@app.post("/audit/analyze")
def audit_analyze(body: AuditAnalyzeRequest, _: dict = Depends(require_permission("audit"))):
    if body.agent_type not in AUDIT_AGENTS:
        raise HTTPException(status_code=400, detail=f"Unknown audit agent: {body.agent_type}")
    agent = AUDIT_AGENTS[body.agent_type]()
    if body.agent_type == "forensic_auditor":
        result = agent.investigate(
            raw_data=body.raw_data,
            investigation_period=body.audit_period,
            tenant_id=body.tenant_id,
            jurisdiction=body.jurisdiction,
            investigation_type=body.audit_scope,
            extra_context=body.extra_context,
            enable_research=body.enable_research
        )
        if result.get("mandatory_reporting", {}).get("sar_str_required"):
            result["_sar_alert"] = {
                "banner": "⚠️ SAR/STR REQUIRED — Forensic Auditor has flagged mandatory reporting. Human operator must review and file.",
                "severity": "CRITICAL"
            }
        return _phase4d_auto_escalate(result, body.tenant_id, "audit")

    if body.agent_type == "audit_manager":
        result = agent.audit(
            raw_data=body.raw_data,
            audit_period=body.audit_period,
            tenant_id=body.tenant_id,
            jurisdiction=body.jurisdiction,
            audit_type=body.audit_scope,
            extra_context=body.extra_context,
            enable_research=body.enable_research
        )
    else:
        result = agent.audit(
            raw_data=body.raw_data,
            audit_period=body.audit_period,
            tenant_id=body.tenant_id,
            jurisdiction=body.jurisdiction,
            audit_type=body.audit_scope if body.agent_type == "audit_manager" else None,
            audit_scope=body.audit_scope if body.agent_type == "compliance_auditor" else None,
            review_type=body.audit_scope if body.agent_type == "qa_auditor" else None,
            extra_context=body.extra_context,
            enable_research=body.enable_research
        )
    return _phase4d_auto_escalate(result, body.tenant_id, "audit")

# ---------------------------------------------------------------------------
# Treasury
# ---------------------------------------------------------------------------
@app.get("/treasury/agents")
def treasury_agents(_: dict = Depends(require_permission("treasury"))):
    return {"agents": TREASURY_AGENT_DEFINITIONS}

@app.post("/treasury/analyze")
def treasury_analyze(body: TreasuryAnalyzeRequest, _: dict = Depends(require_permission("treasury"))):
    if body.agent_type not in TREASURY_AGENTS:
        raise HTTPException(status_code=400, detail=f"Unknown treasury agent: {body.agent_type}")

    market_data = None
    if MARKET_DATA_LIVE:
        try:
            market_data = market_adapter.fetch(include_us_rates=True, include_tz_rates=True)
        except Exception as e:
            logger.warning(f"Market data fetch failed for treasury: {e}")

    agent = TREASURY_AGENTS[body.agent_type](API_KEY)
    result = agent.analyze(
        raw_data=body.raw_data,
        period=body.period,
        tenant_id=body.tenant_id,
        jurisdiction=body.jurisdiction,
        analysis_type=body.analysis_type,
        extra_context=body.extra_context,
        enable_research=body.enable_research,
        market_data=market_data
    )
    return _phase4d_auto_escalate(result, body.tenant_id, "treasury")

# ---------------------------------------------------------------------------
# Corporate Finance
# ---------------------------------------------------------------------------
@app.get("/corpfin/agents")
def corpfin_agents(_: dict = Depends(require_permission("corpfin"))):
    return {"agents": CORP_FINANCE_AGENT_DEFINITIONS}

@app.post("/corpfin/analyze")
def corpfin_analyze(body: CorpFinAnalyzeRequest, _: dict = Depends(require_permission("corpfin"))):
    if body.agent_type not in CORP_FINANCE_AGENTS:
        raise HTTPException(status_code=400, detail=f"Unknown corp finance agent: {body.agent_type}")

    market_data = None
    if MARKET_DATA_LIVE:
        try:
            market_data = market_adapter.fetch(include_us_rates=True, include_tz_rates=True)
        except Exception as e:
            logger.warning(f"Market data fetch failed for corpfin: {e}")

    agent = CORP_FINANCE_AGENTS[body.agent_type](API_KEY)
    result = agent.analyze(
        raw_data=body.raw_data,
        period=body.period,
        tenant_id=body.tenant_id,
        jurisdiction=body.jurisdiction,
        analysis_type=body.analysis_type,
        extra_context=body.extra_context,
        enable_research=body.enable_research,
        market_data=market_data
    )
    return _phase4d_auto_escalate(result, body.tenant_id, "corpfin")

# ---------------------------------------------------------------------------
# Universal (Phase4Orchestrator)
# ---------------------------------------------------------------------------
@app.post("/analyze")
def universal_analyze(body: UniversalAnalyzeRequest, _: dict = Depends(require_permission("analyze"))):
    orch = Phase4Orchestrator(API_KEY)
    result = orch.route(
        raw_data=body.raw_data,
        tenant_id=body.tenant_id,
        period=body.period,
        jurisdiction=body.jurisdiction,
        extra_context=body.extra_context,
        enable_research=body.enable_research,
        force_department=body.force_department or None,
        force_agent_type=body.force_agent_type or None,
        force_analysis_type=body.force_analysis_type or None
    )
    return result

# ---------------------------------------------------------------------------
# Session 10 — Accounting Specialists (Cost, Revenue, Accounting Manager)
# ---------------------------------------------------------------------------
@app.get("/accounting/agents")
def accounting_specialist_agents(_: dict = Depends(require_permission("accounting_specialist"))):
    return {"agents": ACCOUNTING_SPECIALIST_DEFINITIONS}

@app.post("/accounting/analyze")
def accounting_specialist_analyze(
    body: AccountingSpecialistRequest,
    _: dict = Depends(require_permission("accounting_specialist"))
):
    if body.agent_type not in ACCOUNTING_SPECIALIST_AGENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown accounting specialist agent: {body.agent_type}. "
                   f"Valid: {list(ACCOUNTING_SPECIALIST_AGENTS.keys())}"
        )

    # Optionally fetch live market data (FX rates useful for multi-currency cost/revenue)
    market_data = None
    if body.include_market_data:
        try:
            market_data = market_adapter.fetch(
                include_us_rates=(body.jurisdiction == "US"),
                include_tz_rates=(body.jurisdiction == "TZ")
            )
            logger.info(f"Market data fetched for {body.agent_type} — source: {market_data.get('meta', {}).get('source')}")
        except Exception as e:
            logger.warning(f"Market data fetch failed: {e}")

    agent = ACCOUNTING_SPECIALIST_AGENTS[body.agent_type]()
    result = agent.analyze(
        raw_data=body.raw_data,
        period=body.period,
        tenant_id=body.tenant_id,
        jurisdiction=body.jurisdiction,
        analysis_type=body.analysis_type,
        extra_context=body.extra_context,
        enable_research=body.enable_research,
        market_data=market_data
    )

    # Auto-escalate CRITICAL findings into the escalation store
    esc_id = None
    if result.get("auto_escalate"):
        esc_id = _handle_accounting_specialist_escalation(result, body.tenant_id)

    if esc_id:
        result["_escalation_id"] = esc_id
        result["_escalation_notice"] = (
            f"⚠️ CRITICAL findings auto-escalated — escalation ID: {esc_id}. "
            "Review in the Escalations tab."
        )

    return result

# ---------------------------------------------------------------------------
# Session 10 — Market Data
# ---------------------------------------------------------------------------
@app.get("/market/rates")
def get_market_rates(
    base: str = "USD",
    include_us_rates: bool = True,
    include_tz_rates: bool = True,
    _: dict = Depends(require_permission("market"))
):
    """
    Fetch current market rates.
    Returns FX rates (ExchangeRate-API), US interest rates (FRED), TZ rates (cached).
    """
    try:
        data = market_adapter.fetch(
            base_currency=base,
            include_us_rates=include_us_rates,
            include_tz_rates=include_tz_rates
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Market data unavailable: {e}")

@app.get("/market/fx/{from_currency}/{to_currency}")
def get_fx_rate(from_currency: str, to_currency: str, _: dict = Depends(require_permission("market"))):
    """Get a single FX spot rate."""
    rate = market_adapter.get_fx_rate(from_currency.upper(), to_currency.upper())
    if rate is None:
        raise HTTPException(status_code=404, detail=f"Rate not found: {from_currency}/{to_currency}")
    return {
        "from": from_currency.upper(),
        "to": to_currency.upper(),
        "rate": rate,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
@app.get("/reports")
def list_reports(tenant_id: Optional[str] = None, _: dict = Depends(require_permission("reports"))):
    if not REPORTS_DIR.exists():
        return {"reports": []}
    files = sorted(REPORTS_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    result = []
    for f in files:
        if tenant_id and not f.name.startswith(tenant_id):
            continue
        result.append({
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "created_at": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat()
        })
    return {"reports": result}

@app.get("/reports/latest/{tenant_id}")
def latest_report(tenant_id: str, _: dict = Depends(require_permission("reports"))):
    files = sorted(
        REPORTS_DIR.glob(f"{tenant_id}_*.pdf"),
        key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not files:
        raise HTTPException(status_code=404, detail="No reports found for tenant")
    f = files[0]
    return {"filename": f.name, "size_bytes": f.stat().st_size}

@app.get("/reports/{filename}")
def download_report(filename: str, _: dict = Depends(require_permission("reports"))):
    path = REPORTS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(path=str(path), media_type="application/pdf", filename=filename)
