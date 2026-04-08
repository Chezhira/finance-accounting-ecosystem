"""
FinOps Ecosystem — Phase 4A Test Data
Session 7 Test Pack

Covers all 9 agents:
  FP&A:   FPAAnalyst, FPAManager, SeniorFPAManager, VPFinance, DataAnalyst
  Audit:  ComplianceAuditor, AuditManager, QAAuditor, ForensicAuditor

Each fixture is a dict with keys:
  - agent        : agent class name
  - method       : method to call (analyze / audit / investigate)
  - kwargs       : all arguments to pass
  - description  : what this test is checking

Run:
  python tests/test_phase4a_agents.py

Requires: ANTHROPIC_API_KEY in environment or .env file
"""

import json
import os
import sys
import time
from datetime import datetime

# ─── path setup ───────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
if not API_KEY:
    sys.exit("ERROR: ANTHROPIC_API_KEY not set in environment or .env")

from agents.fpa_agents import (
    FPAAnalystAgent,
    FPAManagerAgent,
    SeniorFPAManagerAgent,
    VPFinanceAgent,
    DataAnalystAgent,
)
from agents.audit_agents import (
    ComplianceAuditorAgent,
    AuditManagerAgent,
    QAAuditorAgent,
    ForensicAuditorAgent,
)

# ─── colour helpers ───────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):  print(f"  {GREEN}✅ {msg}{RESET}")
def err(msg): print(f"  {RED}❌ {msg}{RESET}")
def info(msg):print(f"  {CYAN}ℹ  {msg}{RESET}")
def warn(msg):print(f"  {YELLOW}⚠  {msg}{RESET}")

# ──────────────────────────────────────────────────────────────────────────────
# TEST DATA FIXTURES
# ──────────────────────────────────────────────────────────────────────────────

# ── FP&A Analyst — Tanzania Q1 2026 variance analysis ─────────────────────────
FPA_ANALYST_TZ = {
    "agent": "FPAAnalyst",
    "description": "TZ — Q1 2026 variance analysis with budget vs actual",
    "raw_data": """
ACME TRADING LTD — Q1 2026 MANAGEMENT ACCOUNTS (UNAUDITED)
Jurisdiction: Tanzania | Currency: TZS | Standard: IFRS

P&L SUMMARY (TZS millions)
                        Actual Q1-2026    Budget Q1-2026    Prior Q1-2025
Revenue                      4,850             5,200             3,980
  - Product Sales             3,200             3,500             2,700
  - Service Revenue           1,450             1,500             1,180
  - Other Income                200               200               100
Cost of Goods Sold           2,750             2,860             2,150
Gross Profit                 2,100             2,340             1,830
Gross Margin %                43.3%             45.0%             46.0%

Operating Expenses           1,420             1,380             1,150
  - Salaries & Wages           680               650               540
  - Rent & Utilities           210               200               185
  - Marketing                  180               200               140
  - Admin & General            230               220               195
  - Depreciation               120               110                90

EBITDA                         800               960               770
EBITDA Margin %               16.5%             18.5%             19.3%

Finance Costs                   95                80                70
PBT                            705               880               700
Tax (30% estimated)            212               264               210
PAT                            493               616               490

BALANCE SHEET SNAPSHOT (TZS millions)
Cash & Bank                    320
Trade Receivables            1,240   (DSO: 74 days vs 60 days budget)
Inventory                      980   (DIO: 130 days vs 90 days budget)
Trade Payables                 890   (DPO: 118 days vs 90 days budget)
Short-term Debt              1,500
Long-term Debt               2,200

NOTES:
- Revenue shortfall driven by delayed Dar es Salaam port clearances affecting product sales.
- Salary overspend: 2 additional hires vs budget (IT and compliance roles).
- Marketing underspend: digital campaign delayed to Q2.
- DSO deterioration: 3 large customers (>TZS 300M each) extended payment terms.
- Inventory build-up: supply chain pre-stocking ahead of Finance Act 2025 VAT changes.
""",
    "kwargs": {
        "period": "Q1-2026",
        "tenant_id": "acme_tz_001",
        "jurisdiction": "TZ",
        "analysis_type": "variance",
        "enable_research": False,
    },
}

# ── FP&A Analyst — US LLC monthly KPI pack ────────────────────────────────────
FPA_ANALYST_US = {
    "agent": "FPAAnalyst",
    "description": "US LLC — March 2026 KPI tracking",
    "raw_data": """
SMITH FAMILY LLC — MARCH 2026 KPI PACK
Jurisdiction: United States | Currency: USD | Standard: US GAAP | Entity: Single-member LLC

MONTHLY P&L
                        Mar-2026    Feb-2026    Mar-2025    YTD-2026    Budget YTD
Revenue                  142,500     138,200     121,000     418,300      435,000
COGS                      78,400      76,100      68,500     231,200      239,250
Gross Profit              64,100      62,100      52,500     187,100      195,750
Gross Margin %             45.0%       44.9%       43.4%       44.7%        45.0%
Operating Expenses        38,200      37,400      34,200     112,900      117,000
EBITDA                    25,900      24,700      18,300      74,200       78,750
Net Income                21,500      20,300      14,800      61,200       64,500

CASH FLOW
Operating Cash Flow       19,800      22,100      16,200      57,400       63,000
CAPEX                      4,200           0       1,500       8,200        6,000
Free Cash Flow            15,600      22,100      14,700      49,200       57,000

KEY METRICS
Headcount                     12          12          10
Revenue per Employee      11,875      11,517      12,100
Customer Count               247         241         198
Average Order Value          577         573         611
Customer Acquisition Cost    420         398         385
LTV:CAC Ratio                4.2x        4.3x        4.5x

QUARTERLY ESTIMATED TAX (note for operator review)
Q1 estimated tax due: April 15, 2026
Estimated net SE income YTD: $61,200
SE tax base (x 92.35%): $56,518
Estimated SE tax: $8,647
QBI deduction (20%): $12,240
""",
    "kwargs": {
        "period": "Mar-2026",
        "tenant_id": "smith_llc_us",
        "jurisdiction": "US",
        "analysis_type": "kpi",
        "enable_research": False,
    },
}

