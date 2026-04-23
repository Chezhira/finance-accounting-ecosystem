"""
Mersi Distribution — Finance Health Check Engine
Pulls data from QBO and Fishbowl, runs a suite of reconciliation and
integrity checks, and returns structured findings for dashboard review.

Runs on demand or on a schedule (weekly before close recommended).
All findings are surfaced as flags — GREEN / AMBER / RED.
Nothing is posted or modified. Read-only audit pass.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional

from adapters.fishbowl_adapter import FishbowlAdapter, get_fishbowl_adapter
from adapters.accounting_adapter import AccountingAdapter, get_adapter

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# RESULT STRUCTURES
# ─────────────────────────────────────────────

@dataclass
class CheckResult:
    check_name: str
    status: str          # GREEN | AMBER | RED
    summary: str
    detail: str
    value_at_risk: float = 0.0
    action_required: str = ""
    data: dict = field(default_factory=dict)

@dataclass
class HealthCheckReport:
    tenant_id: str
    run_at: str
    period: str
    overall_status: str   # GREEN | AMBER | RED
    checks: list[CheckResult] = field(default_factory=list)
    red_count: int = 0
    amber_count: int = 0
    green_count: int = 0
    total_value_at_risk: float = 0.0

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "run_at": self.run_at,
            "period": self.period,
            "overall_status": self.overall_status,
            "red_count": self.red_count,
            "amber_count": self.amber_count,
            "green_count": self.green_count,
            "total_value_at_risk": self.total_value_at_risk,
            "checks": [
                {
                    "check_name": c.check_name,
                    "status": c.status,
                    "summary": c.summary,
                    "detail": c.detail,
                    "value_at_risk": c.value_at_risk,
                    "action_required": c.action_required,
                    "data": c.data,
                }
                for c in self.checks
            ]
        }


# ─────────────────────────────────────────────
# HEALTH CHECK ENGINE
# ─────────────────────────────────────────────

class MersiHealthCheck:
    """
    Runs all finance integrity checks for Mersi Distribution.
    Compares Fishbowl vs QBO data and flags discrepancies.

    Usage:
        checker = MersiHealthCheck()
        report = checker.run(period="2026-04")
        print(report.to_dict())
    """

    # Thresholds — adjust once real data patterns are known
    INVENTORY_VARIANCE_THRESHOLD = 500.00     # RED if Fishbowl vs QBO gap > $500
    INVENTORY_VARIANCE_AMBER = 100.00         # AMBER if gap > $100
    COGS_VARIANCE_THRESHOLD = 1_000.00        # RED if Fishbowl vs QBO COGS gap > $1,000
    COGS_VARIANCE_AMBER = 250.00
    AP_OVERDUE_RED_DAYS = 60                  # RED if any vendor overdue > 60 days

    def __init__(
        self,
        qbo_adapter: Optional[AccountingAdapter] = None,
        fishbowl_adapter: Optional[FishbowlAdapter] = None,
        qbo_mode: str = "mock",
        fishbowl_mode: str = "mock",
    ):
        self.qbo = qbo_adapter or get_adapter(qbo_mode)
        self.fishbowl = fishbowl_adapter or get_fishbowl_adapter(fishbowl_mode)

    def run(self, period: str = None) -> HealthCheckReport:
        """
        Run all checks. period = "YYYY-MM" (defaults to current month).
        Returns a HealthCheckReport with all findings.
        """
        if not period:
            period = datetime.now().strftime("%Y-%m")

        period_start = f"{period}-01"
        period_end = f"{period}-{self._last_day(period)}"

        logger.info(f"[HealthCheck] Starting Mersi health check — period={period}")

        checks = [
            self._check_inventory_sync(),
            self._check_manual_warehouse_exposure(),
            self._check_negative_inventory(),
            self._check_grni_exposure(),
            self._check_cogs_sync(period, period_start, period_end),
            self._check_revenue_recognition(period_start, period_end),
            self._check_ar_aging(),
            self._check_ap_aging(),
            self._check_factoring_ar_coverage(),
        ]

        red   = sum(1 for c in checks if c.status == "RED")
        amber = sum(1 for c in checks if c.status == "AMBER")
        green = sum(1 for c in checks if c.status == "GREEN")
        total_risk = sum(c.value_at_risk for c in checks)

        if red > 0:
            overall = "RED"
        elif amber > 0:
            overall = "AMBER"
        else:
            overall = "GREEN"

        report = HealthCheckReport(
            tenant_id="mersi_us",
            run_at=datetime.now().isoformat(),
            period=period,
            overall_status=overall,
            checks=checks,
            red_count=red,
            amber_count=amber,
            green_count=green,
            total_value_at_risk=round(total_risk, 2),
        )

        logger.info(f"[HealthCheck] Complete — {overall} | RED:{red} AMBER:{amber} GREEN:{green} | Risk:${total_risk:,.2f}")
        return report

    # ─────────────────────────────────────────
    # INDIVIDUAL CHECKS
    # ─────────────────────────────────────────

    def _check_inventory_sync(self) -> CheckResult:
        """
        Compare Fishbowl total inventory value (excl. manual warehouses)
        against QBO account 1200 balance. Flag any gap.
        """
        fishbowl_value = self.fishbowl.get_total_inventory_value(exclude_manual_warehouses=True)
        qbo_value = self.qbo.get_account_balance("1200")
        gap = abs(fishbowl_value - qbo_value)

        if gap > self.INVENTORY_VARIANCE_THRESHOLD:
            status = "RED"
            summary = f"Fishbowl vs QBO inventory gap of ${gap:,.2f} — sync failure likely"
            action = "Investigate Fishbowl → QBO sync log. Check for failed postings or timing delays. Do not close books until resolved."
        elif gap > self.INVENTORY_VARIANCE_AMBER:
            status = "AMBER"
            summary = f"Minor Fishbowl vs QBO inventory variance of ${gap:,.2f} — monitor"
            action = "Review recent Fishbowl sync activity. Likely a timing difference — verify by end of day."
        else:
            status = "GREEN"
            summary = f"Fishbowl and QBO inventory in sync (gap ${gap:,.2f})"
            action = ""

        return CheckResult(
            check_name="Inventory Sync — Fishbowl vs QBO",
            status=status,
            summary=summary,
            detail=f"Fishbowl (excl. manual warehouses): ${fishbowl_value:,.2f} | QBO Account 1200: ${qbo_value:,.2f} | Gap: ${gap:,.2f}",
            value_at_risk=gap,
            action_required=action,
            data={"fishbowl_value": fishbowl_value, "qbo_value": qbo_value, "gap": gap}
        )

    def _check_manual_warehouse_exposure(self) -> CheckResult:
        """
        Calculate total inventory value sitting in manual warehouses
        (not tracked by Fishbowl). This is uncontrolled inventory exposure.
        """
        all_items = self.fishbowl.get_inventory_valuation()
        manual_items = [i for i in all_items if i.is_manual_warehouse]
        manual_value = sum(i.total_value for i in manual_items)
        by_location = {}
        for item in manual_items:
            by_location[item.warehouse] = round(
                by_location.get(item.warehouse, 0) + item.total_value, 2
            )

        if manual_value > 5_000:
            status = "RED"
            summary = f"${manual_value:,.2f} in manual warehouses with no system controls"
            action = "Schedule physical count for manual warehouse locations. Verify book values match physical stock."
        elif manual_value > 1_000:
            status = "AMBER"
            summary = f"${manual_value:,.2f} in manual warehouses — monitor closely"
            action = "Confirm last physical count date for manual locations. Flag for next count cycle."
        else:
            status = "GREEN"
            summary = f"Manual warehouse exposure low at ${manual_value:,.2f}"
            action = ""

        return CheckResult(
            check_name="Manual Warehouse Exposure",
            status=status,
            summary=summary,
            detail=f"Manual warehouse total: ${manual_value:,.2f} | Locations: {by_location}",
            value_at_risk=manual_value,
            action_required=action,
            data={"manual_value": manual_value, "by_location": by_location}
        )

    def _check_negative_inventory(self) -> CheckResult:
        """
        Flag any SKU/location with negative quantity on hand.
        Negative inventory = sales posted against non-existent stock.
        """
        negative = self.fishbowl.get_negative_inventory()
        total_exposure = sum(i.exposure for i in negative)

        if negative:
            items_detail = [
                f"{i.part_number} ({i.description}) @ {i.location}: qty {i.quantity:,.0f} | exposure ${i.exposure:,.2f}"
                for i in negative
            ]
            return CheckResult(
                check_name="Negative Inventory",
                status="RED",
                summary=f"{len(negative)} SKU(s) with negative inventory — total exposure ${total_exposure:,.2f}",
                detail=" | ".join(items_detail),
                value_at_risk=total_exposure,
                action_required="Investigate immediately. Negative inventory usually means a sales order was shipped against stock that wasn't received, or a receiving error. COGS is overstated until resolved.",
                data={"items": [{"part": i.part_number, "qty": i.quantity, "exposure": i.exposure} for i in negative]}
            )

        return CheckResult(
            check_name="Negative Inventory",
            status="GREEN",
            summary="No negative inventory detected",
            detail="All SKUs have non-negative quantity on hand",
        )

    def _check_grni_exposure(self) -> CheckResult:
        """
        Goods Received Not Invoiced — received in Fishbowl but no
        Bill.com invoice yet. These are unrecorded AP liabilities.
        """
        grni_items = self.fishbowl.get_open_pos(grni_only=True)
        total_exposure = sum(
            p.qty_received * p.unit_cost for p in grni_items
        )

        if not grni_items:
            return CheckResult(
                check_name="GRNI — Unrecorded AP Liabilities",
                status="GREEN",
                summary="No GRNI items detected",
                detail="All received goods have matching invoices in Bill.com",
            )

        items_detail = [
            f"PO {p.po_number} | {p.vendor_name} | {p.description} | received {p.qty_received:,.0f} units | est. ${p.qty_received * p.unit_cost:,.2f}"
            for p in grni_items
        ]
        status = "RED" if total_exposure > 2_000 else "AMBER"

        return CheckResult(
            check_name="GRNI — Unrecorded AP Liabilities",
            status=status,
            summary=f"{len(grni_items)} GRNI item(s) — ${total_exposure:,.2f} unrecorded AP liability",
            detail=" | ".join(items_detail),
            value_at_risk=total_exposure,
            action_required="Chase invoices from vendors for received goods. Accrue the liability in QBO if invoice won't arrive before close.",
            data={"grni_count": len(grni_items), "total_exposure": total_exposure}
        )

    def _check_cogs_sync(self, period: str, from_date: str, to_date: str) -> CheckResult:
        """
        Compare COGS posted by Fishbowl vs COGS balance in QBO for the period.
        """
        fishbowl_cogs = self.fishbowl.get_cogs_by_period(period).total_cogs
        qbo_cogs = self.qbo.get_cogs_balance(from_date, to_date)
        gap = abs(fishbowl_cogs - qbo_cogs)

        if gap > self.COGS_VARIANCE_THRESHOLD:
            status = "RED"
            summary = f"COGS variance of ${gap:,.2f} between Fishbowl and QBO"
            action = "Investigate Fishbowl COGS sync. Check for unposted shipments or manual COGS adjustments in QBO. Gross margin is unreliable until resolved."
        elif gap > self.COGS_VARIANCE_AMBER:
            status = "AMBER"
            summary = f"Minor COGS variance of ${gap:,.2f} — likely timing difference"
            action = "Review recent Fishbowl shipment postings. Confirm all shipments in period have synced to QBO."
        else:
            status = "GREEN"
            summary = f"COGS in sync between Fishbowl and QBO (gap ${gap:,.2f})"
            action = ""

        return CheckResult(
            check_name="COGS Sync — Fishbowl vs QBO",
            status=status,
            summary=summary,
            detail=f"Fishbowl COGS: ${fishbowl_cogs:,.2f} | QBO COGS: ${qbo_cogs:,.2f} | Gap: ${gap:,.2f}",
            value_at_risk=gap,
            action_required=action,
            data={"fishbowl_cogs": fishbowl_cogs, "qbo_cogs": qbo_cogs, "gap": gap}
        )

    def _check_revenue_recognition(self, from_date: str, to_date: str) -> CheckResult:
        """
        ASC 606 check — flag invoices raised in QBO where Fishbowl
        shows the order has not yet shipped. Revenue recognised too early.
        """
        shipped = self.fishbowl.get_shipped_orders(from_date, to_date)
        shipped_refs = {o["invoice_ref"] for o in shipped if o.get("ship_date")}
        open_invoices = self.qbo.get_open_invoices()

        premature = [
            inv for inv in open_invoices
            if inv["ref"] not in shipped_refs
        ]
        total_exposure = sum(i["amount"] for i in premature)

        if premature:
            items_detail = [
                f"{i['ref']} | {i['customer']} | ${i['amount']:,.2f}"
                for i in premature
            ]
            status = "RED" if total_exposure > 1_000 else "AMBER"
            return CheckResult(
                check_name="Revenue Recognition — ASC 606",
                status=status,
                summary=f"{len(premature)} invoice(s) raised but not yet shipped — ${total_exposure:,.2f} at risk",
                detail=" | ".join(items_detail),
                value_at_risk=total_exposure,
                action_required="Verify shipment status for flagged invoices. If goods have not shipped, revenue should not be recognised. Reverse or defer until shipment confirmed.",
                data={"premature_invoices": premature}
            )

        return CheckResult(
            check_name="Revenue Recognition — ASC 606",
            status="GREEN",
            summary="All invoiced orders confirmed shipped — revenue recognition clean",
            detail="Every open invoice in QBO has a corresponding shipped order in Fishbowl",
        )

    def _check_ar_aging(self) -> CheckResult:
        """
        Flag AR over 90 days — these may have lost SouthStar factoring
        eligibility and represent collection risk.
        """
        aging = self.qbo.get_ar_aging()
        over_90 = aging.get("over_90", 0)
        total_ar = aging.get("total", 0)
        pct = (over_90 / total_ar * 100) if total_ar > 0 else 0

        if over_90 > 5_000 or pct > 15:
            status = "RED"
            summary = f"${over_90:,.2f} AR over 90 days ({pct:.1f}% of total) — likely lost factoring eligibility"
            action = "Review 90+ AR in detail. Chase overdue customers. Assess whether bad debt provision is required."
        elif over_90 > 1_000:
            status = "AMBER"
            summary = f"${over_90:,.2f} AR over 90 days — monitor for SouthStar eligibility"
            action = "Confirm SouthStar borrowing base age limit. Flag approaching invoices to Zahidah."
        else:
            status = "GREEN"
            summary = f"AR aging healthy — ${over_90:,.2f} over 90 days"
            action = ""

        return CheckResult(
            check_name="AR Aging — Factoring Eligibility",
            status=status,
            summary=summary,
            detail=f"Current: ${aging.get('current', 0):,.2f} | 1-30: ${aging.get('1_30', 0):,.2f} | 31-60: ${aging.get('31_60', 0):,.2f} | 61-90: ${aging.get('61_90', 0):,.2f} | 90+: ${over_90:,.2f}",
            value_at_risk=over_90,
            action_required=action,
            data=aging
        )

    def _check_ap_aging(self) -> CheckResult:
        """
        Flag overdue AP — vendors with credit terms at risk or already withdrawn.
        """
        aging = self.qbo.get_ap_aging()
        over_60 = aging.get("61_90", 0) + aging.get("over_90", 0)

        if over_60 > 3_000:
            status = "RED"
            summary = f"${over_60:,.2f} AP overdue beyond 60 days — vendor credit terms at risk"
            action = "Prioritise payment of 60+ day vendors. Contact key suppliers to maintain credit terms."
        elif over_60 > 500:
            status = "AMBER"
            summary = f"${over_60:,.2f} AP in 60+ day bucket — monitor vendor relationships"
            action = "Review 60+ day AP. Schedule payment in next payment run."
        else:
            status = "GREEN"
            summary = f"AP aging healthy — ${over_60:,.2f} beyond 60 days"
            action = ""

        return CheckResult(
            check_name="AP Aging — Vendor Credit Terms",
            status=status,
            summary=summary,
            detail=f"Current: ${aging.get('current', 0):,.2f} | 1-30: ${aging.get('1_30', 0):,.2f} | 31-60: ${aging.get('31_60', 0):,.2f} | 61-90: ${aging.get('61_90', 0):,.2f} | 90+: ${aging.get('over_90', 0):,.2f}",
            value_at_risk=over_60,
            action_required=action,
            data=aging
        )

    def _check_factoring_ar_coverage(self) -> CheckResult:
        """
        Estimate how much eligible AR could be factored but hasn't been submitted yet.
        Unsubmitted eligible invoices = cash sitting on the table.
        """
        open_invoices = self.qbo.get_open_invoices()
        aging = self.qbo.get_ar_aging()

        # Eligible = current + 1-30 day (rough proxy — SouthStar age limit TBC)
        eligible_ar = aging.get("current", 0) + aging.get("1_30", 0)
        total_open = sum(i["amount"] for i in open_invoices)
        potential_advance = eligible_ar * 0.80

        if potential_advance > 10_000:
            status = "AMBER"
            summary = f"${potential_advance:,.2f} potential SouthStar advance available from ${eligible_ar:,.2f} eligible AR"
            action = "Verify all eligible invoices are included in the weekly SouthStar submission."
        else:
            status = "GREEN"
            summary = f"SouthStar coverage reasonable — ${potential_advance:,.2f} potential advance"
            action = ""

        return CheckResult(
            check_name="SouthStar — Factoring AR Coverage",
            status=status,
            summary=summary,
            detail=f"Total open AR: ${total_open:,.2f} | Eligible (current+30d): ${eligible_ar:,.2f} | Potential 80% advance: ${potential_advance:,.2f}",
            value_at_risk=0,
            action_required=action,
            data={"eligible_ar": eligible_ar, "potential_advance": potential_advance}
        )

    # ─────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────

    def _last_day(self, period: str) -> str:
        """Return last day of month as string DD."""
        import calendar
        year, month = int(period[:4]), int(period[5:7])
        return str(calendar.monthrange(year, month)[1])
