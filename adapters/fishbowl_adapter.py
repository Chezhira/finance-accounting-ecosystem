"""
Fishbowl Adapter — Finance & Accounting AI Ecosystem
Provides read access to Fishbowl inventory data for reconciliation,
audit checks, and stress testing against QBO.

Live adapter uses the Fishbowl REST API (token auth).
Mock adapter returns realistic fixture data for development/testing.

To activate live mode:
  Set FISHBOWL_HOST, FISHBOWL_PORT, FISHBOWL_USERNAME, FISHBOWL_PASSWORD in .env
  Call get_adapter("fishbowl") in the factory
"""

import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, date

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────

@dataclass
class InventoryItem:
    part_number: str
    description: str
    location: str
    warehouse: str
    quantity_on_hand: float
    unit_cost: float
    total_value: float
    is_manual_warehouse: bool = False   # True for the 2 non-integrated locations

@dataclass
class OpenPO:
    po_number: str
    vendor_name: str
    order_date: str
    expected_date: str
    part_number: str
    description: str
    qty_ordered: float
    qty_received: float
    qty_outstanding: float
    unit_cost: float
    total_value: float
    is_grni: bool = False   # Received but no Bill.com invoice yet

@dataclass
class COGSSummary:
    period: str           # YYYY-MM
    total_cogs: float
    by_category: dict = field(default_factory=dict)

@dataclass
class NegativeInventoryItem:
    part_number: str
    description: str
    location: str
    quantity: float       # negative number
    unit_cost: float
    exposure: float       # abs(quantity * unit_cost)


# ─────────────────────────────────────────────
# BASE ADAPTER
# ─────────────────────────────────────────────

class FishbowlAdapter(ABC):
    """
    Read-only interface for Fishbowl data.
    Used for reconciliation and audit checks — never writes to Fishbowl.
    """

    @abstractmethod
    def get_inventory_valuation(self, warehouse: Optional[str] = None) -> list[InventoryItem]:
        """
        Full inventory valuation — qty on hand × unit cost per SKU per location.
        Optionally filter by warehouse name.
        """

    @abstractmethod
    def get_total_inventory_value(self, exclude_manual_warehouses: bool = False) -> float:
        """
        Sum of all inventory values. Used to compare against QBO account 1200.
        exclude_manual_warehouses=True returns only Fishbowl-tracked locations.
        """

    @abstractmethod
    def get_open_pos(self, grni_only: bool = False) -> list[OpenPO]:
        """
        Open purchase orders. grni_only=True returns only items received
        but not yet invoiced (Goods Received Not Invoiced exposure).
        """

    @abstractmethod
    def get_cogs_by_period(self, period: str) -> COGSSummary:
        """
        COGS summary for a given period (YYYY-MM).
        Used to compare against QBO COGS account.
        """

    @abstractmethod
    def get_negative_inventory(self) -> list[NegativeInventoryItem]:
        """
        All SKUs/locations where quantity on hand < 0.
        Negative inventory = sales posted against non-existent stock.
        """

    @abstractmethod
    def get_inventory_by_location(self) -> dict[str, float]:
        """
        Total inventory value grouped by warehouse/location name.
        Used to assess manual warehouse exposure.
        """

    @abstractmethod
    def get_shipped_orders(self, from_date: str, to_date: str) -> list[dict]:
        """
        Sales orders with shipment confirmation in date range.
        Used for revenue recognition cross-check and SouthStar submission.
        Returns list of {so_number, customer, ship_date, invoice_ref, tracking_number, value}
        """


# ─────────────────────────────────────────────
# LIVE ADAPTER — Fishbowl REST API
# ─────────────────────────────────────────────