# ── FP&A Manager — Tanzania 3-statement model ─────────────────────────────────
FPA_MANAGER_TZ = {
    "agent": "FPAManager",
    "description": "TZ — Full-year 2026 3-statement model with 3 scenarios",
    "raw_data": """
ACME TRADING LTD — FY2026 PLANNING MODEL INPUT
Jurisdiction: Tanzania | Currency: TZS millions | IFRS

HISTORICAL BASE (FY2025 Actuals)
Revenue:        17,200
COGS:            9,460  (55% of revenue)
Gross Profit:    7,740
Opex:            5,160
EBITDA:          2,580  (15.0% margin)
Depreciation:      420
EBIT:            2,160
Finance Costs:     340
PBT:             1,820
Tax (30%):         546
PAT:             1,274

Opening Cash:      450
Capex FY2025:      680
Working Capital Change: (220) [increase]
Closing Cash:      890

Opening Debt (long-term):  3,800
New borrowing FY2025:        500
Repayments FY2025:          (300)
Closing Debt:              4,000

PLANNING ASSUMPTIONS FOR FY2026
Management base case:
- Revenue growth: +12% (driven by new Mwanza branch opening Q3)
- COGS as % revenue: 54% (slight efficiency improvement)
- Opex growth: +8% (inflation + Mwanza branch costs)
- Capex: TZS 1,200M (Mwanza fitout TZS 700M + fleet TZS 500M)
- New debt facility: TZS 800M at 15% p.a. (BOT base rate + 3%)
- Debt repayment: TZS 400M scheduled
- Dividend: TZS 300M (proposed, subject to board approval)
- Working capital: DSO 65 days, DIO 100 days, DPO 90 days
- VAT withholding agent implications: cash flow timing on VAT collections

RISKS TO BASE CASE
1. Port clearance delays could reduce revenue by TZS 800M
2. TZS depreciation risk (USD/TZS currently 2,680; FY2025 avg 2,540)
3. Energy cost inflation (TANESCO tariff increase expected H2 2026)
4. TRA audit risk: company flagged for transfer pricing review
""",
    "kwargs": {
        "period": "FY2026",
        "tenant_id": "acme_tz_001",
        "jurisdiction": "TZ",
        "model_type": "3statement",
        "enable_research": False,
    },
}

# ── FP&A Manager — US CAPEX appraisal ─────────────────────────────────────────
FPA_MANAGER_US = {
    "agent": "FPAManager",
    "description": "US LLC — CAPEX appraisal for new equipment",
    "raw_data": """
SMITH FAMILY LLC — CAPEX APPRAISAL REQUEST
Project: CNC Laser Engraver — Production Expansion
Currency: USD

INVESTMENT DETAILS
Equipment cost:         $85,000
Installation:            $8,500
Training:                $3,500
Total initial investment: $97,000

PROJECTED BENEFITS (annual)
Additional revenue capacity: $120,000/year (60% utilisation assumed)
Incremental COGS:             $48,000/year (40% margin on new revenue)
Incremental gross profit:     $72,000/year
Additional operating costs:   $18,000/year (power, maintenance, operator OT)
Incremental EBITDA:           $54,000/year

FINANCING
Funding: 50% cash ($48,500), 50% SBA loan ($48,500) at 7.5% p.a. over 5 years
Annual debt service: ~$11,800/year

ASSUMPTIONS
- Useful life: 7 years
- Salvage value: $8,500 (10% of equipment cost)
- Straight-line depreciation
- Corporate tax not applicable (LLC pass-through)
- WACC estimated at 12% (owner's required return)
- Revenue ramp: 40% Year 1, 70% Year 2, 100% Year 3+
- Section 179 expensing available in Year 1 (full equipment cost deductible)

SENSITIVITY
- If utilisation is 40%: revenue $80,000, EBITDA $28,000
- If utilisation is 80%: revenue $160,000, EBITDA $80,000
""",
    "kwargs": {
        "period": "FY2026-FY2032",
        "tenant_id": "smith_llc_us",
        "jurisdiction": "US",
        "model_type": "capex",
        "enable_research": False,
    },
}

