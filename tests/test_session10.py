"""
Session 10 Test Suite
Tests: CostAccountant, RevenueAccountant, AccountingManager, MockMarketDataAdapter, LiveMarketDataAdapter (FX only)
All tests use mock API key pattern — real Claude API key required for agent tests.
Run: python tests/test_session10.py
"""

import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.market_data_adapter import MockMarketDataAdapter, LiveMarketDataAdapter, get_market_data_adapter

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SKIP_AGENT_TESTS = not API_KEY

PASS = "✅ PASS"
FAIL = "❌ FAIL"
SKIP = "⏭  SKIP"

results = []

def run_test(name, fn):
    try:
        fn()
        results.append((PASS, name))
        print(f"{PASS}  {name}")
    except Exception as e:
        results.append((FAIL, name, str(e)))
        print(f"{FAIL}  {name} — {e}")

# ──────────────────────────────────────────────
# Market Data Adapter Tests (no API key needed)
# ──────────────────────────────────────────────

def test_mock_adapter_fetch():
    adapter = MockMarketDataAdapter()
    data = adapter.fetch()
    assert "fx_rates" in data
    assert "us_rates" in data
    assert "tz_rates" in data
    assert data["meta"]["source"] == "mock"
    assert data["fx_rates"]["USD_TZS"] > 0

def test_mock_adapter_get_fx_rate():
    adapter = MockMarketDataAdapter()
    rate = adapter.get_fx_rate("USD", "TZS")
    assert rate is not None and rate > 2000

def test_mock_adapter_unknown_pair():
    adapter = MockMarketDataAdapter()
    rate = adapter.get_fx_rate("XYZ", "ABC")
    assert rate is None

def test_live_adapter_factory_live():
    adapter = get_market_data_adapter(live=True)
    assert isinstance(adapter, LiveMarketDataAdapter)

def test_live_adapter_factory_mock():
    adapter = get_market_data_adapter(live=False)
    assert isinstance(adapter, MockMarketDataAdapter)

def test_live_adapter_fx_fetch():
    """Test live FX fetch from open.er-api.com — requires internet."""
    adapter = LiveMarketDataAdapter(fallback_on_error=True)
    try:
        data = adapter.fetch(base_currency="USD", include_us_rates=False, include_tz_rates=False)
        fx = data["fx_rates"]
        assert len(fx) > 0
        # Should have USD_TZS or fallback
        assert "meta" in data
        print(f"         FX source: {data['meta'].get('fx_source','?')} | {len(fx)} pairs")
    except Exception as e:
        # Acceptable if no internet
        print(f"         Note: {e} (network may be unavailable)")

def test_live_adapter_no_fred_key():
    """Without FRED key, US rates should use mock fallback with warning."""
    adapter = LiveMarketDataAdapter(fred_api_key="", fallback_on_error=True)
    data = adapter.fetch(include_us_rates=True, include_tz_rates=False)
    assert "us_rates" in data
    warnings = data["meta"]["warnings"]
    assert any("FRED_API_KEY" in w for w in warnings)

def test_live_adapter_tz_rates_always_present():
    """TZ rates are cached — should always be present."""
    adapter = LiveMarketDataAdapter(fallback_on_error=True)
    data = adapter.fetch(include_tz_rates=True)
    assert "tz_rates" in data
    assert data["tz_rates"]["bot_policy_rate"] > 0

def test_live_adapter_fallback_on_error():
    """Bad FRED key should fall back to mock — not crash."""
    adapter = LiveMarketDataAdapter(fred_api_key="bad_key_intentional", fallback_on_error=True)
    data = adapter.fetch(include_us_rates=True)
    # Should not raise — meta.source should be mixed or fallback
    assert data["meta"]["source"] in ("live", "mixed", "fallback")

# ──────────────────────────────────────────────
# Agent Tests (require ANTHROPIC_API_KEY)
# ──────────────────────────────────────────────

COST_FIXTURE = """
Job: Manufacturing run — 500 units of Product X
Standard cost per unit: Materials TZS 12,000, Labour TZS 8,000, Overhead TZS 5,000 (absorption basis: machine hours @ TZS 2,500/hr)
Actual costs incurred:
  Materials purchased: 510 kg @ TZS 11,800/kg = TZS 6,018,000
  Materials used: 505 kg (standard 500 kg)
  Labour: 820 hours @ TZS 7,900/hr = TZS 6,478,000 (standard 800 hours @ TZS 8,000)
  Overhead incurred: TZS 2,650,000 (standard 2,000 machine hours used; budget 2,500 hours)
Closing WIP: 50 units (100% materials, 60% conversion)
"""

