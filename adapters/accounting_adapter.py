"""
Accounting System Adapter — Finance & Accounting AI Ecosystem
Agnostic interface: agents call push_journal_entry() — the adapter handles the
system-specific API call (QuickBooks, Xero, Odoo, etc.)
Adding a new accounting system = subclass AccountingAdapter + implement 3 methods.
"""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


# ─────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────

@dataclass
class JournalLine:
    account_code: str
    account_name: str
    debit: Optional[float]
    credit: Optional[float]
    memo: str = ""

@dataclass
class JournalEntry:
    description: str
    date: str              # YYYY-MM-DD
    currency: str          # TZS, USD, etc.
    reference: str         # suggestion_id or invoice ref
    lines: list[JournalLine]
    tenant_id: str


# ─────────────────────────────────────────────
# BASE ADAPTER INTERFACE
# ─────────────────────────────────────────────

class AccountingAdapter(ABC):
    """
    System-agnostic interface. Every accounting system adapter implements these 3 methods.
    The agent layer NEVER calls system APIs directly — only through this interface.
    """

    @abstractmethod
    def push_journal_entry(self, entry: JournalEntry) -> dict:
        """
        Submit an approved journal entry to the accounting system.
        Returns: { success: bool, system_id: str, message: str }
        """

    @abstractmethod
    def get_chart_of_accounts(self, tenant_id: str) -> list[dict]:
        """
        Fetch the full chart of accounts.
        Returns list of { code, name, type, active }
        """

    @abstractmethod
    def get_vendor(self, vendor_name: str, tenant_id: str) -> Optional[dict]:
        """
        Look up a vendor by name.
        Returns: { id, name, email, terms } or None
        """


# ─────────────────────────────────────────────
# QUICKBOOKS ADAPTER
# ─────────────────────────────────────────────