# ── Senior FP&A Manager — Tanzania LRP ────────────────────────────────────────
SENIOR_FPA_TZ = {
    "agent": "SeniorFPAManager",
    "description": "TZ — 5-year LRP and board pack",
    "raw_data": """
ACME TRADING LTD — 5-YEAR LONG-RANGE PLAN INPUTS
Jurisdiction: Tanzania | Currency: TZS millions | IFRS

FY2025 BASE (Audited)
Revenue: 17,200 | EBITDA: 2,580 | EBITDA %: 15.0%
Net Debt: 3,110 | Net Debt/EBITDA: 1.2x
ROCE: 18.5%

STRATEGIC INITIATIVES (FY2026–FY2030)
1. Geographic expansion: Mwanza (FY2026), Arusha (FY2028), Zanzibar (FY2029)
2. Digital transformation: ERP upgrade (Odoo) + e-commerce channel FY2027
3. Private label product range: 15% margin uplift on own-brand SKUs (FY2027 launch)
4. B2B contract manufacturing supply agreements (3-year fixed price)

MACRO ASSUMPTIONS
- Tanzania GDP growth: 5.5% p.a. (IMF WEO)
- Inflation: 4.8% p.a. average
- TZS/USD: flat at 2,700 through FY2028, then 5% annual depreciation
- Corporate tax rate: 30% (no changes anticipated)
- VAT: 18% maintained
- AMT risk: low (company profitable)

STRATEGIC REVENUE TARGETS
FY2026: 19,260 (growth: 12%)
FY2027: 22,350 (growth: 16% — Mwanza full year + e-commerce)
FY2028: 26,000 (growth: 16% — private label scale)
FY2029: 30,000 (growth: 15% — Arusha operational)
FY2030: 34,500 (growth: 15% — Zanzibar + full digital maturity)

TARGET EBITDA MARGINS
FY2026: 15.5% | FY2027: 16.5% | FY2028: 17.5% | FY2029: 18.0% | FY2030: 19.0%

FINANCING PLAN
- FY2026: TZS 800M new debt (Mwanza)
- FY2027: TZS 2,000M new debt (Odoo + e-commerce infrastructure)
- FY2028: Consider equity raise or strategic partner (TZS 3,000M+)
- Target net debt/EBITDA: max 2.5x at any point

RISKS TO LRP
1. Political risk — Election cycle FY2025 (complete), FY2030
2. Regulatory: TRA increased audit activity in FMCG sector
3. Competition: 2 new South African FMCG entrants entering TZ market FY2026
4. Currency: USD-denominated imports = 40% of COGS (FX exposure)
5. Talent: CFO succession planning required by FY2028
""",
    "kwargs": {
        "period": "FY2026-FY2030",
        "tenant_id": "acme_tz_001",
        "jurisdiction": "TZ",
        "output_type": "lrp",
        "enable_research": False,
    },
}

# ── VP Finance — WACC and capital structure ────────────────────────────────────
VP_FINANCE_TZ = {
    "agent": "VPFinance",
    "description": "TZ — WACC calculation and capital structure recommendation",
    "raw_data": """
ACME TRADING LTD — CAPITAL STRUCTURE REVIEW
Jurisdiction: Tanzania | Currency: TZS millions | IFRS

CURRENT BALANCE SHEET (FY2025)
Total Assets: 18,400
Total Equity: 6,890
Total Debt: 4,000
  - Short-term (<1yr): 1,500 at avg 16.5% p.a.
  - Long-term: 2,500 at avg 14.8% p.a.
Cash: 890
Net Debt: 3,110

COST OF EQUITY INPUTS
Risk-free rate: 7.2% (TZ 10yr gov bond yield, BOT data)
Equity risk premium: 8.5% (Tanzania ERP — Damodaran emerging market)
Beta: 1.15 (estimated vs listed FMCG peers — USE, DSE data)
Size premium: 2.0% (small/mid cap illiquidity)

COST OF DEBT
Weighted average cost of debt: 15.4% p.a. (blended)
Tax rate: 30%
After-tax cost of debt: 10.8%

MARKET VALUES (estimated — private company)
Equity (book used as proxy): 6,890
Debt: 4,000
Enterprise Value estimate: ~12,500 (8x EBITDA — comparable transactions)

PEER BENCHMARKS (listed TZ/EAC FMCG)
Average Net Debt/EBITDA: 1.5x
Average EBITDA margin: 16.2%
Average ROCE: 17.8%
Average WACC: 18-22% range (analyst estimates)

STRATEGIC QUESTION FOR VP REVIEW
Board is considering: (a) additional debt of TZS 1,500M to fund Mwanza expansion,
OR (b) bringing in a private equity minority investor (15-20% stake) at ~8x EBITDA valuation.
Assess optimal capital structure and recommend approach.
""",
    "kwargs": {
        "period": "FY2026",
        "tenant_id": "acme_tz_001",
        "jurisdiction": "TZ",
        "output_type": "wacc",
        "enable_research": False,
    },
}

