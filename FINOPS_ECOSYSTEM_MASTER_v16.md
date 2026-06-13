# Finance & Accounting AI Ecosystem — Master Reference
*Last updated: April 2026 | Sessions 1–10 Complete + Session 11 Bug Fix Pass ✅ | Server running ✅*

> **v16 changelog from v15:** Corrected Phase 3 agent API signatures (TaxAgentTZ/US/Orchestrator). Fixed
> EscalationStore.create() signature. Added Session 11 bug fix registry. Updated file structure
> (requirements.txt fixed, .gitignore added). All 29 route tests pass. See §12g for full diff.

---

## 1. PROJECT OVERVIEW

An automated, AI-powered Finance & Accounting ecosystem built on a multi-agent architecture. Each agent represents a real finance/accounting role, equipped with professional qualifications and skills. Agents collaborate, escalate to each other, and surface suggestions to a human operator — but never make final decisions autonomously.

---

## 2. ARCHITECTURE DECISIONS

| Decision | Choice | Rationale |
|---|---|---|
| Tenancy model | Multi-tenant, shared agent pool | Cost-efficient; data isolation at DB level |
| Backend | Python | User preference |
| Hosting | User's own server + website (F:\Finance_ecosystem) | No cloud hosting needed |
| Primary accounting system | QuickBooks | With Fishbowl + BILL.com integrations |
| System design | Adapter/agnostic pattern | So systems can be swapped (Xero, Odoo etc) without rebuilding |
| Offline mode | SQLite local DB | Syncs to Postgres main DB when connection restored |
| Agent communication | Async escalation engine with retry loops | Junior → Senior → Controller → Human → Auto-Post |
| Human interface | Phase 1 dashboard extended each phase | 10 tabs as of v5.1.0 |
| LLM provider | Claude API (start) | Plan to migrate to self-hosted LLM long-term |
| Agent online research | Yes | Can look up regulations, software docs, tax law changes |
| Post-approval action | Auto-post to accounting system | Push journal via adapter on human approval |
| Tax PDF export | Auto-generate on every tax analysis | Saved to reports/ folder; no manual trigger needed |
| FP&A + Audit + Treasury + Corp Finance routing | Direct — no escalation chain | Results shown immediately in tab; human reviews inline. Full escalation wiring planned Phase 4D. |
| Accounting Specialists routing | Direct + auto-escalate on CRITICAL | CostAccountant, RevenueAccountant, AccountingManager return results directly; CRITICAL flags auto-saved to escalation store |
| Universal routing | Phase4Orchestrator (Haiku L1 + Sonnet L2) | Auto-classifies department + agent from any raw input |
| RBAC | API key per role in .env | viewer / analyst / senior / admin — disabled by default (RBAC_ENABLED=false) |
| Market data | LiveMarketDataAdapter | ExchangeRate-API (FX, free) + FRED (US rates, free key) + BoT cached (TZ). MARKET_DATA_LIVE=true in .env |

---

## 3. THE 25+ ROLES (6 DEPARTMENTS)

### Accounting
- Junior Accountant ← ✅ PHASE 1 COMPLETE
- Senior Accountant ← ✅ PHASE 2 COMPLETE
- Revenue Accountant ← ✅ SESSION 10 COMPLETE
- Accounting Manager ← ✅ SESSION 10 COMPLETE
- Financial Controller ← ✅ PHASE 2 COMPLETE
- Cost Accountant ← ✅ SESSION 10 COMPLETE
- Tax Accountant

### FP&A
- FP&A Analyst ← ✅ PHASE 4A COMPLETE
- FP&A Manager ← ✅ PHASE 4A COMPLETE
- Senior FP&A Manager ← ✅ PHASE 4A COMPLETE
- VP of Finance ← ✅ PHASE 4A COMPLETE
- Data Analyst ← ✅ PHASE 4A COMPLETE

### Tax
- Tax Specialist ← ✅ PHASE 3 (TaxAgentTZ + TaxAgentUS)
- Tax Supervisor
- Tax Compliance Specialist ← ✅ PHASE 3
- Tax Strategy Manager

### Auditing
- Compliance Auditor ← ✅ PHASE 4A COMPLETE
- Audit Manager ← ✅ PHASE 4A COMPLETE
- Quality Assurance Auditor ← ✅ PHASE 4A COMPLETE
- Forensic Auditor ← ✅ PHASE 4A COMPLETE

### Treasury
- Cash Flow Analyst ← ✅ PHASE 4B COMPLETE
- Liquidity Manager ← ✅ PHASE 4B COMPLETE
- Investment Strategist ← ✅ PHASE 4B COMPLETE
- Treasury Manager ← ✅ PHASE 4B COMPLETE
- Capital Markets Analyst ← ✅ PHASE 4B COMPLETE
- Hedge Fund Manager ← ✅ PHASE 4B COMPLETE

### Corporate Finance
- Investment Banker ← ✅ PHASE 4B COMPLETE
- VP of Capital Markets ← ✅ PHASE 4B COMPLETE
- Valuations Analyst ← ✅ PHASE 4B COMPLETE
- Capital Budgeting Manager ← ✅ PHASE 4B COMPLETE

---

## 4. AGENT PRINCIPLES

1. **No final decisions** — agents produce suggestions only
2. **Human approval** required before any action is committed
3. **Inter-agent communication** — async escalation chain with retry loops
4. **Online research capability** — agents can look up current regulations, software docs, tax law
5. **System-agnostic** — agents learn new systems; adapters handle system-specific API calls
6. **Raw data ingestion** — agents parse and make sense of unstructured/raw data as-is
7. **Qualifications baked in** — ACCA, CIMA, CFA, FP&A, CPA, EA, CIA, CFE knowledge embedded in system prompts
8. **Auto-correct data errors** — geographic, mathematical, formatting errors corrected + flagged as CRITICAL
9. **Post-approval auto-posting** — approved suggestions pushed to accounting system via adapter
10. **Auto-retry** — RETURN_TO_JUNIOR re-runs Junior automatically; RETURN_TO_SENIOR re-runs Senior (max 2 retries each)
11. **Human resubmit** — rejected suggestions can be resubmitted from dashboard with operator context injected
12. **Auto PDF export** — every tax analysis automatically saves a professional PDF report to `reports/`
13. **Array caps on audit agents** — system prompts limit array sizes to prevent token truncation (e.g. max 8 findings, max 6 flags)

