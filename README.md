# Finance & Accounting AI Ecosystem

**Multi-agent, AI-powered finance & accounting system — Sessions 1–13 Complete | v5.4.0**

> Agents suggest. Humans decide. Nothing posts without approval.

---

## Overview

An automated Finance & Accounting ecosystem built on a multi-agent architecture. Each agent represents a real finance/accounting role, equipped with professional qualifications (ACCA, CIMA, CFA, CPA, CIA, CFE). Agents collaborate, escalate to each other, and surface structured suggestions to a human operator — but **never make final decisions autonomously**.

Data enters via email, API webhooks, file uploads, or raw text paste. The system digests it as-is, routes it to the right agent(s), and presents a suggestion card in the dashboard for human review and approval.

---

## Architecture

| Decision | Choice |
|---|---|
| Backend | Python (FastAPI) |
| Agent LLM | Claude API (Haiku / Sonnet / Opus) |
| Offline DB | SQLite (auto-syncs to Postgres when online) |
| Accounting systems | QuickBooks, Fishbowl, BILL.com (adapter pattern — swap to Xero/Odoo without rebuilding) |
| Human interface | Web dashboard (`dashboard/index.html`) — 10 tabs |
| Routing | Phase4Orchestrator (Haiku L1 classifies → Sonnet L2 processes) |
| Tax PDF export | Auto-generated on every tax analysis → saved to `reports/` |
| Post-approval | Approved journal entries auto-posted to accounting system via adapter |
| Offline/online | Runs fully on SQLite; auto-syncs to Postgres on reconnection |

---

## The 25+ Agent Roles (6 Departments)

### Accounting
| Agent | Status |
|---|---|
| Junior Accountant | ✅ Phase 1 |
| Senior Accountant | ✅ Phase 2 |
| Financial Controller | ✅ Phase 2 |
| Revenue Accountant | ✅ Session 10 |
| Cost Accountant | ✅ Session 10 |
| Accounting Manager | ✅ Session 10 |
| Tax Accountant | ✅ Session 12 |

### FP&A
| Agent | Status |
|---|---|
| FP&A Analyst | ✅ Phase 4A |
| FP&A Manager | ✅ Phase 4A |
| Senior FP&A Manager | ✅ Phase 4A |
| VP of Finance | ✅ Phase 4A |
| Data Analyst | ✅ Phase 4A |

### Tax
| Agent | Status |
|---|---|
| Tax Specialist (TZ) | ✅ Phase 3 |
| Tax Specialist (US) | ✅ Phase 3 |
| Tax Compliance Specialist | ✅ Phase 3 |
| Tax Supervisor | ✅ Session 12 |
| Tax Strategy Manager | ✅ Session 13 |

### Auditing
| Agent | Status |
|---|---|
| Compliance Auditor | ✅ Phase 4A |
| Audit Manager | ✅ Phase 4A |
| Quality Assurance Auditor | ✅ Phase 4A |
| Forensic Auditor | ✅ Phase 4A |

### Treasury
| Agent | Status |
|---|---|
| Cash Flow Analyst | ✅ Phase 4B |
| Liquidity Manager | ✅ Phase 4B |
| Investment Strategist | ✅ Phase 4B |
| Treasury Manager | ✅ Phase 4B |
| Capital Markets Analyst | ✅ Phase 4B |
| Hedge Fund Manager | ✅ Phase 4B |

### Corporate Finance
| Agent | Status |
|---|---|
| Investment Banker | ✅ Phase 4B |
| VP of Capital Markets | ✅ Phase 4B |
| Valuations Analyst | ✅ Phase 4B |
| Capital Budgeting Manager | ✅ Phase 4B |

---

## Agent Principles

1. **No final decisions** — agents produce structured suggestions only
2. **Human approval required** before any action is committed or posted
3. **Inter-agent escalation** — Junior → Senior → Controller → Human, with async retry loops (max 2 retries each)
4. **Online research capability** — agents look up current regulations, software docs, and tax law
5. **System-agnostic** — adapter pattern means any accounting system can be swapped in
6. **Raw data ingestion** — agents parse and interpret unstructured data as-is
7. **Qualifications embedded** — ACCA, CIMA, CFA, CPA, EA, CIA, CFE knowledge baked into system prompts
8. **Auto-correct** — geographic, mathematical, and formatting errors corrected and flagged as CRITICAL
9. **Auto PDF export** — every tax analysis automatically generates a professional PDF report
10. **Human resubmit** — rejected suggestions can be resubmitted with operator context injected

---

## Data Ingestion Sources

| Endpoint | Input Type |
|---|---|
| `POST /ingest/text` | Raw text paste (invoice, data, notes) |
| `POST /ingest/email` | Raw email (string or dict) |
| `POST /ingest/upload` | File upload (PDF, CSV, Excel, JSON, TXT) |
| `POST /ingest/webhook/{system}` | QuickBooks, Fishbowl, BILL.com, Stripe, Xero, Odoo |
| `POST /tax/analyze` | Direct tax input — routes by jurisdiction (TZ / US) |
| `POST /fpa/analyze` | Direct FP&A input — routes by agent type |
| `POST /audit/analyze` | Direct audit input — routes by agent type |
| `POST /treasury/analyze` | Direct treasury input — routes by agent type |
| `POST /corpfin/analyze` | Direct corp finance input — routes by agent type |
| `POST /accounting/analyze` | Cost, Revenue, Accounting Manager — CRITICAL flags auto-escalate |
| `POST /analyze` | **Universal** — auto-routes to correct dept + agent |

All raw data is digested as-is. `DataIngestor` handles PDF extraction, OCR fallback (Stripe PDFs), CSV/Excel parsing, and webhook normalisation internally.

---