# ── Data Analyst — anomaly detection on transaction ledger ────────────────────
DATA_ANALYST = {
    "agent": "DataAnalyst",
    "description": "Statistical anomaly detection on expense ledger + Benford pre-check",
    "raw_data": """
ACME TRADING LTD — Q1 2026 EXPENSE LEDGER (SAMPLE 50 TRANSACTIONS)
Tenant: acme_tz_001 | Currency: TZS | Period: Jan-Mar 2026

TXN_ID    DATE        VENDOR                  CATEGORY        AMOUNT_TZS   APPROVED_BY
TXN001    2026-01-05  Dar Supplies Co         Stationery          285,000   Mary K
TXN002    2026-01-08  TeleTZ Ltd              Telecoms          1,240,000   Mary K
TXN003    2026-01-12  Dar Supplies Co         Stationery          285,000   Mary K   ← DUPLICATE DATE DIFF
TXN004    2026-01-15  National Fuel Depot     Fuel              3,100,000   John M
TXN005    2026-01-19  Mwanza Freight          Logistics         8,450,000   John M
TXN006    2026-01-22  Unknown Vendor XYZ      Consultancy      22,000,000   CEO Direct
TXN007    2026-01-25  Dar Supplies Co         Stationery          284,999   Mary K   ← NEAR DUPLICATE
TXN008    2026-01-28  ABC Security            Security          2,100,000   Mary K
TXN009    2026-02-02  TeleTZ Ltd              Telecoms          1,240,000   Mary K
TXN010    2026-02-05  National Fuel Depot     Fuel              4,800,000   John M   ← SPIKE +55%
TXN011    2026-02-08  Fast Print Services     Marketing           890,000   Sarah A
TXN012    2026-02-11  Mwanza Freight          Logistics         8,450,000   John M
TXN013    2026-02-14  Unknown Vendor XYZ      Consultancy      22,000,000   CEO Direct  ← REPEAT
TXN014    2026-02-18  Global Consulting Ltd   Consultancy      45,000,000   CEO Direct  ← LARGE
TXN015    2026-02-20  Dar Supplies Co         Stationery          285,500   Mary K
TXN016    2026-02-24  Power Solutions TZ      Utilities         1,890,000   Mary K
TXN017    2026-02-27  ABC Security            Security          2,100,000   Mary K
TXN018    2026-03-03  National Fuel Depot     Fuel              3,200,000   John M
TXN019    2026-03-06  TeleTZ Ltd              Telecoms          1,240,000   Mary K
TXN020    2026-03-09  Unknown Vendor XYZ      Consultancy      22,000,000   CEO Direct  ← REPEAT x3
TXN021    2026-03-12  Mwanza Freight          Logistics         8,450,000   John M
TXN022    2026-03-15  Fast Print Services     Marketing           910,000   Sarah A
TXN023    2026-03-18  Global Consulting Ltd   Consultancy      45,000,000   CEO Direct  ← REPEAT
TXN024    2026-03-21  Dar Supplies Co         Stationery          285,000   Mary K
TXN025    2026-03-25  ABC Security            Security          2,100,000   Mary K
TXN026    2026-03-28  Power Solutions TZ      Utilities         1,920,000   Mary K
TXN027    2026-03-31  Staff Expenses Pool     Reimbursements    9,800,000   CEO Direct  ← LARGE/VAGUE

SUMMARY STATS
Total expenses Q1: TZS 318,309,499
Budget Q1: TZS 280,000,000  [OVERSPEND: TZS 38,309,499 / 13.7%]
Consultancy budget: TZS 40,000,000
Consultancy actual: TZS 178,000,000  [OVERSPEND: 345%]
Unknown Vendor XYZ: 3 invoices x TZS 22M = TZS 66M — no contract on file
Global Consulting Ltd: 2 invoices x TZS 45M = TZS 90M — no contract on file
CEO Direct approvals: 6 transactions, total TZS 224,800,000 (70.6% of total spend)
""",
    "kwargs": {
        "period": "Q1-2026",
        "tenant_id": "acme_tz_001",
        "analysis_type": "anomaly",
        "enable_research": False,
    },
}

# ── Compliance Auditor — SoD and regulatory review ────────────────────────────
COMPLIANCE_AUDITOR = {
    "agent": "ComplianceAuditor",
    "description": "TZ — SoD conflicts, TRA compliance, COSO assessment",
    "raw_data": """
ACME TRADING LTD — COMPLIANCE REVIEW INPUT
Jurisdiction: Tanzania | Period: FY2025 | IFRS | Companies Act 2002

ORGANIZATIONAL CONTROLS
Staffing: 47 employees
Finance team: 6 (CFO, 2 accountants, 2 AP clerks, 1 payroll)
IT team: 2 (IT Manager + 1 IT Officer)
Approvals policy: purchases >TZS 5M require CFO sign-off; >TZS 20M require CEO

SEGREGATION OF DUTIES CONCERNS IDENTIFIED
1. AP Clerk A (initiate purchase requisition + raise PO + post invoice + approve payment up to TZS 4.9M)
2. Payroll Officer processes payroll AND maintains employee master file (add/remove employees)
3. IT Manager has both admin rights to accounting system AND approves IT vendor invoices
4. CFO can both approve payments AND reconcile bank accounts
5. No independent review of journal entries posted by accountants

REGULATORY STATUS
TRA:
- VAT returns: Jan-2026 filed, Feb-2026 filed, Mar-2026 OVERDUE (due 20-Apr-2026 — not filed as of 06-Apr-2026)
- Corporate tax: FY2024 return filed timely; FY2025 return due 30-Jun-2026 — preparation not started
- Provisional tax Q3-FY2026: due 15-Mar-2026 — filed and paid TZS 420M
- Transfer pricing: No documentation prepared (related party = parent company UAE)
- WHT on imported services: 3 payments to foreign consultants in Q1-2026 — WHT not deducted

BRELA:
- Annual return FY2025: Filed 28-Feb-2026 ✓
- Director changes: 2 new directors appointed Jan-2026 — BRELA filing PENDING

COMPANIES ACT:
- Annual general meeting: Due within 6 months of year-end (Jun-2026) — not scheduled
- Auditor appointment: External auditor contract renewal OVERDUE (expired Dec-2025)

POLICY GAPS NOTED
- No whistleblower policy in place
- No anti-bribery & corruption policy (written policy)
- Expense reimbursement policy last updated 2019
- IT security policy: last updated 2021
- No related-party transaction disclosure process
""",
    "kwargs": {
        "audit_period": "FY2025",
        "tenant_id": "acme_tz_001",
        "jurisdiction": "TZ",
        "audit_scope": "general_compliance_and_sod",
        "enable_research": False,
    },
}