---

## 5. DATA INGESTION SOURCES

- **Email** — `/ingest/email`
- **API webhooks** (QuickBooks, Fishbowl, BILL.com) — `/ingest/webhook/{system}`
- **Direct file upload** (PDF, CSV, Excel, JSON) — `/ingest/upload`
- **Raw text** (paste invoice/data directly) — `/ingest/text`
- **Tax analysis** — `/tax/analyze` (direct tax input, routes by jurisdiction)
- **FP&A analysis** — `/fpa/analyze` (direct input, routes by agent_type)
- **Audit analysis** — `/audit/analyze` (direct input, routes by agent_type)
- **Treasury analysis** — `/treasury/analyze` (direct input, routes by agent_type)
- **Corp Finance analysis** — `/corpfin/analyze` (direct input, routes by agent_type)
- **Accounting Specialists** — `/accounting/analyze` (Cost, Revenue, Accounting Manager — direct + CRITICAL auto-escalate)
- **Universal** — `/analyze` (auto-routes to correct dept + agent via Phase4Orchestrator)
- **Market data** — `/market/rates` (live FX + US rates + TZ cached) | `/market/fx/{from}/{to}` (single rate lookup)

All raw data is ingested as-is and interpreted by the agent layer.

**⚠️ PDF UPLOAD RULE:** Pass raw bytes directly to `ingestor.from_file(content, filename)`. Never `.decode()` first — destroys PDF binary. `DataIngestor` handles `pdfplumber` extraction internally.

**⚠️ INGESTOR RETURNS DICT:** `DataIngestor` returns a dict, not a string. Always call `.get("text", "")` on the result.

**⚠️ STRIPE PDF LIMITATION:** Stripe-generated PDFs are image-rendered — OCR is applied automatically (Session 5). Confidence % returned in warnings.

---

## 6. JURISDICTIONS & STANDARDS

### Tanzania (Primary)
- **Accounting standard:** IFRS
- **Regulator:** TRA (Tanzania Revenue Authority)
- **Corporate tax:** 30% for resident companies
- **VAT:** 18% standard (Mainland), 16% B2C electronic, 15% Zanzibar
- **VAT registration threshold:** TZS 200,000,000/year
- **VAT returns:** Due 20th of following month
- **AMT:** 1% of turnover (companies with losses 3+ consecutive years)
- **Provisional tax:** Quarterly, due within 3 months of quarter end
- **Final tax returns:** Within 6 months of financial year end
- **Finance Act 2025:** VAT withholding agents — 3% goods, 6% services
- **Reverse charge VAT:** 18% self-assessed on imported digital/software services
- **WHT:** 5% dividends (resident), 10% (non-resident), 15% interest/royalties
- **WHT on imported services:** 15% per Section 83 Income Tax Act — deducted at payment, not accrual
- **Forensic/AML:** PCCB (Prevention and Combating of Corruption Bureau), AMLA 2006
- **Audit standard:** ISA as adopted by NBAA Tanzania

### United States (Family-Owned LLC)
- **Accounting standard:** US GAAP
- **Regulator:** IRS
- **LLC tax treatment:** Pass-through by default
- **Self-employment tax:** 15.3% on 92.35% of net SE income (SS 12.4% up to $184,500 + Medicare 2.9%)
- **Additional Medicare surtax:** 0.9% on income over $200,000
- **Quarterly estimated taxes:** Apr 15, Jun 15, Sep 15, Jan 15
- **SALT deduction cap:** $40,000 (2025, One Big Beautiful Bill Act)
- **QBI deduction:** 20% of qualified business income (IRC §199A)
- **SE tax deduction:** 50% of SE tax deductible from gross income
- **Key forms:** Schedule C, Form 1065 + K-1, Form 1040-ES, Form SE
- **Forensic/AML:** FCPA, Bank Secrecy Act (BSA), FinCEN SAR reporting

---

## 7. REFERENCE DOCUMENTS (Project Files)

| File | Purpose |
|---|---|
| `IFRS_in_your_pocket_2025.pdf` | Primary IFRS standards reference for TZ agents |
| `eyifrs29540261us01212026.pdf` | US GAAP vs IFRS comparison (EY, Jan 2026) |
| `Fishbowl_Documentation_Pack.pdf` | Fishbowl ERP integration reference |
| `Fishbowl_Setup_Implementation_Inventory_Warehouse_Guide.pdf` | Fishbowl setup guide |
| `TaxJar_Setup_and_Operations_Guide.pdf` | TaxJar integration (US sales tax) |
| `BILL_Setup_and_AP_Operations_Guide.pdf` | BILL.com AP operations reference |
| `Finance_Roles.gif` | Visual org chart of all 25+ roles |

---

## 8. CLAUDE API COST STRATEGY

| Model | Use Case | Cost (per 1M tokens in/out) |
|---|---|---|
| Haiku 4.5 | Routing, classification, tenant detection | $1 / $5 |
| Sonnet 4.5/4.6 | Core accounting, tax, FP&A, audit work | $3 / $15 |
| Opus 4.6 | Complex reasoning — audit, valuations, tax strategy | $15 / $75 |

**Cost optimizations:**
- Prompt caching: Agent system prompts cached → ~90% savings on repeated context
- Batch API: 50% discount for non-real-time tasks (nightly reconciliations, month-end)
- 70/20/10 split (Haiku/Sonnet/Opus) cuts costs significantly vs all-Sonnet
- Long-term: Migrate to self-hosted open-source LLM — Claude API abstracted behind interface

---

## 9. CRITICAL JOURNAL ENTRY RULES

**Rule 1:** Total debits MUST equal total credits. Always verify before output.

