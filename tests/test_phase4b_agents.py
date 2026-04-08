"""
tests/test_phase4b_agents.py
Phase 4B — Treasury + Corporate Finance Agent Test Suite

Run:
    python tests/test_phase4b_agents.py

Each test sends a realistic raw data fixture to one agent and validates the response shape.
No live API key needed if ANTHROPIC_API_KEY is set in .env.
"""

import os
import sys
import json

# Make sure the project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ---------------------------------------------------------------------------
# Lazy imports — only load agents when API_KEY is available
# ---------------------------------------------------------------------------

def _get_treasury():
    from agents.treasury_agents import (
        CashFlowAnalystAgent,
        LiquidityManagerAgent,
        InvestmentStrategistAgent,
        TreasuryManagerAgent,
        CapitalMarketsAnalystAgent,
        HedgeFundManagerAgent,
        TREASURY_AGENT_DEFINITIONS,
    )
    return (CashFlowAnalystAgent, LiquidityManagerAgent, InvestmentStrategistAgent,
            TreasuryManagerAgent, CapitalMarketsAnalystAgent, HedgeFundManagerAgent,
            TREASURY_AGENT_DEFINITIONS)

def _get_corpfin():
    from agents.corp_finance_agents import (
        InvestmentBankerAgent,
        VPCapitalMarketsAgent,
        ValuationsAnalystAgent,
        CapitalBudgetingManagerAgent,
        CORP_FINANCE_AGENT_DEFINITIONS,
    )
    return (InvestmentBankerAgent, VPCapitalMarketsAgent, ValuationsAnalystAgent,
            CapitalBudgetingManagerAgent, CORP_FINANCE_AGENT_DEFINITIONS)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES = {

    # ── Treasury ─────────────────────────────────────────────────────────

    "cash_flow_13w": {
        "agent": "cash_flow",
        "analysis_type": "13week_forecast",
        "jurisdiction": "Tanzania",
        "period": "Q2-2025",
        "tenant_id": "tanzacorp_001",
        "raw_data": """
Opening cash balance: TZS 850,000,000
Weekly inflows (average): TZS 120,000,000 (export receivables USD 45,000 @ 2,650)
Weekly outflows (average): TZS 95,000,000 (payroll TZS 40M, suppliers TZS 35M, utilities TZS 20M)
Debt service: TZS 200,000,000 due in Week 6 (quarterly loan repayment, NMB Bank)
Covenant: minimum cash balance TZS 500,000,000 at all times (NMB facility covenant)
FX exposure: USD 180,000 receivable outstanding (3 invoices)
""",
    },

    "liquidity_lcr": {
        "agent": "liquidity",
        "analysis_type": "liquidity_coverage",
        "jurisdiction": "Tanzania",
        "period": "March-2025",
        "tenant_id": "tanzacorp_001",
        "raw_data": """
HQLA (High Quality Liquid Assets):
  - BoT Treasury Bills (91-day): TZS 300,000,000
  - NMB overnight deposits: TZS 150,000,000
  - DSE Government Bonds: TZS 200,000,000
  Total HQLA: TZS 650,000,000

30-day expected outflows:
  - Supplier payments: TZS 380,000,000
  - Loan repayment (NMB): TZS 200,000,000
  - Payroll: TZS 160,000,000
  - VAT payment (TRA, due 20th): TZS 54,000,000
  Total outflows: TZS 794,000,000

30-day expected inflows:
  - Customer receipts: TZS 420,000,000
  Capped inflows (75% max): TZS 315,000,000

Net stressed outflows: TZS 794,000,000 - TZS 315,000,000 = TZS 479,000,000
Intercompany loan to subsidiary: TZS 100,000,000 outstanding
""",
    },

    "investment_yield": {
        "agent": "investment",
        "analysis_type": "yield_optimisation",
        "jurisdiction": "Tanzania",
        "period": "Q1-2025",
        "tenant_id": "tanzacorp_001",
        "raw_data": """
Current short-term investment portfolio (TZS):
  - Call deposit at NMB: TZS 200,000,000 @ 6% p.a.
  - 91-day T-bill (BoT): TZS 150,000,000 @ 9.75% p.a.
  - CRDB call account: TZS 80,000,000 @ 5.5% p.a.

Cash available for additional investment: TZS 120,000,000 (horizon: 3-6 months)
Rating: NMB Bank — Fitch B+; CRDB Bank — Fitch B
Investment policy: no single counterparty > 30% of portfolio
ESG mandate: prefer green bonds / sustainability-linked instruments if available
""",
    },

    "treasury_fx": {
        "agent": "treasury",
        "analysis_type": "fx_hedging",
        "jurisdiction": "Tanzania",
        "period": "Q2-2025",
        "tenant_id": "tanzacorp_001",
        "raw_data": """
FX Exposure Summary:
  USD receivables: USD 350,000 (avg collection 60 days)
  USD payables: USD 120,000 (avg payment 30 days)
  Net USD long: USD 230,000

Revenue in USD: 35% of total revenue
Functional currency: TZS
Current spot rate: USD/TZS = 2,650 (sandbox estimate)
BoT forex retention requirement: exporters retain 70% in TZS

Existing hedges: None
Available instruments: NMB Bank FX forwards (USD/TZS, up to 90 days)
Interest rate exposure: TZS 500,000,000 floating rate facility @ TANLIBOR + 3.5% (reset quarterly)
""",
    },

    "capital_markets_covenant": {
        "agent": "capital_markets",
        "analysis_type": "covenant_review",
        "jurisdiction": "Tanzania",
        "period": "FY-2024",
        "tenant_id": "tanzacorp_001",
        "raw_data": """
NMB Term Loan — TZS 1,200,000,000 outstanding (5-year, drawn 2022)
Covenants:
  1. Net Debt / EBITDA ≤ 3.5x — actual: Net Debt TZS 1,050,000,000, EBITDA TZS 280,000,000
  2. Interest Coverage Ratio ≥ 3.0x — EBIT TZS 200,000,000, Interest TZS 84,000,000
  3. Minimum Net Worth ≥ TZS 800,000,000 — actual: TZS 920,000,000
  4. DSCR ≥ 1.2x — CFADS TZS 210,000,000, Debt Service TZS 185,000,000

DSE Bond: TZS 500,000,000, 7-year, coupon 12.5%, maturing 2027
Bank concentration: NMB 80% of all facilities
""",
    },

    "hedge_fund_portfolio": {
        "agent": "hedge_fund",
        "analysis_type": "portfolio_review",
        "jurisdiction": "United States",
        "period": "Q1-2025",
        "tenant_id": "usfamily_llc",
        "raw_data": """
Portfolio NAV: USD 2,500,000
Strategy: Multi-strategy (long/short equity 50%, macro 30%, event-driven 20%)

Holdings:
  - US equity long book: USD 1,800,000 (Level 1 — listed on NYSE)
  - US equity short book: USD -600,000 (Level 1)
  - S&P 500 put options (protective): USD 150,000 premium paid (Level 2)
    Strike: 5,200; Expiry: Jun 2025; Delta: -0.35; Vega: USD 8,500 per vol point
  - Private credit note: USD 200,000 (Level 3 — no market price, hold-to-maturity)
  - Gold futures (macro): USD 250,000 notional (Level 1)

Gross leverage: 2.4x NAV
Net exposure: 48% long
12-month return: +18.5% gross / +15.2% net (after 2/20 fees)
Benchmark (S&P 500 TR): +24.1%
Max drawdown (12m): -8.3%
Volatility (annualised): 14.2%
Prime broker: Goldman Sachs (100% of exposure — single PB)
""",
    },

    # ── Corporate Finance ─────────────────────────────────────────────────

    "ib_ma_advisory": {
        "agent": "investment_banker",
        "analysis_type": "ma_advisory",
        "jurisdiction": "Tanzania",
        "period": "2025",
        "tenant_id": "tanzacorp_001",
        "raw_data": """
Target: Simba Manufacturing Ltd (Tanzania) — private, unlisted
Revenue (LTM): TZS 4,200,000,000
EBITDA (LTM): TZS 630,000,000 (margin 15%)
Net Debt: TZS 800,000,000
Industry: Fast-moving consumer goods (FMCG) manufacturing

Acquiror: TanzaCorp Ltd — strategic buyer, same sector
Deal rationale: vertical integration (supply chain control), geographic expansion
Proposed structure: 100% cash acquisition
Indicative price discussed: TZS 5,500,000,000 (enterprise value)
Combined market share post-deal: ~38%
Tanzania FCC merger threshold: TZS 3,500,000,000 combined turnover (both parties exceed)
""",
    },

    "vp_cm_ipo": {
        "agent": "vp_capital_markets",
        "analysis_type": "ipo_readiness",
        "jurisdiction": "Tanzania",
        "period": "2025",
        "tenant_id": "tanzacorp_001",
        "raw_data": """
Company: TanzaCorp Ltd — manufacturing + distribution
Revenue (FY2024): TZS 8,500,000,000
EBITDA (FY2024): TZS 1,275,000,000 (15% margin)
Net Profit (FY2024): TZS 680,000,000
3-year audited accounts: Yes (KPMG Tanzania, clean opinion)
Board composition: 4 directors (CEO, CFO, 2 family members) — no independent directors
Audit committee: Not yet established
IFRS compliance: Yes (adopted 2022)
DSE listing interest: Main Investment Market (MIM) — minimum float 25%
Target raise: TZS 2,000,000,000 (primary, for expansion capex)
Existing shareholders: Family-owned (100%)
""",
    },

    "valuations_dcf": {
        "agent": "valuations",
        "analysis_type": "football_field",
        "jurisdiction": "Tanzania",
        "period": "FY-2024",
        "tenant_id": "tanzacorp_001",
        "raw_data": """
Subject: Simba Manufacturing Ltd (Tanzania)
Valuation Date: 31 March 2025
Revenue (LTM): TZS 4,200,000,000
EBITDA (LTM): TZS 630,000,000
EBIT (LTM): TZS 430,000,000
Net Income (LTM): TZS 250,000,000
Total Debt: TZS 800,000,000
Cash: TZS 120,000,000
Capex (LTM): TZS 180,000,000
D&A: TZS 200,000,000
NWC change: TZS -50,000,000
Tax rate: 30%
Growth assumptions (Years 1-3): 12% revenue CAGR
Growth assumptions (Years 4-5): 8%
Terminal growth: 3.5%
Industry: FMCG manufacturing, Tanzania
""",
    },

    "capex_appraisal": {
        "agent": "capital_budgeting",
        "analysis_type": "capex_appraisal",
        "jurisdiction": "Tanzania",
        "period": "2025",
        "tenant_id": "tanzacorp_001",
        "raw_data": """
Project A — New production line (Dar es Salaam plant):
  Initial investment: TZS 1,200,000,000
  Expected annual incremental EBITDA: TZS 300,000,000
  Project life: 8 years
  Asset class: Industrial machinery (Class 1 — TRA 37.5% diminishing balance)
  Terminal value: TZS 100,000,000

Project B — Warehouse in Arusha (lease vs buy):
  Purchase price: TZS 800,000,000 (Class 4 building — TRA 5%)
  Alternatively: Lease at TZS 80,000,000/year for 10 years
  Annual savings from ownership (vs leasing): TZS 15,000,000 p.a.

Project C — ERP system upgrade:
  Initial investment: TZS 350,000,000
  Expected annual savings: TZS 120,000,000
  Project life: 5 years
  Asset class: Computer equipment (Class 1 — TRA 37.5%)

WACC (sandbox estimate): 14.5%
Capital budget available: TZS 1,500,000,000
""",
    },
}


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def run_test(name: str, fixture: dict, agent_factory) -> dict:
    """
    agent_factory is a zero-argument callable — it already has the fixture baked in.
    Call it with no arguments; it returns the result dict directly.
    """
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"Agent: {fixture['agent']} | Type: {fixture['analysis_type']}")
    print(f"Jurisdiction: {fixture['jurisdiction']} | Tenant: {fixture['tenant_id']}")
    print("-" * 60)

    try:
        result = agent_factory()   # zero-arg — fixture already captured in lambda

        # Validate basic shape
        assert isinstance(result, dict), "Result must be a dict"
        assert "agent" in result or "error" not in result, f"Agent error: {result.get('error')}"

        flags = result.get("flags", [])
        suggestions = result.get("suggestions", [])

        print(f"✅ PASS — flags: {len(flags)}, suggestions: {len(suggestions)}")
        if flags:
            print(f"   ⚑  Top flag: {flags[0]}")
        if suggestions:
            print(f"   💡 Top suggestion: {str(suggestions[0])[:120]}")

        return {"status": "PASS", "name": name}

    except AssertionError as e:
        print(f"❌ FAIL — assertion: {e}")
        return {"status": "FAIL", "name": name, "error": str(e)}
    except Exception as e:
        print(f"❌ ERROR — {type(e).__name__}: {e}")
        return {"status": "ERROR", "name": name, "error": str(e)}


