"""
api/tax_routes.py — Phase 3 Tax API Endpoints
===============================================
Mount this router into main.py with:
    from api.tax_routes import router as tax_router
    app.include_router(tax_router, prefix="/tax", tags=["Tax"])

Endpoints:
    POST /tax/analyze          — Analyze raw data (routes TZ or US by jurisdiction)
    POST /tax/analyze/tz       — Force Tanzania tax analysis
    POST /tax/analyze/us       — Force US tax analysis
    GET  /tax/escalations      — List tax escalations (from escalation DB)
    GET  /tax/rules/tz         — Show Tanzania tax rule constants
    GET  /tax/rules/us         — Show US tax rule constants
    POST /tax/compute/se-tax   — Quick SE tax computation (US)
    POST /tax/compute/vat      — Quick VAT return computation (TZ)
    POST /tax/compute/amt      — Quick AMT computation (TZ)
    POST /tax/compute/provisional — Quick provisional tax (TZ)
    POST /tax/compute/quarterly   — Quick quarterly estimate (US)
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from agents.tax_agent_tz import TaxAgentTZ, TZ_TAX_RULES
from agents.tax_agent_us import TaxAgentUS, US_TAX_RULES
from agents.tax_orchestrator import get_tax_orchestrator

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class TaxAnalyzeRequest(BaseModel):
    raw_input: str
    tenant_id: str
    jurisdiction: str          # "Tanzania"|"TZ"|"United States"|"US"
    period: Optional[str] = None
    extra_context: str = ""
    online_research: str = ""
    send_to_escalation: bool = False   # If True, push result into escalation chain

class TaxAnalyzeTZRequest(BaseModel):
    raw_input: str
    tenant_id: str
    period: Optional[str] = None
    extra_context: str = ""
    online_research: str = ""
    send_to_escalation: bool = False

class TaxAnalyzeUSRequest(BaseModel):
    raw_input: str
    tenant_id: str
    period: Optional[str] = None
    extra_context: str = ""
    online_research: str = ""
    send_to_escalation: bool = False

class SETaxRequest(BaseModel):
    net_llc_income: float

class VATReturnRequest(BaseModel):
    output_vat: float
    input_vat: float
    wht_vat_withheld: float = 0.0
    currency: str = "TZS"

class AMTRequest(BaseModel):
    annual_turnover: float
    consecutive_loss_years: int

class ProvisionalTaxRequest(BaseModel):
    estimated_annual_taxable_income: float
    instalments_paid_to_date: float = 0.0
    quarter_number: int = 1

class QuarterlyEstimateRequest(BaseModel):
    estimated_annual_federal_income_tax: float
    estimated_annual_se_tax: float
    paid_to_date: float = 0.0
    quarter_number: int = 1


# ---------------------------------------------------------------------------
# Helpers — escalation chain integration
# ---------------------------------------------------------------------------

def _push_to_escalation(tax_result: dict, tenant_id: str, jurisdiction: str):
    """
    Push a completed tax analysis into the EscalationEngine (background task).
    engine.process() spawns a daemon thread and returns immediately — no asyncio needed.
    Imported lazily to avoid circular imports with main.py.
    """
    try:
        from api.escalation import EscalationEngine, EscalationStore, EscalationEmailer
        from adapters.accounting_adapter import get_adapter
        from agents.senior_accountant import SeniorAccountantAgent
        from agents.financial_controller import FinancialControllerAgent
        from agents.junior_accountant import JuniorAccountantAgent

        def junior_factory(tenant_id: str = "default", jurisdiction: str = "TZ"):
            return JuniorAccountantAgent(tenant_id=tenant_id, jurisdiction=jurisdiction)

        engine = EscalationEngine(
            senior_agent=SeniorAccountantAgent(),
            controller_agent=FinancialControllerAgent(),
            accounting_adapter=get_adapter(os.getenv("ACCOUNTING_SYSTEM", "mock")),
            emailer=EscalationEmailer(
                smtp_host=os.getenv("SMTP_HOST", ""),
                smtp_port=int(os.getenv("SMTP_PORT", "587")),
                smtp_user=os.getenv("SMTP_USER", ""),
                smtp_pass=os.getenv("SMTP_PASSWORD", ""),
                from_address=os.getenv("FROM_EMAIL", ""),
                operator_email=os.getenv("OPERATOR_EMAIL", ""),
            ),
            store=EscalationStore(),
            junior_agent_factory=junior_factory,
            auto_post_on_approval=True,
        )
        # process() spawns a daemon thread and returns immediately
        engine.process(
            junior_suggestion=tax_result,
            tenant_id=tenant_id,
            additional_context=f"Tax analysis for {jurisdiction}",
            online_research="",
        )
        logger.info("Tax result pushed to escalation engine for tenant=%s", tenant_id)
    except Exception as e:
        logger.error("Failed to push tax result to escalation: %s", e)


# ---------------------------------------------------------------------------
# Endpoints — Main Analysis
# ---------------------------------------------------------------------------

@router.post("/analyze")
async def tax_analyze(req: TaxAnalyzeRequest, background_tasks: BackgroundTasks):
    """
    Analyze raw financial data for tax compliance.
    Automatically routes to TZ or US agent based on jurisdiction.
    
    If send_to_escalation=True, the result is pushed into the Senior → Controller → Human chain.
    """
    orchestrator = get_tax_orchestrator()

    try:
        result = orchestrator.analyze(
            raw_input=req.raw_input,
            tenant_id=req.tenant_id,
            jurisdiction=req.jurisdiction,
            period=req.period,
            extra_context=req.extra_context,
            online_research_results=req.online_research,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Tax analysis error: %s", e)
        raise HTTPException(status_code=500, detail=f"Tax analysis failed: {e}")

    if req.send_to_escalation:
        background_tasks.add_task(_push_to_escalation, result, req.tenant_id, req.jurisdiction)
        result["escalation_queued"] = True

    return result


@router.post("/analyze/tz")
async def tax_analyze_tz(req: TaxAnalyzeTZRequest, background_tasks: BackgroundTasks):
    """Analyze raw data — Tanzania (TRA) tax compliance only."""
    agent = TaxAgentTZ()
    try:
        result = agent.analyze(
            raw_input=req.raw_input,
            tenant_id=req.tenant_id,
            period=req.period,
            extra_context=req.extra_context,
            online_research_results=req.online_research,
        )
    except Exception as e:
        logger.error("TZ tax analysis error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    if req.send_to_escalation:
        background_tasks.add_task(_push_to_escalation, result, req.tenant_id, "Tanzania")
        result["escalation_queued"] = True

    return result


@router.post("/analyze/us")
async def tax_analyze_us(req: TaxAnalyzeUSRequest, background_tasks: BackgroundTasks):
    """Analyze raw data — US LLC (IRS / pass-through) tax compliance only."""
    agent = TaxAgentUS()
    try:
        result = agent.analyze(
            raw_input=req.raw_input,
            tenant_id=req.tenant_id,
            period=req.period,
            extra_context=req.extra_context,
            online_research_results=req.online_research,
        )
    except Exception as e:
        logger.error("US tax analysis error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    if req.send_to_escalation:
        background_tasks.add_task(_push_to_escalation, result, req.tenant_id, "United States")
        result["escalation_queued"] = True

    return result


# ---------------------------------------------------------------------------
# Endpoints — Reference Data
# ---------------------------------------------------------------------------

@router.get("/rules/tz")
def get_tz_rules():
    """Return Tanzania tax rule constants used by the TZ agent."""
    return {
        "jurisdiction": "Tanzania",
        "regulator": "TRA (Tanzania Revenue Authority)",
        "standard": "IFRS",
        "rules": TZ_TAX_RULES,
    }


@router.get("/rules/us")
def get_us_rules():
    """Return US tax rule constants used by the US agent."""
    return {
        "jurisdiction": "United States",
        "regulator": "IRS",
        "standard": "US GAAP",
        "rules": US_TAX_RULES,
    }


# ---------------------------------------------------------------------------
# Endpoints — Quick Computation Helpers
# ---------------------------------------------------------------------------

@router.post("/compute/se-tax")
def compute_se_tax(req: SETaxRequest):
    """
    Compute US self-employment tax (IRC §1401).
    Shows the 92.35% step, SS wage base cap, Medicare, additional Medicare surtax.
    """
    agent = TaxAgentUS()
    return agent.compute_se_tax(req.net_llc_income)


@router.post("/compute/vat")
def compute_vat(req: VATReturnRequest):
    """
    Compute Tanzania VAT return — net payable or refundable.
    """
    agent = TaxAgentTZ()
    return agent.compute_vat_return(
        output_vat=req.output_vat,
        input_vat=req.input_vat,
        wht_vat_withheld=req.wht_vat_withheld,
        currency=req.currency,
    )


@router.post("/compute/amt")
def compute_amt(req: AMTRequest):
    """
    Compute Tanzania Alternative Minimum Tax (AMT).
    AMT = 1% of annual turnover, applies after 3+ consecutive loss years.
    """
    agent = TaxAgentTZ()
    return agent.compute_amt(req.annual_turnover, req.consecutive_loss_years)


@router.post("/compute/provisional")
def compute_provisional(req: ProvisionalTaxRequest):
    """
    Compute Tanzania provisional tax instalment for a given quarter.
    """
    agent = TaxAgentTZ()
    return agent.compute_provisional_tax(
        estimated_annual_taxable_income=req.estimated_annual_taxable_income,
        instalments_paid_to_date=req.instalments_paid_to_date,
        quarter_number=req.quarter_number,
    )


@router.post("/compute/quarterly")
def compute_quarterly(req: QuarterlyEstimateRequest):
    """
    Compute US quarterly estimated tax instalment (Form 1040-ES).
    """
    agent = TaxAgentUS()
    return agent.quarterly_estimate(
        estimated_annual_federal_income_tax=req.estimated_annual_federal_income_tax,
        estimated_annual_se_tax=req.estimated_annual_se_tax,
        paid_to_date=req.paid_to_date,
        quarter_number=req.quarter_number,
    )