**Rule 2 — Reverse Charge VAT (imported services/digital):**
```
DR  Expense Account          [invoice amount]
DR  VAT Recoverable          [VAT amount]    ← self-assessed input
CR  VAT Payable              [VAT amount]    ← self-assessed output
CR  Accounts Payable         [invoice amount] ← ONLY invoice amount, NOT gross
Total DR = Total CR ✓
```

**Rule 3 — Standard VAT (vendor charges on invoice):**
```
DR  Expense Account          [net]
DR  VAT Recoverable          [VAT]
CR  Accounts Payable         [net + VAT = GROSS]
```

**Rule 4 — WHT on imported services (Tanzania):**
- 15% WHT per Section 83 Income Tax Act
- NOT deducted at accrual. Flagged as INFO. Separate entry at payment.
- Example: USD 10.00 invoice → WHT USD 1.50 → Net payment USD 8.50

**Rule 5 — Auto-correct errors:**
Geographic, mathematical, formatting errors corrected automatically. Flagged CRITICAL.

**Rule 6 — IAS 21 FX:**
Foreign currency AP recorded at invoice date rate. Revalue at month-end if unpaid.

**Rule 7 — SE Tax (US, IRC §1401):**
- Apply 92.35% factor FIRST, then 15.3% rate
- SE Net = Net LLC Income × 0.9235
- SS tax = min(SE Net, $184,500) × 12.4%
- Medicare = SE Net × 2.9%
- Additional Medicare = (Net LLC Income - $200,000) × 0.9% [if applicable]
- SE Tax Deduction = Total SE Tax × 50%

**Rule 8 — VAT Withholding Agent (Tanzania, Finance Act 2025):**
```
DR  Accounts Payable         [gross amount]
CR  VAT Withholding Payable  [3% goods / 6% services]
CR  Bank                     [net payment to supplier]
```

---

## 10. FILE STRUCTURE

```
F:\Finance_ecosystem\finops\
├── run.py
├── requirements.txt                ← ✅ Session 11 fix (was requirements.txt.txt)
├── README.md
├── .env                            ← Live config (never commit — in .gitignore)
├── .env.example                    ← Template (placeholder keys only)
├── .gitignore                      ← ✅ Session 11 — excludes .env, *.db, __pycache__
├── FINOPS_ECOSYSTEM_MASTER_v16.md  ← This file
├── finops_offline.db               ← Phase 1 SQLite (suggestions + tenants) — gitignored
├── finops_escalation.db            ← Phase 2 SQLite (escalation state machine) — gitignored
├── config\
│   └── tax_rates.json              ← ✅ Session 6 — versioned TZ + US tax constants (v2025.1)
├── reports\
│   ├── __init__.py
│   ├── tax_pdf_generator.py        ← ✅ Phase 3 — PDF generation engine
│   └── {tenant_id}_{jur}_{period}_{timestamp}.pdf  ← auto-generated, gitignored
├── agents\
│   ├── __init__.py
│   ├── junior_accountant.py        ← ✅ Phase 1
│   ├── senior_accountant.py        ← ✅ Phase 2
│   ├── financial_controller.py     ← ✅ Phase 2
│   ├── tax_agent_tz.py             ← ✅ Phase 3
│   ├── tax_agent_us.py             ← ✅ Phase 3
│   ├── tax_orchestrator.py         ← ✅ Phase 3
│   ├── fpa_agents.py               ← ✅ Phase 4A (5 agents)
│   ├── audit_agents.py             ← ✅ Phase 4A (4 agents)
│   ├── treasury_agents.py          ← ✅ Phase 4B (6 agents + TREASURY_AGENTS dict)
│   ├── corp_finance_agents.py      ← ✅ Phase 4B (4 agents + CORP_FINANCE_AGENTS dict)
│   ├── phase4_orchestrator.py      ← ✅ Phase 4C — universal L1/L2 routing engine
│   ├── cost_accountant.py          ← ✅ Session 10
│   ├── revenue_accountant.py       ← ✅ Session 10
│   └── accounting_manager.py       ← ✅ Session 10
├── api\
│   ├── __init__.py
│   ├── main.py                     ← ✅ v5.2.0 — 51 routes + Session 11 fixes
│   ├── escalation.py               ← ✅ v3.1 — column whitelist, timezone-aware datetimes
│   └── tax_routes.py               ← ✅ Session 11 fixed (escalation integration corrected)
│                                      Not mounted — routes live in main.py
├── adapters\
│   ├── __init__.py
│   ├── accounting_adapter.py       ← ✅ Phase 1
│   └── market_data_adapter.py      ← ✅ Session 10
├── db\
│   ├── __init__.py
│   └── store.py                    ← ✅ Session 11 — absolute DB path, stats() tenant filter
├── ingestion\
│   ├── __init__.py
│   └── ingestor.py                 ← ✅ Phase 5 v2 — OCR fallback (class: DataIngestor)
├── tests\
│   ├── test_phase4a_agents.py
│   ├── phase4a_raw_fixtures.txt
│   ├── test_phase4b_agents.py
│   ├── phase4b_raw_fixtures.txt
│   └── test_session10.py
└── dashboard\
    └── index.html                  ← ✅ v5.1.0 — 10 tabs
```

---

## 11. ⚠️ PHASE 1 CLASS & METHOD REGISTRY
*Always check this before writing any new code that imports Phase 1 modules.*

### db/store.py
| Item | Name |
|---|---|
| Main store class | `OfflineStore` |
| Sync class | `PostgresSyncManager` |
| `create_tenant()` | `(tenant_id, display_name, jurisdiction, accounting_standard, country, currency, notes)` ← uses `tenant_id` NOT `id` |
| `list_tenants()` | `()` → returns `list[dict]` — each dict has `id` as the tenant key |
| `get_suggestion()` | `(suggestion_id: str)` → `Optional[dict]` — O(1) indexed lookup ✅ Session 11 |
| `save_suggestion()` | `(suggestion: dict, tenant_id: str, jurisdiction: str)` |
| `list_suggestions()` | `(tenant_id: str, status: Optional[str], limit: int)` → returns `list[dict]` |
| `update_decision()` | `(suggestion_id: str, decision: str, decided_by: str, notes: str)` |
| `stats()` | `(tenant_id: str)` → `unsynced` count now filtered by `tenant_id` ✅ Session 11 |
| DB path | Absolute path via `Path(__file__).parent.parent` — safe from any launch directory ✅ Session 11 |