class QuickBooksAdapter(AccountingAdapter):
    """
    QuickBooks Online adapter using the Intuit QBO REST API.
    Credentials via env vars or passed explicitly.
    """

    BASE_URL = "https://quickbooks.api.intuit.com/v3"

    def __init__(
        self,
        realm_id: Optional[str] = None,
        access_token: Optional[str] = None,
        sandbox: bool = False,
    ):
        self.realm_id = realm_id or os.environ.get("QB_REALM_ID")
        self.access_token = access_token or os.environ.get("QB_ACCESS_TOKEN")
        self.sandbox = sandbox
        if sandbox:
            self.BASE_URL = "https://sandbox-quickbooks.api.intuit.com/v3"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def push_journal_entry(self, entry: JournalEntry) -> dict:
        """
        POST a JournalEntry to QuickBooks as a JournalEntry object.
        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/journalentry
        """
        try:
            import requests
        except ImportError:
            return {"success": False, "message": "requests library not installed"}

        lines = []
        for i, line in enumerate(entry.lines, 1):
            posting_type = "Debit" if (line.debit or 0) > 0 else "Credit"
            amount = line.debit if posting_type == "Debit" else line.credit
            lines.append({
                "Id": str(i),
                "JournalEntryLineDetail": {
                    "PostingType": posting_type,
                    "AccountRef": {"name": line.account_name, "value": line.account_code},
                },
                "DetailType": "JournalEntryLineDetail",
                "Amount": float(amount or 0),
                "Description": line.memo,
            })

        payload = {
            "DocNumber": entry.reference[:21],  # QB max 21 chars
            "TxnDate": entry.date,
            "PrivateNote": entry.description,
            "CurrencyRef": {"value": entry.currency},
            "Line": lines,
        }

        url = f"{self.BASE_URL}/company/{self.realm_id}/journalentry"
        try:
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            je_id = data.get("JournalEntry", {}).get("Id", "")
            return {"success": True, "system_id": je_id, "message": "Journal entry created in QuickBooks"}
        except Exception as e:
            return {"success": False, "system_id": "", "message": str(e)}

    def get_chart_of_accounts(self, tenant_id: str) -> list[dict]:
        try:
            import requests
            url = f"{self.BASE_URL}/company/{self.realm_id}/query"
            query = "SELECT * FROM Account WHERE Active = true MAXRESULTS 1000"
            resp = requests.get(url, headers=self._headers(), params={"query": query}, timeout=15)
            resp.raise_for_status()
            accounts = resp.json().get("QueryResponse", {}).get("Account", [])
            return [
                {"code": a.get("AcctNum", ""), "name": a["Name"],
                 "type": a.get("AccountType", ""), "active": a.get("Active", True)}
                for a in accounts
            ]
        except Exception as e:
            return []

    def get_vendor(self, vendor_name: str, tenant_id: str) -> Optional[dict]:
        try:
            import requests
            url = f"{self.BASE_URL}/company/{self.realm_id}/query"
            query = f"SELECT * FROM Vendor WHERE DisplayName LIKE '%{vendor_name}%' MAXRESULTS 5"
            resp = requests.get(url, headers=self._headers(), params={"query": query}, timeout=15)
            resp.raise_for_status()
            vendors = resp.json().get("QueryResponse", {}).get("Vendor", [])
            if vendors:
                v = vendors[0]
                return {"id": v["Id"], "name": v["DisplayName"], "email": v.get("PrimaryEmailAddr", {}).get("Address", ""), "terms": ""}
            return None
        except Exception:
            return None

    # ── DATA PULL METHODS (for reconciliation and audit checks) ───────────────

    def get_account_balance(self, account_code: str) -> float:
        """Fetch the current balance of a specific GL account by account number."""
        try:
            import requests
            url = f"{self.BASE_URL}/company/{self.realm_id}/query"
            query = f"SELECT * FROM Account WHERE AcctNum = '{account_code}'"
            resp = requests.get(url, headers=self._headers(), params={"query": query}, timeout=15)
            resp.raise_for_status()
            accounts = resp.json().get("QueryResponse", {}).get("Account", [])
            if accounts:
                return float(accounts[0].get("CurrentBalance", 0))
            return 0.0
        except Exception as e:
            logger.error(f"[QBO] get_account_balance failed: {e}")
            return 0.0

    def get_ar_aging(self) -> dict:
        """
        Fetch AR aging report from QBO Reports API.
        Returns buckets: current, 1-30, 31-60, 61-90, 90+, total
        """
        try:
            import requests
            url = f"{self.BASE_URL}/company/{self.realm_id}/reports/AgedReceivables"
            resp = requests.get(url, headers=self._headers(), timeout=15)
            resp.raise_for_status()
            return self._parse_aging_report(resp.json())
        except Exception as e:
            logger.error(f"[QBO] get_ar_aging failed: {e}")
            return {}

    def get_ap_aging(self) -> dict:
        """
        Fetch AP aging report from QBO Reports API.
        Returns buckets: current, 1-30, 31-60, 61-90, 90+, total
        """
        try:
            import requests
            url = f"{self.BASE_URL}/company/{self.realm_id}/reports/AgedPayables"
            resp = requests.get(url, headers=self._headers(), timeout=15)
            resp.raise_for_status()
            return self._parse_aging_report(resp.json())
        except Exception as e:
            logger.error(f"[QBO] get_ap_aging failed: {e}")
            return {}

    def get_trial_balance(self) -> list[dict]:
        """
        Fetch trial balance from QBO Reports API.
        Returns list of {account, code, type, debit, credit, balance}
        """
        try:
            import requests
            url = f"{self.BASE_URL}/company/{self.realm_id}/reports/TrialBalance"
            resp = requests.get(url, headers=self._headers(), timeout=15)
            resp.raise_for_status()
            return self._parse_trial_balance(resp.json())
        except Exception as e:
            logger.error(f"[QBO] get_trial_balance failed: {e}")
            return []

    def get_open_invoices(self, customer_name: Optional[str] = None) -> list[dict]:
        """
        Fetch open (unpaid) invoices. Optionally filter by customer.
        Returns list of {invoice_id, customer, date, due_date, amount, balance, ref}
        Used for SouthStar factoring eligibility checks.
        """
        try:
            import requests
            url = f"{self.BASE_URL}/company/{self.realm_id}/query"
            query = "SELECT * FROM Invoice WHERE Balance > '0' MAXRESULTS 1000"
            if customer_name:
                query = f"SELECT * FROM Invoice WHERE CustomerRef IN (SELECT Id FROM Customer WHERE DisplayName LIKE '%{customer_name}%') AND Balance > '0' MAXRESULTS 200"
            resp = requests.get(url, headers=self._headers(), params={"query": query}, timeout=15)
            resp.raise_for_status()
            invoices = resp.json().get("QueryResponse", {}).get("Invoice", [])
            return [
                {
                    "invoice_id": inv["Id"],
                    "customer": inv.get("CustomerRef", {}).get("name", ""),
                    "date": inv.get("TxnDate", ""),
                    "due_date": inv.get("DueDate", ""),
                    "amount": float(inv.get("TotalAmt", 0)),
                    "balance": float(inv.get("Balance", 0)),
                    "ref": inv.get("DocNumber", ""),
                }
                for inv in invoices
            ]
        except Exception as e:
            logger.error(f"[QBO] get_open_invoices failed: {e}")
            return []

    def get_cogs_balance(self, from_date: str, to_date: str) -> float:
        """
        Fetch total COGS posted in QBO for a date range.
        Used to reconcile against Fishbowl COGS.
        """
        try:
            import requests
            url = f"{self.BASE_URL}/company/{self.realm_id}/reports/ProfitAndLoss"
            resp = requests.get(
                url, headers=self._headers(),
                params={"start_date": from_date, "end_date": to_date},
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            # Parse COGS line from P&L report
            for row in data.get("Rows", {}).get("Row", []):
                if row.get("group") == "CostOfGoodsSold":
                    for col in row.get("Summary", {}).get("ColData", []):
                        try:
                            val = float(col.get("value", 0))
                            if val != 0:
                                return val
                        except (ValueError, TypeError):
                            pass
            return 0.0
        except Exception as e:
            logger.error(f"[QBO] get_cogs_balance failed: {e}")
            return 0.0

    def _parse_aging_report(self, data: dict) -> dict:
        """Parse QBO aging report JSON into simple bucket dict."""
        result = {"current": 0, "1_30": 0, "31_60": 0, "61_90": 0, "over_90": 0, "total": 0}
        try:
            rows = data.get("Rows", {}).get("Row", [])
            for row in rows:
                cols = row.get("Summary", {}).get("ColData", [])
                if len(cols) >= 6:
                    result["current"] += float(cols[1].get("value", 0) or 0)
                    result["1_30"]    += float(cols[2].get("value", 0) or 0)
                    result["31_60"]   += float(cols[3].get("value", 0) or 0)
                    result["61_90"]   += float(cols[4].get("value", 0) or 0)
                    result["over_90"] += float(cols[5].get("value", 0) or 0)
            result["total"] = sum(v for k, v in result.items() if k != "total")
        except Exception:
            pass
        return result

    def _parse_trial_balance(self, data: dict) -> list[dict]:
        """Parse QBO trial balance report into list of account dicts."""
        accounts = []
        try:
            for row in data.get("Rows", {}).get("Row", []):
                cols = row.get("ColData", [])
                if len(cols) >= 3:
                    accounts.append({
                        "account": cols[0].get("value", ""),
                        "debit": float(cols[1].get("value", 0) or 0),
                        "credit": float(cols[2].get("value", 0) or 0),
                    })
        except Exception:
            pass
        return accounts


# ─────────────────────────────────────────────
# MOCK ADAPTER (for testing / offline mode)
# ─────────────────────────────────────────────

class MockAdapter(AccountingAdapter):
    """
    In-memory adapter for testing and offline mode.
    Logs all calls; does not call any external API.
    """

    def __init__(self):
        self.journal_entries: list[dict] = []
        self._coa = [
            {"code": "1000", "name": "Cash and Cash Equivalents", "type": "Asset", "active": True},
            {"code": "1100", "name": "Accounts Receivable", "type": "Asset", "active": True},
            {"code": "1200", "name": "Inventory", "type": "Asset", "active": True},
            {"code": "1500", "name": "Property, Plant & Equipment", "type": "Asset", "active": True},
            {"code": "1510", "name": "Accumulated Depreciation", "type": "Asset", "active": True},
            {"code": "1600", "name": "Intangible Assets", "type": "Asset", "active": True},
            {"code": "2000", "name": "Accounts Payable", "type": "Liability", "active": True},
            {"code": "2100", "name": "VAT Payable", "type": "Liability", "active": True},
            {"code": "2200", "name": "Accrued Liabilities", "type": "Liability", "active": True},
            {"code": "2300", "name": "Loans Payable", "type": "Liability", "active": True},
            {"code": "3000", "name": "Share Capital", "type": "Equity", "active": True},
            {"code": "3100", "name": "Retained Earnings", "type": "Equity", "active": True},
            {"code": "4000", "name": "Revenue", "type": "Income", "active": True},
            {"code": "4100", "name": "Other Income", "type": "Income", "active": True},
            {"code": "5000", "name": "Cost of Goods Sold", "type": "Expense", "active": True},
            {"code": "6000", "name": "Salaries & Wages", "type": "Expense", "active": True},
            {"code": "6100", "name": "Rent Expense", "type": "Expense", "active": True},
            {"code": "6200", "name": "Utilities Expense", "type": "Expense", "active": True},
            {"code": "6300", "name": "Depreciation Expense", "type": "Expense", "active": True},
            {"code": "6400", "name": "Computer & IT Expense", "type": "Expense", "active": True},
            {"code": "6500", "name": "Professional Fees", "type": "Expense", "active": True},
            {"code": "6600", "name": "Travel & Entertainment", "type": "Expense", "active": True},
            {"code": "6700", "name": "VAT Input", "type": "Asset", "active": True},
            {"code": "7000", "name": "Income Tax Expense", "type": "Expense", "active": True},
        ]

    def push_journal_entry(self, entry: JournalEntry) -> dict:
        import uuid
        fake_id = str(uuid.uuid4())[:8].upper()
        self.journal_entries.append({"id": fake_id, "entry": entry})
        print(f"[MockAdapter] Journal entry posted: {fake_id} — {entry.description}")
        return {"success": True, "system_id": fake_id, "message": f"Mock journal entry posted: {fake_id}"}

    def get_chart_of_accounts(self, tenant_id: str) -> list[dict]:
        return self._coa

    def get_vendor(self, vendor_name: str, tenant_id: str) -> Optional[dict]:
        return {"id": "V001", "name": vendor_name, "email": "", "terms": "Net 30"}

    def get_account_balance(self, account_code: str) -> float:
        # Simulate QBO 1200 Inventory balance — intentionally slightly off from
        # Fishbowl total to trigger the sync discrepancy check
        mock_balances = {
            "1200": 27_456.00,   # Fishbowl total (excl. manual) = 27,189.00 → gap of $267
            "1100": 48_320.00,
            "2000": 21_840.00,
        }
        return mock_balances.get(account_code, 0.0)

    def get_ar_aging(self) -> dict:
        return {
            "current": 18_400.00,
            "1_30":    15_200.00,
            "31_60":    8_750.00,
            "61_90":    3_200.00,
            "over_90":  2_770.00,
            "total":   48_320.00,
        }

    def get_ap_aging(self) -> dict:
        return {
            "current":  8_400.00,
            "1_30":     7_200.00,
            "31_60":    4_240.00,
            "61_90":    1_500.00,
            "over_90":    500.00,
            "total":   21_840.00,
        }

    def get_trial_balance(self) -> list[dict]:
        return [
            {"account": "Cash — Operating Account",  "debit": 24_800.00, "credit": 0},
            {"account": "Accounts Receivable",        "debit": 48_320.00, "credit": 0},
            {"account": "Factoring Reserve Account",  "debit":  4_200.00, "credit": 0},
            {"account": "Inventory",                  "debit": 27_456.00, "credit": 0},
            {"account": "Accounts Payable",           "debit": 0, "credit": 21_840.00},
            {"account": "Loans Payable",              "debit": 0, "credit": 35_000.00},
            {"account": "Product Sales Revenue",      "debit": 0, "credit": 94_200.00},
            {"account": "Cost of Goods Sold",         "debit": 38_200.00, "credit": 0},
            {"account": "Contract Labor",             "debit":  6_400.00, "credit": 0},
            {"account": "Software & Subscriptions",   "debit":  1_240.00, "credit": 0},
            {"account": "Factoring Fees",             "debit":  1_884.00, "credit": 0},
        ]

    def get_open_invoices(self, customer_name: Optional[str] = None) -> list[dict]:
        invoices = [
            {"invoice_id": "INV-201", "customer": "Sunrise Senior Living",
             "date": "2026-04-18", "due_date": "2026-05-18",
             "amount": 1_840.00, "balance": 1_840.00, "ref": "INV-2026-201"},
            {"invoice_id": "INV-202", "customer": "Brookdale Senior Living",
             "date": "2026-04-19", "due_date": "2026-05-19",
             "amount": 3_200.00, "balance": 3_200.00, "ref": "INV-2026-202"},
            # Invoiced but not yet shipped — ASC 606 risk (matches Fishbowl mock)
            {"invoice_id": "INV-205", "customer": "Atria Senior Living",
             "date": "2026-04-21", "due_date": "2026-05-21",
             "amount": 2_650.00, "balance": 2_650.00, "ref": "INV-2026-205"},
        ]
        if customer_name:
            invoices = [i for i in invoices if customer_name.lower() in i["customer"].lower()]
        return invoices

    def get_cogs_balance(self, from_date: str, to_date: str) -> float:
        # Mock QBO COGS — intentionally slightly different from Fishbowl ($250 gap)
        return 38_200.00


# ─────────────────────────────────────────────
# ADAPTER FACTORY
# ─────────────────────────────────────────────

def get_adapter(system: str = "mock", **kwargs) -> AccountingAdapter:
    """
    Factory: returns the correct adapter.
    Swap systems here without touching any agent code.
    """
    adapters = {
        "quickbooks": QuickBooksAdapter,
        "mock": MockAdapter,
    }
    cls = adapters.get(system.lower())
    if not cls:
        raise ValueError(f"Unknown accounting system: {system}. Available: {list(adapters.keys())}")
    return cls(**kwargs) if kwargs else cls()


# ─────────────────────────────────────────────
# SUGGESTION → JOURNAL ENTRY CONVERTER
# ─────────────────────────────────────────────

def suggestion_to_journal_entry(suggestion: dict, tenant_id: str) -> JournalEntry:
    """
    Convert an agent suggestion dict to a JournalEntry ready to push to the adapter.
    Called ONLY after human approval.
    """
    je = suggestion.get("journal_entry", {})
    entries_raw = je.get("entries", [])
    lines = [
        JournalLine(
            account_code=str(e.get("account", "").split("—")[0].strip()),
            account_name=e.get("account", ""),
            debit=e.get("debit"),
            credit=e.get("credit"),
            memo=e.get("memo", ""),
        )
        for e in entries_raw
    ]
    return JournalEntry(
        description=je.get("description", ""),
        date=je.get("date", ""),
        currency=je.get("currency", "USD"),
        reference=suggestion.get("suggestion_id", "")[:21],
        lines=lines,
        tenant_id=tenant_id,
    )
