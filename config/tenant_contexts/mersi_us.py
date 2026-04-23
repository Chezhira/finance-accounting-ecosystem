"""
Mersi Distribution LLC — Tenant Context
Injected into the Junior Accountant agent for every transaction processed
under tenant_id=mersi_us.

WHAT THE INTEGRATIONS ALREADY HANDLE (do not duplicate):
  - Fishbowl → QBO (native): inventory receipts, COGS on sale, landed cost
    allocation, PO matching. These journal entries are auto-posted by Fishbowl.
  - Bill.com → QBO: vendor invoice entry and AP payments. These sync automatically.

WHAT THIS CONTEXT COVERS (the gaps):
  1. Bank feed transactions outside Fishbowl/Bill.com flows
  2. Manual warehouse inventory adjustments (2 locations not in Fishbowl)
  3. Fishbowl → QBO sync discrepancies
  4. SouthStar factoring entries (no system integration — fully manual)
  5. Month-end accruals, prepaid amortization, depreciation entries
  6. Credit card charges and any transactions not routed through the above systems
"""

MERSI_CONTEXT = """
═══════════════════════════════════════════════════════════════
TENANT CONTEXT: MERSI DISTRIBUTION LLC (tenant_id: mersi_us)
═══════════════════════════════════════════════════════════════

BUSINESS OVERVIEW
─────────────────
Mersi Distribution LLC — US medical supplies distributor, Miami FL.
Sells to senior living homes across the US. Imports product from overseas.
Jurisdiction: United States. Standard: US GAAP. Currency: USD.

SYSTEM INTEGRATION MAP
──────────────────────
Fishbowl (inventory) ──native sync──► QuickBooks Online (GL)
Bill.com (AP payments) ──native sync──► QuickBooks Online (GL)
SouthStar (AR factoring) ──NO integration──► manual entries required
Deel (contractors) ──NO integration──► manual entries required
Bank feed ──QBO bank feed──► manual categorisation required

WHAT FISHBOWL ALREADY POSTS TO QBO (do not re-post):
  - Inventory receipts: DR Inventory / CR AP (on PO receipt)
  - Landed costs: freight, duties, broker fees allocated in Fishbowl
    and pushed as part of inventory cost — already capitalised
  - COGS: DR COGS / CR Inventory (auto on sale/shipment)
  - Inventory adjustments for Fishbowl-connected warehouses

WHAT BILL.COM ALREADY POSTS TO QBO (do not re-post):
  - Vendor invoice accruals
  - AP payment entries

IMPORTANT — MANUAL WAREHOUSES:
  Two warehouse locations do NOT connect to Fishbowl. Inventory movements
  at these locations must be manually entered as journal entries in QBO.
  These are high-risk — flag any inventory adjustment for these locations
  for Zahidah review regardless of amount.

═══════════════════════════════════════════════════════════════
CHART OF ACCOUNTS — MERSI DISTRIBUTION
═══════════════════════════════════════════════════════════════

ASSETS
  1000  Cash — Operating Account
  1010  Cash — Payroll Account
  1100  Accounts Receivable
  1110  Factoring Reserve Account (SouthStar 20% holdback)
  1200  Inventory (Fishbowl is source of truth — do not manually adjust
        without Zahidah approval; manual warehouse adjustments are an exception)
  1300  Prepaid Expenses

LIABILITIES
  2000  Accounts Payable (Bill.com — do not manually enter AP if it came through Bill.com)
  2100  Accrued Liabilities
  2200  Credit Card Payable
  2300  Loans Payable

EQUITY
  3000  Owner's Capital
  3100  Retained Earnings

REVENUE
  4000  Product Sales Revenue
  4100  Other Income

COST OF GOODS SOLD (5000s)
  NOTE: Fishbowl handles all COGS and landed cost entries automatically.
  Only post to 5000s manually if Fishbowl sync has failed or for corrections.
  5000  Cost of Goods Sold
  5100  Freight In — Inbound Shipping
  5200  Freight In — International / Air Freight
  5300  Import Duties & Tariffs
  5400  Customs Broker Fees
  5500  Landed Cost Adjustments

OPERATING EXPENSES (6000s) — primary focus of manual categorisation
  6010  Contract Labor / Contractor Fees (Deel)
  6020  Bookkeeping & Accounting Fees
  6100  Warehouse Rent
  6110  Office Rent
  6200  Utilities — Warehouse
  6210  Utilities — Office / Internet / Phone
  6300  Depreciation Expense
  6400  Software & Subscriptions
  6410  Outbound Shipping & Packaging
  6500  Professional Fees — Legal
  6510  Professional Fees — Accounting / Advisory
  6520  Factoring Fees (SouthStar 2% fee only)
  6530  Bank Charges & Merchant Fees
  6600  Travel & Entertainment
  6610  Meals — Internal
  6700  Insurance — General Liability
  6710  Insurance — Product Liability
  6720  Insurance — Cargo / Freight
  6800  Office Supplies
  6810  Warehouse Supplies (non-inventory packing materials)
  6900  Marketing & Advertising
  6910  Sales Commissions
  7000  Interest Expense
  7100  Income Tax Expense

═══════════════════════════════════════════════════════════════
TRANSACTION TYPES REQUIRING MANUAL ENTRIES
═══════════════════════════════════════════════════════════════

TYPE 1 — BANK FEED / CREDIT CARD TRANSACTIONS
Transactions that hit the bank or credit card directly and are not routed
through Fishbowl or Bill.com. These need manual categorisation.

Common examples and their codes:
  Deel contractor disbursements         → 6010 Contract Labor
  Deel platform fee                     → 6400 Software & Subscriptions
  QuickBooks / Intuit                   → 6400 Software & Subscriptions
  Fishbowl subscription                 → 6400 Software & Subscriptions
  Slack                                 → 6400 Software & Subscriptions
  Bill.com platform fee                 → 6400 Software & Subscriptions
  Microsoft 365 / Google Workspace      → 6400 Software & Subscriptions
  Zoom / Read.AI / any SaaS             → 6400 Software & Subscriptions
  Warehouse rent payment                → 6100 Warehouse Rent
  Office rent payment                   → 6110 Office Rent
  Electric / gas utility                → 6200 Utilities — Warehouse
  Internet / phone                      → 6210 Utilities — Office
  Insurance premium                     → 6700 / 6710 / 6720 (see type)
  Amazon Business / Staples             → 6800 Office Supplies
  Bank service / wire fee               → 6530 Bank Charges
  Credit card payment (balance payoff)  → 2200 Credit Card Payable (NOT an expense)
  Loan repayment                        → split 2300 (principal) + 7000 (interest)

TYPE 2 — SOUTHSTAR FACTORING (three distinct entries, all manual)
SouthStar has no QBO integration. Every factoring transaction is manual.

  Entry A — Advance received (80% of factored invoice):
    DR 1000  Cash                         [advance amount]
    CR 1100  Accounts Receivable          [advance amount]
    ← Reduces AR. NOT revenue. NOT income.

  Entry B — Reserve release (balance after fees):
    DR 1000  Cash                         [reserve release amount]
    CR 1110  Factoring Reserve Account    [reserve release amount]

  Entry C — SouthStar fee (2% of invoice face value):
    DR 6520  Factoring Fees               [fee amount]
    CR 1110  Factoring Reserve Account    [fee amount]

  CRITICAL: Never code any SouthStar deposit to 4000 Revenue. It is a cash
  advance against an existing receivable, not new income.

TYPE 3 — MANUAL WAREHOUSE INVENTORY ADJUSTMENTS
For the two warehouse locations not connected to Fishbowl.
All inventory adjustments at these locations require manual journal entries.

  Inventory increase (count higher than book):
    DR 1200  Inventory                    [value at cost]
    CR 5000  COGS                         [same amount]

  Inventory decrease / write-down (count lower than book, damage, expiry):
    DR 5000  COGS (or separate write-down account)  [value]
    CR 1200  Inventory                              [value]

  FLAG ALL MANUAL WAREHOUSE ADJUSTMENTS as requiring Zahidah approval
  regardless of amount. These are high-risk entries.

TYPE 4 — FISHBOWL → QBO SYNC CORRECTIONS
When a Fishbowl sync has failed or posted incorrectly, a correcting entry
may be needed. These should always be flagged CRITICAL and escalated to
Senior Accountant — do not auto-approve sync correction entries.

TYPE 5 — MONTH-END ACCRUALS (recurring entries)
  Prepaid insurance amortization:
    DR 6700 / 6710 / 6720  Insurance Expense   [monthly portion]
    CR 1300  Prepaid Expenses                  [same]

  Depreciation (fixed assets):
    DR 6300  Depreciation Expense              [monthly charge]
    CR 1510  Accumulated Depreciation          [same]

  Accrued expenses (goods/services received, invoice not yet in Bill.com):
    DR [relevant expense account]              [estimated amount]
    CR 2100  Accrued Liabilities               [same]

═══════════════════════════════════════════════════════════════
DECISION RULES
═══════════════════════════════════════════════════════════════

RULE M1 — CHECK THE SOURCE FIRST
Before coding any transaction, ask: did this come through Fishbowl or Bill.com?
  - If yes → it is already in QBO. Do not re-post. Flag as potential duplicate.
  - If no → apply the rules below.

RULE M2 — SOUTHSTAR DEPOSITS ARE NOT REVENUE
Any deposit from SouthStar Capital reduces AR (Type 2 above).
If you see a large round deposit from SouthStar, it is an advance — not income.

RULE M3 — CREDIT CARD BALANCE PAYMENTS ARE NOT EXPENSES
Paying the credit card balance: DR 2200 Credit Card Payable / CR 1000 Cash.
The individual charges on the card are expenses — not the payment itself.

RULE M4 — MANUAL WAREHOUSE ADJUSTMENTS NEED APPROVAL
Any entry touching 1200 Inventory for the manual warehouse locations must
be flagged for Zahidah review (set escalate_to_senior: true).

RULE M5 — FISHBOWL SYNC ERRORS — ESCALATE ALWAYS
If a transaction appears to be correcting a Fishbowl sync error, always
escalate. These entries affect inventory valuation and COGS accuracy.

RULE M6 — LANDED COSTS ARE FISHBOWL'S JOB
Freight, duties, broker fees on inbound shipments are handled by Fishbowl
as part of landed cost. If one of these appears on the bank feed independently
(e.g. a customs duty payment direct debit), verify it is not already posted
by Fishbowl before coding it to 5000s.

═══════════════════════════════════════════════════════════════
ESCALATION RULES FOR MERSI
═══════════════════════════════════════════════════════════════
Escalate (set escalate_to_senior: true) when:
  - Any manual warehouse inventory adjustment (always)
  - Any Fishbowl sync correction (always)
  - Amount exceeds USD 2,000 and transaction type is uncertain
  - Transaction appears to duplicate something already in QBO
  - SouthStar transaction does not match Type A, B, or C above
  - Any related-party transaction
  - Landed cost entry that may already be in Fishbowl

Do NOT escalate for:
  - Any SaaS subscription from a known vendor
  - Recurring rent or utility payments
  - Deel contractor payments
  - Factoring fee entries (Type 2C) under USD 500
  - Bank charges and merchant fees
═══════════════════════════════════════════════════════════════
"""


def get_context() -> str:
    """Return the Mersi tenant context string for injection into agent prompts."""
    return MERSI_CONTEXT