### ingestion/ingestor.py (v2.0.0 — Phase 5)
| Item | Name |
|---|---|
| Main class | `DataIngestor` ← NOT `FileIngestor` |
| Raw text | `DataIngestor.from_raw_text(text: str)` |
| File | `DataIngestor.from_file(content: bytes, filename: str)` ← raw bytes, not decoded string |
| Webhook | `DataIngestor.from_webhook(payload: dict, system: str)` |
| Email | `DataIngestor.from_email(raw_email: str or dict)` |
| Return type | Always `dict` with keys: `text, source_type, filename, metadata, ocr_used, ocr_page_count, ocr_confidence, char_count, warnings` |
| ⚠️ IMPORTANT | Always call `.get("text", "")` on result — it returns a dict, not a string |

### adapters/accounting_adapter.py
| Item | Name |
|---|---|
| Base class | `AccountingAdapter` (ABC) |
| Factory | `get_adapter(system: str)` ← NO api_key argument |
| Helpers | `JournalLine`, `JournalEntry` |
| Converter | `suggestion_to_journal_entry(suggestion: dict, tenant_id: str) -> JournalEntry` |

### agents/junior_accountant.py
| Item | Name |
|---|---|
| Class | `JuniorAccountantAgent` |
| `__init__()` | `(tenant_id: str, jurisdiction: str)` ← NO api_key |
| `process()` | `(raw_input: str, source: str, extra_context: str)` ← NO tenant_id in process() |
| Instantiation | Per-request only — never a global singleton |

### agents/senior_accountant.py
| Item | Name |
|---|---|
| Class | `SeniorAccountantAgent` |
| `__init__()` | `(api_key: Optional[str] = None)` |
| `review()` | `(junior_suggestion, tenant_id, additional_context, online_research_results)` |

### agents/financial_controller.py
| Item | Name |
|---|---|
| Class | `FinancialControllerAgent` |
| `__init__()` | `(api_key: Optional[str] = None)` |
| `review()` | `(senior_review, junior_suggestion, tenant_id, additional_context, online_research_results)` |

### api/escalation.py (v3.1 — Session 11)
| Item | Name |
|---|---|
| State enum | `EscalationState` |
| DB class | `EscalationStore` |
| `create()` | `(tenant_id: str, junior_suggestion: dict) -> str` — returns generated UUID. ⚠️ NO `id=` param, NO json.dumps() |
| `get()` | `(esc_id: str) -> Optional[dict]` |
| `update_state()` | `(esc_id, state, **kwargs)` — kwargs keys are whitelisted (column injection protection) ✅ Session 11 |
| Allowed kwargs | `senior_review, controller_review, reasoning_log, operator_notes, system_reference, junior_retry_count, senior_retry_count` |
| `append_reasoning()` | `(esc_id, stage, summary, detail)` |
| `list_all()` | `()` — no arguments. Filter tenant in caller |
| `list_pending_human()` | `()` |
| `list_rejected()` | `()` |
| ⚠️ NO `get_escalation_engine()` | Not exported from escalation.py — use `_get_escalation_engine()` factory in main.py |
| datetime | All timestamps use `datetime.now(timezone.utc)` — timezone-aware ✅ Session 11 |
| DB path | Absolute path via `Path(__file__).parent.parent` ✅ Session 11 |
| Email class | `EscalationEmailer(smtp_host, smtp_port, smtp_user, smtp_pass, from_address, operator_email)` |
| Engine class | `EscalationEngine` |
| `EscalationEngine.__init__()` | `(senior_agent, controller_agent, accounting_adapter, emailer, store, junior_agent_factory, auto_post_on_approval)` |
| `junior_agent_factory` | Must accept `(tenant_id: str = "default", jurisdiction: str = "TZ")` ✅ Session 11 |
| `process()` | `(junior_suggestion: dict, tenant_id: str, additional_context: str, online_research: str)` |
| `process_human_approval()` | `(escalation_id: str, approved: bool, operator_notes: str)` |
| `process_resubmit()` | `(escalation_id: str, operator_context: str, tenant_id: str)` |
| Max retries | `MAX_JUNIOR_RETRIES = 2`, `MAX_SENIOR_RETRIES = 2` |

### api/main.py (v5.2.0 — Session 11)
| Item | Detail |
|---|---|
| `esc_store` | Module-level `EscalationStore()` singleton — NOT instantiated per-request ✅ Session 11 |
| `_get_escalation_engine()` | Local factory — uses shared `esc_store` singleton |
| `_ROOT` | `Path(__file__).parent.parent` — used for all file paths ✅ Session 11 |
| `REPORTS_DIR` | `_ROOT / "reports"` — used throughout reports routes |
| Request body limits | `raw_data`, `raw_text`, `raw_email`: max 200,000 chars. `extra_context`, `notes`: max 10,000 chars ✅ Session 11 |
| `get_suggestion` route | Calls `store.get_suggestion(id)` directly — O(1), validates tenant_id ✅ Session 11 |

---

## 12a. ⚠️ PHASE 3 ADDITIONS REGISTRY

### agents/tax_agent_tz.py
| Item | Name |
|---|---|
| Class | `TaxAgentTZ` ← NOT `TanzaniaTaxAgent` |
| `__init__()` | `()` ← NO api_key — reads `ANTHROPIC_API_KEY` from env ✅ Session 11 |
| `analyze()` | `(raw_input, tenant_id, period, extra_context, online_research_results)` ✅ Session 11 |
| Constants | `TZ_TAX_RULES` dict — import directly: `from agents.tax_agent_tz import TaxAgentTZ, TZ_TAX_RULES` |
| ⚠️ Was wrong in v15 | `__init__(api_key)` and `analyze(raw_data, ..., enable_research)` — both corrected |