def main():
    if not API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    (CashFlowAnalystAgent, LiquidityManagerAgent, InvestmentStrategistAgent,
     TreasuryManagerAgent, CapitalMarketsAnalystAgent, HedgeFundManagerAgent,
     TREASURY_DEFS) = _get_treasury()

    (InvestmentBankerAgent, VPCapitalMarketsAgent, ValuationsAnalystAgent,
     CapitalBudgetingManagerAgent, CORPFIN_DEFS) = _get_corpfin()

    # Map agent_type → factory lambda
    agent_map = {
        "cash_flow":          lambda f: CashFlowAnalystAgent(API_KEY).analyze(**_kwargs(f)),
        "liquidity":          lambda f: LiquidityManagerAgent(API_KEY).analyze(**_kwargs(f)),
        "investment":         lambda f: InvestmentStrategistAgent(API_KEY).analyze(**_kwargs(f)),
        "treasury":           lambda f: TreasuryManagerAgent(API_KEY).analyze(**_kwargs(f)),
        "capital_markets":    lambda f: CapitalMarketsAnalystAgent(API_KEY).analyze(**_kwargs(f)),
        "hedge_fund":         lambda f: HedgeFundManagerAgent(API_KEY).analyze(**_kwargs(f)),
        "investment_banker":  lambda f: InvestmentBankerAgent(API_KEY).analyze(**_kwargs(f)),
        "vp_capital_markets": lambda f: VPCapitalMarketsAgent(API_KEY).analyze(**_kwargs(f)),
        "valuations":         lambda f: ValuationsAnalystAgent(API_KEY).analyze(**_kwargs(f)),
        "capital_budgeting":  lambda f: CapitalBudgetingManagerAgent(API_KEY).analyze(**_kwargs(f)),
    }

    results = []
    for test_name, fixture in FIXTURES.items():
        factory_fn = agent_map[fixture["agent"]]
        res = run_test(test_name, fixture, lambda f=fixture: factory_fn(f))
        results.append(res)

    # Summary
    passed  = sum(1 for r in results if r["status"] == "PASS")
    failed  = sum(1 for r in results if r["status"] == "FAIL")
    errored = sum(1 for r in results if r["status"] == "ERROR")

    print(f"\n{'='*60}")
    print(f"PHASE 4B TEST SUMMARY — {len(results)} tests")
    print(f"  ✅ PASS:  {passed}")
    print(f"  ❌ FAIL:  {failed}")
    print(f"  ⚠️  ERROR: {errored}")
    print("=" * 60)

    if failed + errored > 0:
        sys.exit(1)


def _kwargs(fixture: dict) -> dict:
    return {
        "raw_data":      fixture["raw_data"],
        "period":        fixture["period"],
        "tenant_id":     fixture["tenant_id"],
        "jurisdiction":  fixture["jurisdiction"],
        "analysis_type": fixture["analysis_type"],
        "enable_research": False,
    }


if __name__ == "__main__":
    main()