# ── Audit Manager — Going concern + materiality ───────────────────────────────
AUDIT_MANAGER = {
    "agent": "AuditManager",
    "description": "TZ — Going concern assessment and materiality for FY2025 audit",
    "raw_data": """
ACME TRADING LTD — FY2025 AUDIT INPUT PACK
Jurisdiction: Tanzania | Currency: TZS millions | IFRS | External audit support

FINANCIAL SUMMARY FY2025 (draft)
Revenue:                17,200
PBT:                     1,820
Total Assets:           18,400
Total Equity:            6,890
Net Debt:                3,110
Net Debt/EBITDA:          1.2x
Current Ratio:            1.08  [LOW — near 1.0 threshold]
Quick Ratio:              0.62  [BELOW 1.0]
Interest Coverage:        6.4x
Free Cash Flow:           +890

GOING CONCERN INDICATORS
NEGATIVE INDICATORS:
1. Current ratio 1.08 — declining (FY2024: 1.35, FY2023: 1.52)
2. Short-term debt of TZS 1,500M due for renewal Apr-2026 — bank renewal letter not yet received
3. Consultancy overspend TZS 138M unbudgeted (see Q1-2026 data)
4. Transfer pricing documentation missing — TRA audit risk (potential TZS 500M+ liability)
5. TRA VAT arrears risk: Mar-2026 VAT return overdue
6. Auditor not yet re-appointed (contract expired Dec-2025)

POSITIVE INDICATORS / MITIGATING FACTORS:
1. Company profitable for 8 consecutive years
2. Strong trading relationships: top 5 customers >5 years each
3. Net Debt/EBITDA 1.2x — within banking covenant (max 3.0x)
4. New TZS 800M facility being negotiated (term sheet stage)
5. Management plan: asset sale (warehouse property) TZS 1,200M proceeds expected H2-2026
6. Board committed to dividend waiver if cash flow deteriorates

AUDIT SCOPE
Entity: Acme Trading Ltd (standalone, not consolidated)
Year end: 31 December 2025
Audit standard: ISA (as adopted by NBAA Tanzania)
Prior year opinion: Unqualified
Prior year materiality: TZS 182M (1% of revenue)
Prior year errors identified: 1 uncorrected (TZS 28M understatement of accruals — below materiality)

RELEVANT BALANCES FOR MATERIALITY
Revenue: 17,200 | PBT: 1,820 | Total Assets: 18,400 | Equity: 6,890
""",
    "kwargs": {
        "audit_period": "FY2025",
        "tenant_id": "acme_tz_001",
        "jurisdiction": "TZ",
        "audit_type": "going_concern",
        "enable_research": False,
    },
}

# ── QA Auditor — ITGC and access review ──────────────────────────────────────
QA_AUDITOR = {
    "agent": "QAAuditor",
    "description": "TZ — ITGC review and user access rights audit",
    "raw_data": """
ACME TRADING LTD — IT GENERAL CONTROLS REVIEW
Jurisdiction: Tanzania | Period: FY2025 | System: QuickBooks Enterprise + Fishbowl

USER ACCESS REVIEW (QuickBooks)
Username           Role              Last Login      Admin?   Notes
admin              System Admin      2026-01-15      YES      Shared password — 4 staff know it
cfo_james          Full Access       2026-04-05      YES      Active
accountant_mary    Full Access       2026-04-04      YES      Should be limited to AP only
accountant_peter   Full Access       2026-03-28      YES      On maternity cover — should be read-only
ap_clerk_anna      AP + Payments     2026-04-05      NO       Can both create AND approve own payments
ap_clerk_ben       AP Only           2026-02-14      NO       DORMANT >45 days
payroll_sarah      Payroll Full      2026-04-05      NO       Can add employees AND process payroll
it_manager_david   Full Access       2026-04-05      YES      IT role — should have no accounting access
ex_employee_tom    Full Access       NEVER (2024)    NO       TERMINATED Dec-2024 — account not disabled
trainee_linda      Full Access       2026-01-20      NO       Temporary staff — excessive access

CHANGE MANAGEMENT
- Last system update: QuickBooks version updated Feb-2026 — no change log maintained
- Chart of accounts changes: 3 new accounts added Mar-2026 — added by accountant_mary, no approval
- Fishbowl-QuickBooks sync settings changed Jan-2026 — changed by it_manager_david, no approval

BACKUP AND DR
- Last backup test: NEVER formally tested
- Backup frequency: Daily automated (cloud)
- RTO defined: No | RPO defined: No
- Disaster recovery plan: Not documented

PROCESS IMPROVEMENT OBSERVATIONS
- Month-end close takes avg 12 days (industry benchmark: 5-7 days)
- VAT reconciliation done manually in Excel (high error risk)
- Bank reconciliation done weekly (should be daily given cash flow concerns)
- Supplier statement reconciliations: only done for top 10 vendors

IT SECURITY
- Password policy: No minimum length enforced in system
- MFA: Not enabled
- VPN: Not used for remote access
- Last security audit: Never conducted
""",
    "kwargs": {
        "review_period": "FY2025",
        "tenant_id": "acme_tz_001",
        "jurisdiction": "TZ",
        "review_type": "itgc",
        "enable_research": False,
    },
}