## API Reference (v5.2.0 — 51 routes)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Dashboard |
| GET | `/health` | Online/offline status |
| POST | `/ingest/text` | Process raw text |
| POST | `/ingest/email` | Process email |
| POST | `/ingest/upload` | Upload file |
| POST | `/ingest/webhook/{system}` | System webhook |
| GET | `/suggestions/{tenant_id}` | List suggestions |
| GET | `/suggestions/{tenant_id}/{id}` | Get suggestion |
| POST | `/suggestions/{tenant_id}/{id}/decide` | Approve / Reject / Escalate |
| GET | `/stats/{tenant_id}` | Dashboard stats |
| POST | `/sync` | Manual Postgres sync |
| POST | `/tax/analyze` | Tax analysis (TZ / US) |
| POST | `/tax/analyze/supervised` | Tax analysis + automatic supervisor review |
| POST | `/tax/supervise` | Supervisor review of an existing tax analysis |
| GET | `/tax/accounting/agents` | List Tax Accountant analysis types |
| POST | `/tax/accounting/analyze` | Tax Accountant — deferred tax, provisions, reconciliations |
| GET | `/tax/strategy/agents` | List Tax Strategy analysis types |
| POST | `/tax/strategy/analyze` | Tax Strategy Manager — planning, structuring, risk register |
| POST | `/fpa/analyze` | FP&A analysis |
| POST | `/audit/analyze` | Audit analysis |
| POST | `/treasury/analyze` | Treasury analysis |
| POST | `/corpfin/analyze` | Corporate finance analysis |
| POST | `/accounting/analyze` | Accounting specialists |
| POST | `/analyze` | Universal router |
| GET | `/escalations` | List escalations |
| POST | `/escalations/{id}/approve` | Human approval |
| GET | `/market/rates` | Live FX + US rates |
| GET | `/market/fx/{from}/{to}` | Single FX rate lookup |
| GET | `/tenants` | List tenants |
| POST | `/tenants` | Create tenant |

---

## Quick Start

### 1. Install dependencies
```bash
cd finops
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env — add your Anthropic API key and SMTP settings
```

### 3. Start the server
```bash
uvicorn api.main:app --reload --port 8000
```

### 4. Open the dashboard
Navigate to `http://localhost:8000` — 10 tabs covering all departments, escalations, market data, and tenant management.

---

## Offline Mode

The system runs fully on SQLite when offline. On reconnection:
- Auto-syncs to Postgres on startup
- Background sync runs after every decision
- Manual trigger: `POST /sync`

---

## Jurisdictions & Standards

### Tanzania (Primary)
- **Standard:** IFRS (IAS 1/2/7/8/10/12/16/38, IFRS 9/15/16)
- **Tax:** TRA — 30% CIT, 18% VAT (Mainland), 1% AMT, Finance Act 2025 VAT withholding
- **WHT:** 5% dividends (resident), 10% (non-resident), 15% interest/royalties/imported services
- **Audit:** ISA as adopted by NBAA Tanzania

### United States (Family-Owned LLC)
- **Standard:** US GAAP
- **Tax:** IRS — LLC pass-through, 15.3% SE tax, QBI deduction (IRC §199A), quarterly estimated taxes
- **Forensic/AML:** FCPA, Bank Secrecy Act, FinCEN SAR reporting

---

## Cost Strategy

| Model | Used For | Cost (per 1M tokens in/out) |
|---|---|---|
| Haiku 4.5 | Routing, classification | $1 / $5 |
| Sonnet 4.5/4.6 | Core accounting, tax, FP&A, audit | $3 / $15 |
| Opus 4.6 | Complex audit, valuations, tax strategy | $15 / $75 |

Cost optimisations: prompt caching (~90% savings on repeated context), Batch API (50% discount for non-real-time tasks), 70/20/10 Haiku/Sonnet/Opus split.

---

## Extending the System

```python
# Add a new accounting system — adapters/accounting_adapter.py
class XeroAdapter(AccountingAdapter):
    def push_journal_entry(self, entry: JournalEntry) -> dict:
        # Call Xero API here
        ...
    def get_chart_of_accounts(self): ...
    def get_vendor(self, vendor_id: str): ...
```
Register it in `get_adapter()` — no other changes needed anywhere.

---

## Project Roadmap

| Phase | Status | Description |
|---|---|---|
| 1 | ✅ Complete | Junior Accountant + Dashboard + Ingestion + SQLite |
| 2 | ✅ Complete | Senior Accountant + Financial Controller + Escalation engine |
| 3 | ✅ Complete | Tanzania Tax Agent + US Tax Agent + PDF export |
| 4A | ✅ Complete | FP&A (5 agents) + Audit (4 agents) |
| 4B | ✅ Complete | Treasury (6 agents) + Corporate Finance (4 agents) |
| 4C | ✅ Complete | Universal Phase4Orchestrator (L1/L2 routing) |
| Session 10 | ✅ Complete | Cost Accountant, Revenue Accountant, Accounting Manager + Market Data |
| Session 11 | ✅ Complete | Bug fix pass — absolute DB paths, timezone-aware datetimes, request body limits, stats tenant filter, O(1) suggestion lookup |
| Session 12 | ✅ Complete | Tax Supervisor (ATAX/CPA(T)/EA), Tax Accountant (IAS 12/ASC 740), RBAC documented + activated |
| Session 13 | ✅ Complete | Tax Strategy Manager (CTA/LLM Tax), Phase 4D escalation wiring for FP&A, Audit, Treasury & Corp Finance |
| Next | ⬜ Planned | Dashboard Session 13 tab updates, Phase 4D escalation chain deep review |
| Long-term | ⬜ Planned | Self-hosted open-source LLM (Claude API abstracted behind interface) |