### agents/tax_agent_us.py
| Item | Name |
|---|---|
| Class | `TaxAgentUS` ← NOT `USTaxAgent` |
| `__init__()` | `()` ← NO api_key — reads `ANTHROPIC_API_KEY` from env ✅ Session 11 |
| `analyze()` | `(raw_input, tenant_id, period, extra_context, online_research_results)` ✅ Session 11 |
| Constants | `US_TAX_RULES` dict — import directly: `from agents.tax_agent_us import TaxAgentUS, US_TAX_RULES` |

### agents/tax_orchestrator.py
| Item | Name |
|---|---|
| Class | `TaxOrchestrator` |
| `__init__()` | `()` ← NO api_key ✅ Session 11 |
| `analyze()` | `(raw_input, tenant_id, jurisdiction, period, extra_context, online_research_results)` ✅ Session 11 |
| Singleton | `get_tax_orchestrator()` — use this instead of instantiating directly |
| ⚠️ Was wrong in v15 | `__init__(api_key)` and `analyze(raw_data, ..., enable_research)` — both corrected |

---

## 12b. ⚠️ PHASE 4A ADDITIONS REGISTRY

*(Unchanged from v15)*

### agents/fpa_agents.py (Session 7)
**⚠️ NO registry dicts exported** — `FPA_AGENTS` and `FPA_AGENT_DEFINITIONS` are defined in `api/main.py`

| Class | `__init__()` | Primary Method |
|---|---|---|
| `FPAAnalystAgent` | `(api_key: str)` | `analyze(raw_data, period, tenant_id, jurisdiction, analysis_type, extra_context, enable_research)` |
| `FPAManagerAgent` | `(api_key: str)` | `analyze(raw_data, period, tenant_id, jurisdiction, model_type, analyst_output, extra_context, enable_research)` |
| `SeniorFPAManagerAgent` | `(api_key: str)` | `analyze(raw_data, period, tenant_id, jurisdiction, output_type, manager_output, extra_context, enable_research)` |
| `VPFinanceAgent` | `(api_key: str)` | `analyze(raw_data, period, tenant_id, jurisdiction, output_type, senior_fpa_output, extra_context, enable_research)` |
| `DataAnalystAgent` | `(api_key: str)` | `analyze(raw_data, period, tenant_id, analysis_type, extra_context, enable_research)` |

**All FP&A agents:** `max_tokens = 16000` | `model = claude-sonnet-4-5`

### agents/audit_agents.py (Session 7)
**⚠️ NO registry dicts exported** — defined in `api/main.py`

| Class | `__init__()` | Primary Method |
|---|---|---|
| `ComplianceAuditorAgent` | `(api_key: str)` | `audit(raw_data, audit_period, tenant_id, jurisdiction, audit_scope, extra_context, enable_research)` |
| `AuditManagerAgent` | `(api_key: str)` | `audit(raw_data, audit_period, tenant_id, jurisdiction, audit_type, extra_context, enable_research)` |
| `QAAuditorAgent` | `(api_key: str)` | `audit(raw_data, review_period, tenant_id, jurisdiction, review_type, extra_context, enable_research)` |
| `ForensicAuditorAgent` | `(api_key: str)` | `investigate(raw_data, investigation_period, tenant_id, jurisdiction, investigation_type, extra_context, enable_research)` |

---

## 12c. ⚠️ PHASE 4B ADDITIONS REGISTRY (Session 8)

*(Unchanged from v15)*

### agents/treasury_agents.py
**✅ Exports `TREASURY_AGENTS` dict and `TREASURY_AGENT_DEFINITIONS` list**

| Class | agent_type key | `__init__()` |
|---|---|---|
| `CashFlowAnalystAgent` | `cash_flow` | `(api_key: str)` |
| `LiquidityManagerAgent` | `liquidity` | `(api_key: str)` |
| `InvestmentStrategistAgent` | `investment` | `(api_key: str)` |
| `TreasuryManagerAgent` | `treasury` | `(api_key: str)` |
| `CapitalMarketsAnalystAgent` | `capital_markets` | `(api_key: str)` |
| `HedgeFundManagerAgent` | `hedge_fund` | `(api_key: str)` |

**⚠️ `TREASURY_AGENT_DEFINITIONS` uses key `class` not `display_name`** — health endpoint uses `.get("display_name") or .get("class")` ✅ Session 11

### agents/corp_finance_agents.py
**✅ Exports `CORP_FINANCE_AGENTS` dict and `CORP_FINANCE_AGENT_DEFINITIONS` list**

| Class | agent_type key |
|---|---|
| `InvestmentBankerAgent` | `investment_banker` |
| `VPCapitalMarketsAgent` | `vp_capital_markets` |
| `ValuationsAnalystAgent` | `valuations` |
| `CapitalBudgetingManagerAgent` | `capital_budgeting` |

**⚠️ `CORP_FINANCE_AGENT_DEFINITIONS` uses key `class` not `display_name`** — same fix as treasury ✅ Session 11

---

## 12d. ⚠️ PHASE 4C ADDITIONS REGISTRY (Session 9)

*(Unchanged from v15)*

### agents/phase4_orchestrator.py
| Item | Detail |
|---|---|
| Class | `Phase4Orchestrator` |
| `__init__()` | `(api_key: str)` |
| `route()` | `(raw_data, tenant_id, period, jurisdiction, extra_context, enable_research, force_department, force_agent_type, force_analysis_type)` |
| L1 model | `claude-haiku-4-5` |
| L2 model | `claude-sonnet-4-6` |

---

## 12e. ⚠️ BUG FIX REGISTRY — SESSION 9

*(Unchanged from v15 — see v15 for full detail)*

Summary: TaxAgentTZ import name fix, FPA/Audit registry location fix, `get_escalation_engine` ghost fix, `FileIngestor` rename fix, `escalate_suggestion` method name fix, escalation DB migration, reasoning_log dashboard rendering fix.

---

## 12f. ⚠️ SESSION 10 ADDITIONS REGISTRY

*(Unchanged from v15)*