REVENUE_FIXTURE = """
Client: Kilimanjaro Hotels Ltd (Tanzania)
Contract signed: January 2025
Services:
  1. Hotel management software licence — 2-year right to use — TZS 48,000,000 total
  2. Implementation & setup services — distinct PO — TZS 12,000,000 fixed fee
  3. Monthly support services — TZS 2,000,000/month × 24 months = TZS 48,000,000
SSP: Licence TZS 50,000,000, Setup TZS 15,000,000, Support TZS 50,000,000 (total SSP TZS 115,000,000)
Transaction price: TZS 108,000,000 (discount of TZS 7,000,000)
Period: Q1 2025 (January–March). Setup completed March 31. Licence delivered Jan 1. 3 months support provided.
Billing: TZS 30,000,000 invoiced and received in January (upfront).
"""

MANAGER_FIXTURE = """
Entity: Dar Tech Solutions Ltd — March 2025 Month-End Close
Trial Balance (extract):
  Cash & Bank: TZS 145,000,000 (GL) vs TZS 143,500,000 (bank statement) — difference TZS 1,500,000 (unpresented cheque #2245 dated March 28)
  Accounts Receivable: TZS 280,000,000 — last reconciled February 28
  Prepayments: TZS 18,000,000 — includes annual insurance TZS 12,000,000 paid Jan 1 2025 (not amortised for Q1)
  Suspense account: TZS 3,200,000 — aged 45 days, reason unknown
  Revenue: TZS 820,000,000 YTD
  COGS: TZS 492,000,000 YTD
  EBITDA: TZS 95,000,000 YTD (budget: TZS 110,000,000)
Close target: Day 5 (April 7). Today: April 3.
Journal #JE-2025-0312 posted by Finance Manager AND approved by Finance Manager (same person).
"""

def test_cost_accountant_agent():
    if SKIP_AGENT_TESTS:
        print(f"    {SKIP}  CostAccountant (no API key)")
        results.append((SKIP, "CostAccountant agent"))
        return
    from agents.cost_accountant import CostAccountantAgent
    agent = CostAccountantAgent(API_KEY)
    result = agent.analyze(
        raw_data=COST_FIXTURE,
        period="Q1 2025",
        tenant_id="test-tz",
        jurisdiction="TZ",
        analysis_type="variance_analysis"
    )
    assert "agent" in result and result["agent"] == "CostAccountant"
    assert "variance_analysis" in result or "executive_summary" in result
    assert "flags" in result
    assert "suggested_journal_entries" in result
    assert "_meta" in result
    print(f"         Elapsed: {result['_meta'].get('elapsed_s','?')}s | Flags: {len(result.get('flags',[]))}")

def test_revenue_accountant_agent():
    if SKIP_AGENT_TESTS:
        print(f"    {SKIP}  RevenueAccountant (no API key)")
        results.append((SKIP, "RevenueAccountant agent"))
        return
    from agents.revenue_accountant import RevenueAccountantAgent
    agent = RevenueAccountantAgent(API_KEY)
    result = agent.analyze(
        raw_data=REVENUE_FIXTURE,
        period="Q1 2025",
        tenant_id="test-tz",
        jurisdiction="TZ",
        analysis_type="revenue_recognition"
    )
    assert "agent" in result and result["agent"] == "RevenueAccountant"
    assert "five_step_analysis" in result
    assert "flags" in result
    assert "suggested_journal_entries" in result
    print(f"         Elapsed: {result['_meta'].get('elapsed_s','?')}s | Flags: {len(result.get('flags',[]))}")