# ── Forensic Auditor — procurement fraud indicators ───────────────────────────
FORENSIC_AUDITOR = {
    "agent": "ForensicAuditor",
    "description": "TZ — Procurement fraud investigation (consultancy overspend + unknown vendors)",
    "raw_data": """
ACME TRADING LTD — FORENSIC REVIEW INPUT
Jurisdiction: Tanzania | Period: Q1 2026 | PCCB / AMLA jurisdiction

REFERRAL BASIS
Internal flag from Data Analyst: consultancy spend 345% over budget.
CEO is sole approver for Unknown Vendor XYZ and Global Consulting Ltd.
No contracts on file for either vendor. Total at risk: TZS 178,000,000.

VENDOR REGISTRATION CHECKS
Unknown Vendor XYZ:
- TIN: not verifiable (TRA ETIMS not returning result)
- BRELA registration: not found in public register
- Physical address: PO Box 4421, Dar es Salaam — no street address
- Bank account: Equity Bank Tanzania — personal account name, not company
- Contact: single mobile number, no website
- Invoices: hand-written, no VAT number, no professional letterhead
- Services described: "Consultancy and advisory services" — no SOW attached

Global Consulting Ltd:
- TIN: Valid ✓
- BRELA: Registered Feb-2025 (3 months before first invoice)
- Director: Name partially matches CEO's spouse (different spelling — could be coincidence)
- Physical address: Same PO Box as Unknown Vendor XYZ ← SAME BOX
- Bank account: CRDB Bank Tanzania — company account ✓
- Invoices: Professional format, but no SOW or deliverables documented
- Services: "Strategic business development advisory"

PAYMENT PATTERN
Unknown Vendor XYZ: 3 x TZS 22,000,000 = TZS 66,000,000
  - All paid within 3 days of invoice (standard terms are 30 days)
  - All approved on same day as invoice date
  - Payments made on 22-Jan, 13-Feb, 09-Mar (consistent monthly cycle)

Global Consulting Ltd: 2 x TZS 45,000,000 = TZS 90,000,000
  - Both paid within 5 days
  - No board resolution for >TZS 20M (policy breach — should need CEO + CFO)
  - CFO was on annual leave both approval dates

STAFF EXPENSE POOL (TXN027)
TZS 9,800,000 — "Staff Expenses Q1 2026 Pool"
- No breakdown provided
- No supporting receipts attached
- Approved by CEO only
- Posted as single lump sum journal entry (not itemised)

BENFORD ANALYSIS NOTE
Transaction amounts submitted for Benford test:
22000000, 22000000, 22000000, 45000000, 45000000, 9800000
First digit distribution: heavy concentration on 2, 4, 9 — limited dataset but warrants flagging.
""",
    "kwargs": {
        "investigation_period": "Q1-2026",
        "tenant_id": "acme_tz_001",
        "jurisdiction": "TZ",
        "investigation_type": "procurement",
        "enable_research": False,
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# ALL FIXTURES
# ──────────────────────────────────────────────────────────────────────────────

ALL_FIXTURES = [
    FPA_ANALYST_TZ,
    FPA_ANALYST_US,
    FPA_MANAGER_TZ,
    FPA_MANAGER_US,
    SENIOR_FPA_TZ,
    VP_FINANCE_TZ,
    DATA_ANALYST,
    COMPLIANCE_AUDITOR,
    AUDIT_MANAGER,
    QA_AUDITOR,
    FORENSIC_AUDITOR,
]

# ──────────────────────────────────────────────────────────────────────────────
# RUNNER
# ──────────────────────────────────────────────────────────────────────────────

AGENT_MAP = {
    "FPAAnalyst":         (FPAAnalystAgent,        "analyze"),
    "FPAManager":         (FPAManagerAgent,         "analyze"),
    "SeniorFPAManager":   (SeniorFPAManagerAgent,   "analyze"),
    "VPFinance":          (VPFinanceAgent,           "analyze"),
    "DataAnalyst":        (DataAnalystAgent,         "analyze"),
    "ComplianceAuditor":  (ComplianceAuditorAgent,   "audit"),
    "AuditManager":       (AuditManagerAgent,        "audit"),
    "QAAuditor":          (QAAuditorAgent,           "audit"),
    "ForensicAuditor":    (ForensicAuditorAgent,     "investigate"),
}

VALIDATION_RULES = {
    "FPAAnalyst":        ["variances", "kpis", "flags", "suggestions"],
    "FPAManager":        ["three_statement_summary", "scenarios", "flags", "suggestions"],
    "SeniorFPAManager":  ["lrp_projections", "strategic_risks", "flags", "suggestions"],
    "VPFinance":         ["wacc_analysis", "enterprise_risks", "flags", "suggestions"],
    "DataAnalyst":       ["data_quality_report", "anomalies", "flags", "suggestions"],
    "ComplianceAuditor": ["coso_assessment", "sod_conflicts", "findings", "flags"],
    "AuditManager":      ["materiality", "going_concern_assessment", "findings", "flags"],
    "QAAuditor":         ["itgc_assessment", "access_review", "findings", "flags"],
    "ForensicAuditor":   ["fraud_indicators", "mandatory_reporting", "findings", "flags"],
}


def validate_output(agent_name: str, result: dict) -> tuple[bool, list[str]]:
    """Check required output fields are present and non-empty."""
    issues = []
    required = VALIDATION_RULES.get(agent_name, [])
    for field in required:
        if field not in result:
            issues.append(f"Missing field: '{field}'")
        elif result[field] in (None, [], {}, ""):
            issues.append(f"Empty field: '{field}'")
    if "error" in result and "raw_response" in result:
        issues.append(f"JSON parse failed: {result.get('error')}")
    return len(issues) == 0, issues


def run_fixture(fixture: dict) -> dict:
    agent_name = fixture["agent"]
    description = fixture["description"]
    raw_data = fixture["raw_data"]
    kwargs = fixture["kwargs"]

    cls, method_name = AGENT_MAP[agent_name]
    agent = cls(api_key=API_KEY)
    method = getattr(agent, method_name)

    print(f"\n{BOLD}{'─'*70}{RESET}")
    print(f"{BOLD}{CYAN}▶ {agent_name}{RESET} — {description}")
    print(f"  Method: {method_name}() | Tenant: {kwargs.get('tenant_id')} | "
          f"Jurisdiction: {kwargs.get('jurisdiction', 'N/A')}")

    start = time.time()
    try:
        result = method(raw_data=raw_data, **kwargs)
        elapsed = time.time() - start

        ok(f"Agent returned in {elapsed:.1f}s")

        # Validate required fields
        passed, issues = validate_output(agent_name, result)
        if passed:
            ok(f"All required fields present")
        else:
            for issue in issues:
                err(issue)

        # Show top-level keys
        info(f"Output keys: {list(result.keys())}")

        # Show flags summary
        flags = result.get("flags", [])
        if flags:
            critical = [f for f in flags if f.get("level") == "CRITICAL"]
            high     = [f for f in flags if f.get("level") == "HIGH"]
            if critical:
                err(f"CRITICAL flags ({len(critical)}): {[f.get('message','?')[:80] for f in critical]}")
            if high:
                warn(f"HIGH flags ({len(high)}): {[f.get('message','?')[:80] for f in high]}")
            info(f"Total flags: {len(flags)}")

        # Show suggestions count
        suggestions = result.get("suggestions", [])
        info(f"Suggestions generated: {len(suggestions)}")
        if suggestions:
            info(f"  Sample: {suggestions[0][:100]}")

        # Agent-specific highlights
        _show_highlights(agent_name, result)

        return {"agent": agent_name, "status": "PASS" if passed else "PARTIAL", "result": result, "elapsed": elapsed}

    except Exception as e:
        elapsed = time.time() - start
        err(f"Exception after {elapsed:.1f}s: {type(e).__name__}: {e}")
        return {"agent": agent_name, "status": "FAIL", "error": str(e), "elapsed": elapsed}


def _show_highlights(agent_name: str, result: dict):
    """Print agent-specific interesting output fields."""
    if agent_name == "FPAAnalyst":
        variances = result.get("variances", [])
        if variances:
            v = variances[0]
            info(f"  Top variance: {v.get('metric')} | "
                 f"Actual: {v.get('actual')} | Budget: {v.get('budget')} | "
                 f"Var%: {v.get('variance_pct_vs_budget')}")
        kpis = result.get("kpis", [])
        reds = [k for k in kpis if k.get("status") == "RED"]
        if reds:
            warn(f"  RED KPIs: {[k.get('name') for k in reds]}")

    elif agent_name == "FPAManager":
        ts = result.get("three_statement_summary", {})
        if ts:
            info(f"  Revenue: {ts.get('revenue')} | EBITDA%: {ts.get('ebitda_margin_pct')} | "
                 f"FCF: {ts.get('free_cash_flow')} | Currency: {ts.get('currency')}")
        cap = result.get("capex_appraisal", {})
        if cap and cap.get("npv"):
            info(f"  CAPEX: NPV={cap.get('npv')} | IRR={cap.get('irr_pct')}% | "
                 f"Payback={cap.get('payback_years')}yr | Rec: {cap.get('recommendation')}")

    elif agent_name == "SeniorFPAManager":
        lrp = result.get("lrp_projections", [])
        if lrp:
            info(f"  LRP years: {[p.get('year') for p in lrp]}")
            last = lrp[-1] if lrp else {}
            info(f"  FY2030 target: Revenue={last.get('revenue')} | "
                 f"EBITDA%={last.get('ebitda_margin_pct')}")

    elif agent_name == "VPFinance":
        wacc = result.get("wacc_analysis", {})
        if wacc:
            info(f"  WACC: {wacc.get('wacc_pct')}% | "
                 f"CoE: {wacc.get('cost_of_equity_pct')}% | "
                 f"CoD (AT): {wacc.get('cost_of_debt_pct')}%")

    elif agent_name == "DataAnalyst":
        anomalies = result.get("anomalies", [])
        if anomalies:
            highs = [a for a in anomalies if a.get("severity") == "HIGH"]
            warn(f"  HIGH anomalies detected: {len(highs)}")
            if highs:
                info(f"  Sample: {highs[0].get('field')} = {highs[0].get('value')} "
                     f"(z-score: {highs[0].get('z_score')})")

    elif agent_name == "ComplianceAuditor":
        sod = result.get("sod_conflicts", [])
        if sod:
            criticals = [s for s in sod if s.get("severity") == "CRITICAL"]
            warn(f"  SoD conflicts: {len(sod)} total, {len(criticals)} CRITICAL")
        reg = result.get("regulatory_compliance", [])
        non = [r for r in reg if r.get("status") == "NON_COMPLIANT"]
        if non:
            err(f"  NON_COMPLIANT items: {[r.get('regulation') for r in non]}")
        rating = result.get("overall_compliance_rating", "?")
        info(f"  Overall rating: {rating}")

    elif agent_name == "AuditManager":
        mat = result.get("materiality", {})
        if mat:
            info(f"  Materiality: {mat.get('overall_materiality')} {mat.get('currency','TZS')} "
                 f"| Benchmark: {mat.get('percentage_applied_pct')}% of {mat.get('benchmark_used')}")
        gc = result.get("going_concern_assessment", {})
        if gc:
            assessment = gc.get("overall_assessment", "?")
            disc = gc.get("disclosure_required", False)
            label = f"{RED}⚠ MATERIAL UNCERTAINTY{RESET}" if "UNCERTAINTY" in assessment or "DOUBT" in assessment else f"{GREEN}No doubt{RESET}"
            info(f"  Going concern: {label} | Disclosure required: {disc}")

    elif agent_name == "QAAuditor":
        access = result.get("access_review", [])
        issues = [a for a in access if a.get("issue") not in ("OK", None)]
        if issues:
            warn(f"  Access issues: {len(issues)} — types: {list(set(a.get('issue') for a in issues))}")
        itgc = result.get("itgc_assessment", {})
        if itgc:
            ineffective = [k for k, v in itgc.items() if isinstance(v, dict) and v.get("rating") == "INEFFECTIVE"]
            if ineffective:
                err(f"  INEFFECTIVE ITGC domains: {ineffective}")

    elif agent_name == "ForensicAuditor":
        indicators = result.get("fraud_indicators", [])
        if indicators:
            crits = [i for i in indicators if i.get("severity") == "CRITICAL"]
            total_at_risk = sum(i.get("amount_at_risk", 0) or 0 for i in indicators)
            warn(f"  Fraud indicators: {len(indicators)} total | CRITICAL: {len(crits)}")
            if total_at_risk:
                warn(f"  Total amount at risk: TZS {total_at_risk:,.0f}")
        sar = result.get("mandatory_reporting", {})
        if sar.get("sar_str_required"):
            err(f"  ⚠ SAR/STR MAY BE REQUIRED — Authority: {sar.get('authority')} — HUMAN REVIEW NEEDED")


def main():
    # Allow running a single agent by name: python test_phase4a_agents.py FPAAnalyst
    filter_agent = sys.argv[1] if len(sys.argv) > 1 else None
    fixtures = [f for f in ALL_FIXTURES if not filter_agent or f["agent"] == filter_agent]

    if not fixtures:
        print(f"{RED}No fixtures matched '{filter_agent}'{RESET}")
        print(f"Available: {[f['agent'] for f in ALL_FIXTURES]}")
        sys.exit(1)

    print(f"\n{BOLD}{'='*70}{RESET}")
    print(f"{BOLD}  FinOps Ecosystem — Phase 4A Agent Test Suite{RESET}")
    print(f"  Running {len(fixtures)} fixture(s) | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{BOLD}{'='*70}{RESET}")

    results = []
    for fixture in fixtures:
        r = run_fixture(fixture)
        results.append(r)
        # Small pause to avoid rate limiting
        if len(fixtures) > 1:
            time.sleep(2)

    # Summary
    print(f"\n{BOLD}{'='*70}{RESET}")
    print(f"{BOLD}  TEST SUMMARY{RESET}")
    print(f"{'='*70}")
    passed  = sum(1 for r in results if r["status"] == "PASS")
    partial = sum(1 for r in results if r["status"] == "PARTIAL")
    failed  = sum(1 for r in results if r["status"] == "FAIL")
    total_time = sum(r.get("elapsed", 0) for r in results)

    for r in results:
        status_str = f"{GREEN}PASS{RESET}" if r["status"] == "PASS" else \
                     f"{YELLOW}PARTIAL{RESET}" if r["status"] == "PARTIAL" else \
                     f"{RED}FAIL{RESET}"
        print(f"  {status_str}  {r['agent']:<22} {r.get('elapsed', 0):.1f}s")

    print(f"\n  Total: {passed} PASS | {partial} PARTIAL | {failed} FAIL | {total_time:.0f}s elapsed")
    print(f"{BOLD}{'='*70}{RESET}\n")

    # Save full results to JSON
    out_path = os.path.join(os.path.dirname(__file__), "phase4a_test_results.json")
    with open(out_path, "w") as f:
        json.dump(
            [{k: v for k, v in r.items() if k != "result"} for r in results],
            f, indent=2, default=str
        )
    print(f"  Results saved → {out_path}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