### agents/cost_accountant.py / revenue_accountant.py / accounting_manager.py
- All three: `__init__(api_key: str)`, `analyze(raw_data, period, tenant_id, jurisdiction, analysis_type, extra_context, enable_research, market_data)`
- Auto-escalate CRITICAL findings via `EscalationStore.create()` (fixed in Session 11)
- Exports: `COST_AGENT_DEFINITIONS`, `REVENUE_AGENT_DEFINITIONS`, `ACCOUNTING_MANAGER_DEFINITIONS`

### api/main.py (v5.1.0 → v5.2.0)
- `GET /accounting/agents`, `POST /accounting/analyze`, `GET /market/rates`, `GET /market/fx/{from}/{to}`

---

## 12g. ⚠️ BUG FIX REGISTRY — SESSION 11

All 29 route tests pass after these fixes. Server tested with FastAPI TestClient.

### Bug 1 — `junior_agent_factory` crash on retry
| Item | Detail |
|---|---|
| File | `api/main.py:198` |
| Error | `TypeError: junior_agent_factory() takes 0 positional arguments but 2 were given` |
| Root cause | Factory defined with no args but called as `self.junior_factory(tenant_id, jurisdiction)` in `escalation.py:598` |
| Fix | `def junior_agent_factory(tenant_id: str = "default", jurisdiction: str = "TZ"):` |
| Impact | Every `RETURN_TO_JUNIOR` retry was crashing — escalation retries now work |

### Bug 2 — `EscalationStore.create()` wrong call signature
| Item | Detail |
|---|---|
| File | `api/main.py:352` (`_handle_accounting_specialist_escalation`) |
| Error | `TypeError: create() got unexpected keyword argument 'id'` |
| Root cause | Called as `esc_store.create(id=esc_id, ..., junior_suggestion=json.dumps({...}))`. Method takes `(tenant_id, dict)`, returns generated UUID |
| Fix | `esc_id = esc_store.create(tenant_id=tenant_id, junior_suggestion={...})` — removed `id=`, removed `json.dumps()`, capture returned id |
| Impact | CRITICAL auto-escalation from accounting specialists was broken |

### Bug 3 — All tax routes crash on startup
| Item | Detail |
|---|---|
| File | `api/main.py:596–625` |
| Error | `TypeError: __init__() takes 1 positional argument but 2 were given` |
| Root cause | `TaxOrchestrator(API_KEY)`, `TaxAgentTZ(API_KEY)`, `TaxAgentUS(API_KEY)` — all three take no args |
| Fix | Removed API_KEY from all three constructors. Fixed param names: `raw_data` → `raw_input`, removed `enable_research`. Used `TZ_TAX_RULES`/`US_TAX_RULES` module constants directly |
| Impact | `/tax/analyze`, `/tax/analyze/tz`, `/tax/analyze/us`, `/tax/rules/tz`, `/tax/rules/us` all broken |

### Bug 4 — `tax_routes.py` broken escalation integration
| Item | Detail |
|---|---|
| File | `api/tax_routes.py:94` |
| Error | `ImportError: cannot import name 'get_escalation_engine' from 'api.escalation'` + `asyncio` deadlock |
| Root cause | Tried to import non-existent function; wrapped synchronous `engine.process()` in `asyncio.new_event_loop()` |
| Fix | Removed asyncio; builds EscalationEngine locally, calls `engine.process()` directly (it spawns its own thread) |

### Bug 5 — `stats()` unsynced count cross-tenant pollution
| Item | Detail |
|---|---|
| File | `db/store.py:251` |
| Error | `unsynced` count showed global total regardless of tenant |
| Fix | Added `tenant_id=?` filter: `WHERE tenant_id=? AND synced=0` |

### Bug 6 — SQL column-name injection in `update_state`
| Item | Detail |
|---|---|
| File | `api/escalation.py:152` |
| Risk | `**kwargs` keys interpolated directly into SQL — any unknown column name passed through |
| Fix | Added `_UPDATABLE_COLUMNS` frozenset whitelist; unknown keys logged as WARNING and dropped |

### Bug 7 — `datetime.utcnow()` deprecated on Python 3.12+
| Item | Detail |
|---|---|
| File | `api/escalation.py` (11 occurrences) |
| Fix | Added `timezone` to import; replaced all with `datetime.now(timezone.utc)` |

### Bug 8 — `run.py` demo crashes immediately
| Item | Detail |
|---|---|
| File | `run.py:86` |
| Error | `TypeError: __init__() got unexpected keyword argument 'api_key'` |
| Fix | `JuniorAccountantAgent(tenant_id=tenant_id, jurisdiction="TZ")` + `junior.process(raw_input=json.dumps(...), source="demo", extra_context="")` |

### Bug 9 — `get_suggestion` O(n) lookup
| Item | Detail |
|---|---|
| File | `api/main.py:502` |
| Issue | Loaded up to 1,000 rows to find a single record |
| Fix | `store.get_suggestion(suggestion_id)` — O(1) indexed lookup. Also validates `tenant_id` matches |

### Bug 10 — `EscalationStore` instantiated per-request
| Item | Detail |
|---|---|
| File | `api/main.py` — 6 route handlers |
| Issue | Each request ran `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE` on construction |
| Fix | Module-level `esc_store = EscalationStore()` singleton; all route handlers use it |

### Bug 11 — Hardcoded relative file paths
| Item | Detail |
|---|---|
| Files | `api/main.py`, `api/escalation.py`, `db/store.py` |
| Issue | `Path("reports")`, `open("dashboard/index.html")`, `"finops_escalation.db"` all relative to CWD |
| Fix | `_ROOT = Path(__file__).parent.parent` in each file; `REPORTS_DIR = _ROOT / "reports"` in main.py |

### Bug 12 — Request body size unbounded
| Item | Detail |
|---|---|
| File | `api/main.py` — all analysis request models |
| Issue | Unbounded `str` fields sent directly to Claude API — no cost protection |
| Fix | `raw_data`/`raw_text`/`raw_email`: `Field(..., max_length=200_000)`. Context/notes: `Field("", max_length=10_000)` |

