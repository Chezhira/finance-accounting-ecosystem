"""
FinOps Ecosystem — Windows Launcher
Phase 2: Junior → Senior → Controller → Human → Auto-Post

Usage:
    python run.py              # Start API server (default port 8000)
    python run.py --port 9000  # Custom port
    python run.py --demo       # Run a demo escalation chain
"""

import os
import sys
import argparse
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

# Ensure project root is on path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def start_server(port: int = 8000):
    """Start the FastAPI server."""
    import uvicorn
    print(f"""
╔══════════════════════════════════════════════════════╗
║       FinOps Ecosystem — Phase 2                     ║
║       Junior → Senior → Controller → Human           ║
╠══════════════════════════════════════════════════════╣
║  Dashboard : http://localhost:{port}                   ║
║  API Docs  : http://localhost:{port}/docs              ║
║  Health    : http://localhost:{port}/health            ║
╚══════════════════════════════════════════════════════╝
""")
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )


async def run_demo():
    """
    Demo: submit a raw transaction and run the full Phase 2 chain.
    Shows all three agent reviews in the console.
    """
    from agents.junior_accountant import JuniorAccountantAgent
    from agents.senior_accountant import SeniorAccountantAgent
    from agents.financial_controller import FinancialControllerAgent
    from api.escalation import EscalationEngine, EscalationEmailer, EscalationStore
    from adapters.accounting_adapter import get_adapter

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set. Add it to .env or environment.")
        sys.exit(1)

    print("\n🚀 FinOps Phase 2 Demo — Full Escalation Chain\n")

    # Sample raw transaction
    raw_transaction = {
        "vendor": "Microsoft Corporation",
        "description": "Microsoft Azure cloud subscription — October 2025",
        "amount": 1500.00,
        "currency": "USD",
        "invoice_date": "2025-10-01",
        "payment_terms": "Net 30",
        "category": "software/cloud services",
        "notes": "Imported digital service — reverse charge VAT applies"
    }
    tenant_id = "tz_demo"

    print("📄 Raw Transaction:")
    print(json.dumps(raw_transaction, indent=2))
    print("\n" + "─"*60)

    # Step 1: Junior
    print("\n⚙️  Step 1: Junior Accountant processing…")
    junior = JuniorAccountantAgent(tenant_id=tenant_id, jurisdiction="TZ")
    suggestion = junior.process(
        raw_input=json.dumps(raw_transaction, indent=2),
        source="demo",
        extra_context="",
    )
    print(f"   ✓ Decision: {suggestion.get('suggested_action', '?')}")
    print(f"   ✓ Confidence: {suggestion.get('confidence', '?')}")

    # Step 2: Senior
    print("\n⚙️  Step 2: Senior Accountant reviewing…")
    senior = SeniorAccountantAgent(api_key=api_key)
    sr = senior.review(suggestion, tenant_id)
    print(f"   ✓ Decision: {sr.get('decision', '?')}")
    print(f"   ✓ Arithmetic: {sr.get('journal_entry_review', {}).get('arithmetic_check', '?')}")

    # Step 3: Controller
    print("\n⚙️  Step 3: Financial Controller reviewing…")
    ctrl = FinancialControllerAgent(api_key=api_key)
    cr = ctrl.review(sr, suggestion, tenant_id)
    print(f"   ✓ Decision: {cr.get('decision', '?')}")
    print(f"\n📋 Controller Summary for Human Operator:")
    print(f"   {cr.get('human_operator_summary', '?')}")

    print("\n✅ Demo complete. In production, this would now appear in the dashboard for approval.")
    print("   Run 'python run.py' to start the server and use the full dashboard.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinOps Ecosystem Launcher")
    parser.add_argument("--port", type=int, default=8000, help="API server port")
    parser.add_argument("--demo", action="store_true", help="Run demo escalation chain")
    args = parser.parse_args()

    if args.demo:
        asyncio.run(run_demo())
    else:
        start_server(args.port)