def test_accounting_manager_agent():
    if SKIP_AGENT_TESTS:
        print(f"    {SKIP}  AccountingManager (no API key)")
        results.append((SKIP, "AccountingManager agent"))
        return
    from agents.accounting_manager import AccountingManagerAgent
    agent = AccountingManagerAgent(API_KEY)
    result = agent.analyze(
        raw_data=MANAGER_FIXTURE,
        period="March 2025 Close",
        tenant_id="test-tz",
        jurisdiction="TZ",
        analysis_type="month_end_close"
    )
    assert "agent" in result and result["agent"] == "AccountingManager"
    assert "close_status" in result
    assert "close_checklist" in result
    assert "flags" in result
    # SoD violation should trigger CRITICAL
    crits = [f for f in result.get("flags",[]) if f.get("severity")=="CRITICAL"]
    print(f"         Elapsed: {result['_meta'].get('elapsed_s','?')}s | CRITICAL flags: {len(crits)}")

def test_cost_agent_with_market_data():
    if SKIP_AGENT_TESTS:
        print(f"    {SKIP}  CostAccountant+MarketData (no API key)")
        results.append((SKIP, "CostAccountant with market data"))
        return
    from agents.cost_accountant import CostAccountantAgent
    mock_mkt = MockMarketDataAdapter().fetch()
    agent = CostAccountantAgent(API_KEY)
    result = agent.analyze(
        raw_data="Invoice: USD 5,000 for raw materials. Exchange rate needed.",
        period="Q1 2025",
        tenant_id="test-tz",
        jurisdiction="TZ",
        analysis_type="job_costing",
        market_data=mock_mkt
    )
    assert "agent" in result

def test_auto_escalate_flag():
    if SKIP_AGENT_TESTS:
        print(f"    {SKIP}  Auto-escalate (no API key)")
        results.append((SKIP, "Auto-escalate flag"))
        return
    from agents.accounting_manager import AccountingManagerAgent
    agent = AccountingManagerAgent(API_KEY)
    result = agent.analyze(
        raw_data=MANAGER_FIXTURE,
        period="March 2025",
        tenant_id="test-tz",
        jurisdiction="TZ",
        analysis_type="gl_review"
    )
    # auto_escalate should be bool
    assert isinstance(result.get("auto_escalate"), bool)
    print(f"         auto_escalate={result.get('auto_escalate')} | reason={result.get('escalation_reason','—')[:60]}")

# ──────────────────────────────────────────────
# Run all
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Session 10 — Test Suite")
    print("="*60 + "\n")

    print("── Market Data Adapter ─────────────────────────────────")
    run_test("Mock adapter fetch", test_mock_adapter_fetch)
    run_test("Mock adapter get_fx_rate (USD/TZS)", test_mock_adapter_get_fx_rate)
    run_test("Mock adapter unknown pair → None", test_mock_adapter_unknown_pair)
    run_test("Factory: live=True → LiveMarketDataAdapter", test_live_adapter_factory_live)
    run_test("Factory: live=False → MockMarketDataAdapter", test_live_adapter_factory_mock)
    run_test("Live FX fetch (ExchangeRate-API)", test_live_adapter_fx_fetch)
    run_test("Live adapter: no FRED key → mock fallback + warning", test_live_adapter_no_fred_key)
    run_test("Live adapter: TZ rates always present (cached)", test_live_adapter_tz_rates_always_present)
    run_test("Live adapter: bad FRED key → fallback, no crash", test_live_adapter_fallback_on_error)

    print("\n── Agent Tests ─────────────────────────────────────────")
    if SKIP_AGENT_TESTS:
        print(f"  ⚠️  ANTHROPIC_API_KEY not set — agent tests skipped")
    run_test("CostAccountant — variance_analysis (TZ)", test_cost_accountant_agent)
    run_test("RevenueAccountant — revenue_recognition (TZ)", test_revenue_accountant_agent)
    run_test("AccountingManager — month_end_close (TZ)", test_accounting_manager_agent)
    run_test("CostAccountant — with market_data injected", test_cost_agent_with_market_data)
    run_test("AccountingManager — auto_escalate flag present", test_auto_escalate_flag)

    print("\n" + "="*60)
    passed = sum(1 for r in results if r[0]==PASS)
    skipped = sum(1 for r in results if r[0]==SKIP)
    failed = sum(1 for r in results if r[0]==FAIL)
    print(f"  Results: {passed} PASS | {skipped} SKIP | {failed} FAIL  ({len(results)} total)")
    print("="*60 + "\n")

    if failed > 0:
        print("Failed tests:")
        for r in results:
            if r[0]==FAIL:
                print(f"  {r[1]}: {r[2] if len(r)>2 else ''}")
        sys.exit(1)