class LiveFishbowlAdapter(FishbowlAdapter):
    """
    Connects to Fishbowl via its REST API.
    Fishbowl API docs: https://help.fishbowlinventory.com/hc/en-us/articles/360045817511
    Auth: POST /api/login → returns token → pass as Bearer in subsequent calls.

    Credentials via env vars:
      FISHBOWL_HOST       e.g. localhost or 192.168.x.x
      FISHBOWL_PORT       default 28080
      FISHBOWL_USERNAME
      FISHBOWL_PASSWORD
      FISHBOWL_MANUAL_WAREHOUSES  comma-separated warehouse names not in Fishbowl
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.host = host or os.environ.get("FISHBOWL_HOST", "localhost")
        self.port = port or int(os.environ.get("FISHBOWL_PORT", "28080"))
        self.username = username or os.environ.get("FISHBOWL_USERNAME", "")
        self.password = password or os.environ.get("FISHBOWL_PASSWORD", "")
        self._token: Optional[str] = None
        self._manual_warehouses = [
            w.strip() for w in
            os.environ.get("FISHBOWL_MANUAL_WAREHOUSES", "").split(",")
            if w.strip()
        ]
        self.base_url = f"http://{self.host}:{self.port}/api"

    def _get_token(self) -> str:
        """Authenticate and return bearer token."""
        try:
            import requests
            resp = requests.post(
                f"{self.base_url}/login",
                json={"username": self.username, "password": self.password},
                timeout=10
            )
            resp.raise_for_status()
            self._token = resp.json().get("token", "")
            return self._token
        except Exception as e:
            logger.error(f"[Fishbowl] Auth failed: {e}")
            raise

    def _headers(self) -> dict:
        if not self._token:
            self._get_token()
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json"
        }

    def _get(self, endpoint: str, params: dict = None) -> dict:
        try:
            import requests
            resp = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self._headers(),
                params=params or {},
                timeout=15
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"[Fishbowl] GET {endpoint} failed: {e}")
            return {}

    def get_inventory_valuation(self, warehouse: Optional[str] = None) -> list[InventoryItem]:
        data = self._get("/inventory/quantity", params={"warehouse": warehouse} if warehouse else {})
        items = []
        for row in data.get("items", []):
            items.append(InventoryItem(
                part_number=row.get("partNumber", ""),
                description=row.get("description", ""),
                location=row.get("location", ""),
                warehouse=row.get("warehouse", ""),
                quantity_on_hand=float(row.get("qtyOnHand", 0)),
                unit_cost=float(row.get("unitCost", 0)),
                total_value=float(row.get("qtyOnHand", 0)) * float(row.get("unitCost", 0)),
                is_manual_warehouse=row.get("warehouse", "") in self._manual_warehouses
            ))
        return items

    def get_total_inventory_value(self, exclude_manual_warehouses: bool = False) -> float:
        items = self.get_inventory_valuation()
        if exclude_manual_warehouses:
            items = [i for i in items if not i.is_manual_warehouse]
        return sum(i.total_value for i in items)

    def get_open_pos(self, grni_only: bool = False) -> list[OpenPO]:
        data = self._get("/purchaseorder", params={"status": "open"})
        pos = []
        for po in data.get("purchaseOrders", []):
            for item in po.get("items", []):
                qty_ordered = float(item.get("qtyOrdered", 0))
                qty_received = float(item.get("qtyReceived", 0))
                qty_outstanding = qty_ordered - qty_received
                is_grni = qty_received > 0 and not item.get("invoiceReceived", False)
                if grni_only and not is_grni:
                    continue
                pos.append(OpenPO(
                    po_number=po.get("poNumber", ""),
                    vendor_name=po.get("vendorName", ""),
                    order_date=po.get("orderDate", ""),
                    expected_date=po.get("expectedDate", ""),
                    part_number=item.get("partNumber", ""),
                    description=item.get("description", ""),
                    qty_ordered=qty_ordered,
                    qty_received=qty_received,
                    qty_outstanding=qty_outstanding,
                    unit_cost=float(item.get("unitCost", 0)),
                    total_value=qty_outstanding * float(item.get("unitCost", 0)),
                    is_grni=is_grni
                ))
        return pos

    def get_cogs_by_period(self, period: str) -> COGSSummary:
        data = self._get("/reports/cogs", params={"period": period})
        return COGSSummary(
            period=period,
            total_cogs=float(data.get("totalCogs", 0)),
            by_category=data.get("byCategory", {})
        )

    def get_negative_inventory(self) -> list[NegativeInventoryItem]:
        items = self.get_inventory_valuation()
        return [
            NegativeInventoryItem(
                part_number=i.part_number,
                description=i.description,
                location=i.location,
                quantity=i.quantity_on_hand,
                unit_cost=i.unit_cost,
                exposure=abs(i.quantity_on_hand * i.unit_cost)
            )
            for i in items if i.quantity_on_hand < 0
        ]

    def get_inventory_by_location(self) -> dict[str, float]:
        items = self.get_inventory_valuation()
        result = {}
        for item in items:
            key = item.warehouse
            result[key] = result.get(key, 0) + item.total_value
        return result

    def get_shipped_orders(self, from_date: str, to_date: str) -> list[dict]:
        data = self._get("/salesorder/shipped", params={"from": from_date, "to": to_date})
        return [
            {
                "so_number": so.get("soNumber", ""),
                "customer": so.get("customerName", ""),
                "ship_date": so.get("shipDate", ""),
                "invoice_ref": so.get("invoiceRef", ""),
                "tracking_number": so.get("trackingNumber", ""),
                "value": float(so.get("totalValue", 0))
            }
            for so in data.get("orders", [])
        ]


# ─────────────────────────────────────────────
# MOCK ADAPTER — realistic Mersi fixture data
# ─────────────────────────────────────────────

class MockFishbowlAdapter(FishbowlAdapter):
    """
    Returns realistic fixture data for Mersi Distribution.
    Includes intentional issues for testing the health check:
      - One negative inventory item
      - Two GRNI items
      - Manual warehouse exposure
      - Inventory value slightly mismatched with QBO (sync lag)
    """

    MANUAL_WAREHOUSES = ["Warehouse C - Manual", "Warehouse D - Manual"]

    def get_inventory_valuation(self, warehouse: Optional[str] = None) -> list[InventoryItem]:
        items = [
            # Fishbowl-connected warehouses
            InventoryItem("MED-001", "Disposable Gloves (Box/100)", "Aisle A1", "Warehouse A", 450, 8.50, 3825.00),
            InventoryItem("MED-002", "Surgical Masks (Box/50)", "Aisle A2", "Warehouse A", 320, 12.00, 3840.00),
            InventoryItem("MED-003", "Wound Dressing Kit", "Aisle B1", "Warehouse A", 180, 24.75, 4455.00),
            InventoryItem("MED-004", "Hand Sanitizer 1L", "Aisle B2", "Warehouse A", 600, 5.20, 3120.00),
            InventoryItem("MED-005", "Incontinence Pads (Pack/20)", "Aisle C1", "Warehouse B", 275, 18.00, 4950.00),
            InventoryItem("MED-006", "Compression Stockings", "Aisle C2", "Warehouse B", 140, 32.00, 4480.00),
            InventoryItem("MED-007", "Blood Pressure Monitor", "Aisle D1", "Warehouse B", 55, 45.00, 2475.00),
            # Negative inventory — intentional issue for health check
            InventoryItem("MED-008", "Pulse Oximeter", "Aisle D2", "Warehouse B", -12, 38.00, -456.00),
            # Manual warehouses — not in Fishbowl proper
            InventoryItem("MED-001", "Disposable Gloves (Box/100)", "Shelf 1", "Warehouse C - Manual", 80, 8.50, 680.00, is_manual_warehouse=True),
            InventoryItem("MED-003", "Wound Dressing Kit", "Shelf 2", "Warehouse C - Manual", 40, 24.75, 990.00, is_manual_warehouse=True),
            InventoryItem("MED-005", "Incontinence Pads (Pack/20)", "Bay 1", "Warehouse D - Manual", 60, 18.00, 1080.00, is_manual_warehouse=True),
        ]
        if warehouse:
            items = [i for i in items if i.warehouse == warehouse]
        return items

    def get_total_inventory_value(self, exclude_manual_warehouses: bool = False) -> float:
        items = self.get_inventory_valuation()
        if exclude_manual_warehouses:
            items = [i for i in items if not i.is_manual_warehouse]
        return round(sum(i.total_value for i in items), 2)

    def get_open_pos(self, grni_only: bool = False) -> list[OpenPO]:
        pos = [
            # Normal open PO — not yet received
            OpenPO("PO-2026-041", "MedSupply Co", "2026-04-10", "2026-04-28",
                   "MED-001", "Disposable Gloves (Box/100)", 500, 0, 500, 8.50, 4250.00, is_grni=False),
            # GRNI — received but no invoice in Bill.com yet
            OpenPO("PO-2026-038", "GlobalMed Imports", "2026-04-05", "2026-04-20",
                   "MED-006", "Compression Stockings", 200, 200, 0, 32.00, 0.00, is_grni=True),
            # GRNI — partially received, partial GRNI
            OpenPO("PO-2026-039", "Pacific Health Supply", "2026-04-08", "2026-04-22",
                   "MED-003", "Wound Dressing Kit", 300, 180, 120, 24.75, 2970.00, is_grni=True),
        ]
        if grni_only:
            pos = [p for p in pos if p.is_grni]
        return pos

    def get_cogs_by_period(self, period: str) -> COGSSummary:
        # Simulate April 2026 COGS
        return COGSSummary(
            period=period,
            total_cogs=38_450.00,
            by_category={
                "Disposable/PPE": 12_200.00,
                "Wound Care": 8_750.00,
                "Hygiene/Continence": 9_500.00,
                "Monitoring Equipment": 8_000.00,
            }
        )

    def get_negative_inventory(self) -> list[NegativeInventoryItem]:
        items = self.get_inventory_valuation()
        return [
            NegativeInventoryItem(
                part_number=i.part_number,
                description=i.description,
                location=i.location,
                quantity=i.quantity_on_hand,
                unit_cost=i.unit_cost,
                exposure=abs(i.quantity_on_hand * i.unit_cost)
            )
            for i in items if i.quantity_on_hand < 0
        ]

    def get_inventory_by_location(self) -> dict[str, float]:
        items = self.get_inventory_valuation()
        result = {}
        for item in items:
            key = item.warehouse
            result[key] = round(result.get(key, 0) + item.total_value, 2)
        return result

    def get_shipped_orders(self, from_date: str, to_date: str) -> list[dict]:
        return [
            {"so_number": "SO-2026-201", "customer": "Sunrise Senior Living",
             "ship_date": "2026-04-18", "invoice_ref": "INV-2026-201",
             "tracking_number": "1Z999AA10123456784", "value": 1_840.00},
            {"so_number": "SO-2026-202", "customer": "Brookdale Senior Living",
             "ship_date": "2026-04-19", "invoice_ref": "INV-2026-202",
             "tracking_number": "1Z999AA10123456785", "value": 3_200.00},
            # Intentional issue: invoiced in QBO but not yet shipped — ASC 606 risk
            {"so_number": "SO-2026-205", "customer": "Atria Senior Living",
             "ship_date": None, "invoice_ref": "INV-2026-205",
             "tracking_number": None, "value": 2_650.00},
        ]


# ─────────────────────────────────────────────
# FACTORY
# ─────────────────────────────────────────────

def get_fishbowl_adapter(mode: str = "mock") -> FishbowlAdapter:
    """
    Factory: returns live or mock Fishbowl adapter.
    mode = "live" requires FISHBOWL_HOST, FISHBOWL_USERNAME, FISHBOWL_PASSWORD in .env
    """
    if mode.lower() == "live":
        return LiveFishbowlAdapter()
    return MockFishbowlAdapter()