### Bug 13 — `requirements.txt.txt` double extension
| Item | Detail |
|---|---|
| Fix | Created `requirements.txt` with correct name. Old file can be deleted. |

### Bug 14 — No `.gitignore`
| Item | Detail |
|---|---|
| Fix | Created `.gitignore` excluding `.env`, `*.db`, `__pycache__/`, `reports/*.pdf`, `venv/` |

### Bug 15 — `health` endpoint crash
| Item | Detail |
|---|---|
| File | `api/main.py:397` |
| Error | `KeyError: 'display_name'` — `TREASURY_AGENT_DEFINITIONS` and `CORP_FINANCE_AGENT_DEFINITIONS` use key `class` not `display_name` |
| Fix | `.get("display_name") or .get("class") or d["agent_type"]` for treasury and corp finance |

---

## 13. ESCALATION CHAIN — FULL LIFECYCLE

```
Raw data arrives (file / email / webhook / text)
      ↓
DataIngestor.from_*(…) → dict → .get("text","") → JuniorAccountantAgent.process()
      ↓
Suggestion saved to finops_offline.db via store.save_suggestion(suggestion, tenant_id, jurisdiction)
      ↓
Human clicks "↑ Escalate" on Queue tab
      ↓
main.py fetches suggestion, injects suggestion_id, calls engine.process(suggestion, tenant_id, notes, "")
      ↓
[ESCALATION CHAIN STARTS — background thread in escalation.py]
      ↓
Senior Accountant reviews
  ├── APPROVE_WITH_NOTES / AMEND_AND_ESCALATE → proceed to Controller
  ├── FLAG_CRITICAL → FLAGGED_CRITICAL state + urgent email → stop
  └── RETURN_TO_JUNIOR → inject critique context → Junior retries (max 2x) ✅ Now working (Session 11)
            └── if max retries exceeded → MAX_RETRIES_EXCEEDED + email alert
      ↓
Financial Controller reviews
  ├── RECOMMEND_APPROVAL / RECOMMEND_APPROVAL_WITH_CONDITIONS → PENDING_HUMAN
  ├── ESCALATE_TO_HUMAN_URGENT → PENDING_HUMAN + urgent email
  ├── RECOMMEND_REJECTION → PENDING_HUMAN (human still decides)
  └── RETURN_TO_SENIOR → inject critique → Senior retries (max 2x)
            └── if max retries exceeded → MAX_RETRIES_EXCEEDED + email alert
      ↓
PENDING_HUMAN — email sent to operator (if SMTP configured), appears in Escalations tab
      ↓
Human APPROVES → engine.process_human_approval(esc_id, True, notes) → POSTED
Human REJECTS  → engine.process_human_approval(esc_id, False, notes) → HUMAN_REJECTED
                    ↓
              "↺ Resubmit" → engine.process_resubmit(esc_id, context, tenant_id) → fresh chain
```

---

## 14. ESCALATION STATES REFERENCE

| State | Meaning |
|---|---|
| `JUNIOR_COMPLETE` | Junior has processed, ready to escalate |
| `PENDING_SENIOR` | Senior is reviewing |
| `SENIOR_COMPLETE` | Senior review done |
| `PENDING_CONTROLLER` | Controller is reviewing |
| `CONTROLLER_COMPLETE` | Controller review done |
| `PENDING_HUMAN` | Awaiting operator decision in dashboard |
| `HUMAN_APPROVED` | Operator approved, auto-posting |
| `POSTING` | Auto-post in progress |
| `POSTED` | Successfully posted to accounting system |
| `POST_FAILED` | Auto-post failed — check adapter |
| `HUMAN_REJECTED` | Operator rejected — resubmit available |
| `RESUBMITTED` | Original rejected escalation marked as resubmitted |
| `RETURNED_TO_JUNIOR` | Senior sent back — Junior retrying |
| `RETURNED_TO_SENIOR` | Controller sent back — Senior retrying |
| `FLAGGED_CRITICAL` | Fraud/regulatory breach detected — stop immediately |
| `MAX_RETRIES_EXCEEDED` | Too many retries — manual intervention needed |
| `ERROR` | System error — check logs |

---

## 15. API ENDPOINTS REFERENCE

### Interactive API docs (Swagger UI)
**`http://localhost:8000/docs`** — try every endpoint live, see request/response schemas

### Phase 1
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | System health + agent inventory |
| GET | `/tenants` | List tenants |
| POST | `/tenants` | Create tenant |
| DELETE | `/tenants/{id}` | Delete tenant |
| POST | `/tenants/detect` | Auto-detect tenant from document |
| GET | `/suggestions/{tenant_id}` | List suggestions |
| GET | `/suggestions/{tenant_id}/{id}` | Get single suggestion — O(1) ✅ Session 11 |
| POST | `/suggestions/{tenant_id}/{id}/decide` | Approve / Reject / Escalate |
| GET | `/stats/{tenant_id}` | Dashboard stats (per-tenant unsynced count ✅ Session 11) |
| POST | `/ingest/text` | Ingest raw text (max 200k chars) |
| POST | `/ingest/email` | Ingest email (max 200k chars) |
| POST | `/ingest/upload` | Ingest file upload |
| POST | `/ingest/webhook/{system}` | Ingest webhook |

### Phase 2
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/escalations` | List all (`?tenant_id=` filter) |
| GET | `/escalations/pending` | PENDING_HUMAN |
| GET | `/escalations/rejected` | HUMAN_REJECTED |
| GET | `/escalations/{id}` | Single escalation |
| POST | `/escalations/{id}/approve` | Human approves |
| POST | `/escalations/{id}/reject` | Human rejects |
| POST | `/escalations/{id}/resubmit` | Resubmit with context |

### Phase 3 (Tax)
| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/tax/analyze` | Auto-routes TZ or US (max 200k chars) |
| POST | `/tax/analyze/tz` | Force Tanzania |
| POST | `/tax/analyze/us` | Force US LLC |
| GET | `/tax/rules/tz` | TZ tax constants |
| GET | `/tax/rules/us` | US tax constants |
| GET | `/tax/rates/config` | config/tax_rates.json |
| POST | `/tax/compute/se-tax` | Quick US SE tax |
| POST | `/tax/compute/vat` | Quick TZ VAT |
| POST | `/tax/compute/amt` | Quick TZ AMT |
| POST | `/tax/compute/provisional` | Quick TZ provisional |
| POST | `/tax/compute/quarterly` | Quick US quarterly |

