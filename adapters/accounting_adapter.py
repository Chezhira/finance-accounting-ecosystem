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