### Reports + Dashboard
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Dashboard (dashboard/index.html) |
| GET | `/reports` | List PDFs |
| GET | `/reports/latest/{tenant_id}` | Latest report metadata |
| GET | `/reports/{filename}` | Download PDF |

### Phase 4A–4C + Session 10
| Method | Endpoint | Purpose |
|---|---|---|
| GET/POST | `/fpa/agents`, `/fpa/analyze` | FP&A agents |
| GET/POST | `/audit/agents`, `/audit/analyze` | Audit agents |
| GET/POST | `/treasury/agents`, `/treasury/analyze` | Treasury agents |
| GET/POST | `/corpfin/agents`, `/corpfin/analyze` | Corp Finance agents |
| POST | `/analyze` | Universal — Phase4Orchestrator |
| GET | `/auth/role` | Current role + permissions |
| GET/POST | `/accounting/agents`, `/accounting/analyze` | Specialist agents |
| GET | `/market/rates` | Live FX + US + TZ rates |
| GET | `/market/fx/{from}/{to}` | Single FX rate |

---

## 16. BUILD PHASES

### Phase 1 — Junior Accountant POC ✅ COMPLETE
### Phase 2 — Full Review Chain ✅ COMPLETE & LIVE
### Phase 3 — Tax Agents ✅ COMPLETE & TESTED
### Phase 5 — OCR Support ✅ COMPLETE (Session 5)
### Session 6 — Consolidation ✅ COMPLETE
### Phase 4A — FP&A + Auditing Agents ✅ COMPLETE (Session 7)
### Phase 4B — Treasury + Corporate Finance ✅ COMPLETE (Session 8)
### Phase 4C — Orchestrator + RBAC + Dashboard ✅ COMPLETE & LIVE (Session 9)
### Session 10 — Accounting Specialists + Market Data ✅ COMPLETE & LIVE

### Session 11 — Bug Fix & Hardening ✅ COMPLETE & TESTED (April 2026)
- [x] 15 bugs fixed — all runtime crashes, security issues, correctness bugs
- [x] 29/29 route tests pass (FastAPI TestClient)
- [x] Tax routes fully operational (TaxOrchestrator, TaxAgentTZ, TaxAgentUS)
- [x] Escalation retry loop working (RETURN_TO_JUNIOR passes tenant_id + jurisdiction)
- [x] CRITICAL auto-escalation from accounting specialists working
- [x] Column injection protection in EscalationStore.update_state
- [x] All timestamps timezone-aware (Python 3.14 compatible)
- [x] All file paths absolute — server runs from any working directory
- [x] Request body size limits protect against unbounded Claude API costs
- [x] `.gitignore` created — .env and .db files excluded from version control
- [x] `requirements.txt` fixed (was `requirements.txt.txt`)
- [x] Git repository initialized

---

## 17. PLANNED FEATURES BACKLOG

### ✅ Complete — see Build Phases above

### 🔲 Tax Accountant Agent
Deferred tax (IAS 12 / ASC 740), tax provision, ETR reconciliation.

### 🔲 Phase 4D — FP&A + Audit + Treasury + Corp Finance Escalation Wiring
High-severity findings wired into Senior → Controller → Human chain.

### 🔲 SMTP Email — Live Configuration
Set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL`, `OPERATOR_EMAIL` in `.env`.

### 🔲 Unit Test Suite
Replace integration-only tests with mocked LLM responses + pytest structure.

---

## 18. TOKEN USAGE & COST LOG

| Session | Date | Component | Est. Tokens | Est. Cost |
|---|---|---|---|---|
| 1 | Apr 2026 | Discovery & Planning | ~13,000 | ~$0.09 |
| 2 | Apr 2026 | Junior Accountant + Dashboard + Ingestion + DB | ~126,500 | ~$1.06 |
| 3 | Apr 2026 | Phase 2 — Senior + Controller + Escalation | ~275,000 | ~$2.85 |
| 4 | Apr 2026 | Phase 3 — Tax Agents + API + Dashboard + PDF | ~270,000 | ~$2.70 |
| 5 | Apr 2026 | Phase 5 — OCR Support | ~80,000 | ~$0.75 |
| 6 | Apr 2026 | Session 6 — Consolidation + Dashboard | ~120,000 | ~$1.15 |
| 7 | Apr 2026 | Phase 4A — FP&A + Audit Agents | ~180,000 | ~$1.80 |
| 8 | Apr 2026 | Phase 4B — Treasury + Corp Finance | ~160,000 | ~$1.60 |
| 9 | Apr 2026 | Phase 4C — Orchestrator + RBAC + Dashboard | ~200,000 | ~$2.00 |
| 10 | Apr 2026 | Session 10 — Accounting Specialists + Market Data | ~180,000 | ~$1.80 |
| 11 | Apr 2026 | Session 11 — Bug Fix & Hardening (15 bugs, 29 tests) | ~95,000 | ~$0.90 |
| **Total** | | | **~1,699,500** | **~$16.70** |

## v5.5.0 - Audit Export + OCR Upload Fallback

### Added
- Added `/audit/export` with JSON and CSV output for tenant-specific suggestion decision history.
- Hardened the existing OCR fallback for scanned PDFs and added OCR for image uploads.

### Safeguards
- Audit export is read-only and does not modify suggestion records.
- OCR fallback does not change agent prompts, orchestrator routing, or the DB schema.
- Scanned PDFs are limited to 10 pages and low-quality OCR output is rejected instead of being passed to agents.
- Missing OCR system dependencies return a clear API-level configuration error.

### Tests
- Added tests for audit export validation, filtering, empty results, and output formats.
- Added mocked tests for PDF OCR fallback, image OCR, page limits, source propagation, and failure handling.
