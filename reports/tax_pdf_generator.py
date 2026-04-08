"""
reports/tax_pdf_generator.py — FinOps Tax PDF Report Generator
==============================================================
Called automatically on every /tax/analyze endpoint call.
Accepts output from either TaxAgentTZ or TaxAgentUS.

Usage:
    from reports.tax_pdf_generator import build_pdf
    build_pdf(result_dict, "reports/tenant_TZ_Q1_20260406_120000.pdf")

Sections:
    1. Header / Executive Summary
    2. Compliance Flags (colour-coded by severity)
    3. Tax Items Table
    4. SE Tax Computation (US only)
    5. Quarterly Estimates (US only)
    6. Journal Entries (with debit/credit balance check)
    7. Compliance Calendar
    8. Strategic Suggestions
    9. Disclaimer Footer
"""

import os
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# ─── Colour palette (dark-professional theme) ─────────────────────────────────
C_BG_DARK    = colors.HexColor("#1A1A2E")
C_BG_MID     = colors.HexColor("#16213E")
C_BG_LIGHT   = colors.HexColor("#0F3460")
C_ACCENT     = colors.HexColor("#E94560")
C_WHITE      = colors.HexColor("#F0F0F0")
C_GREY_LIGHT = colors.HexColor("#CCCCCC")
C_GREY_MID   = colors.HexColor("#888888")

# Severity colours
C_CRITICAL   = colors.HexColor("#FF4444")
C_HIGH       = colors.HexColor("#FF8C00")
C_MEDIUM     = colors.HexColor("#4488FF")
C_LOW        = colors.HexColor("#44BB44")
C_INFO       = colors.HexColor("#888888")

SEVERITY_COLOURS = {
    "CRITICAL": C_CRITICAL,
    "HIGH":     C_HIGH,
    "MEDIUM":   C_MEDIUM,
    "LOW":      C_LOW,
    "INFO":     C_INFO,
}

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


# ─── Styles ───────────────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()
    def s(name, parent="Normal", **kw):
        return ParagraphStyle(name, parent=base[parent], **kw)

    return {
        "title": s("RTitle", fontSize=22, textColor=C_WHITE,
                   fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4),
        "subtitle": s("RSub", fontSize=11, textColor=C_GREY_LIGHT,
                      fontName="Helvetica", alignment=TA_CENTER, spaceAfter=2),
        "section": s("RSec", fontSize=13, textColor=C_ACCENT,
                     fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=6),
        "body": s("RBody", fontSize=9, textColor=C_GREY_LIGHT,
                  fontName="Helvetica", spaceAfter=3, leading=14),
        "body_white": s("RBodyW", fontSize=9, textColor=C_WHITE,
                        fontName="Helvetica", spaceAfter=2, leading=13),
        "mono": s("RMono", fontSize=8, textColor=C_WHITE,
                  fontName="Courier", spaceAfter=2, leading=12),
        "label": s("RLabel", fontSize=8, textColor=C_GREY_MID,
                   fontName="Helvetica-Bold", spaceAfter=1),
        "small": s("RSmall", fontSize=7, textColor=C_GREY_MID,
                   fontName="Helvetica", spaceAfter=2),
        "disclaimer": s("RDisc", fontSize=7, textColor=C_GREY_MID,
                        fontName="Helvetica-Oblique", alignment=TA_CENTER,
                        spaceBefore=6, spaceAfter=2),
        "flag_text": s("RFlag", fontSize=8, textColor=C_WHITE,
                       fontName="Helvetica", leading=12),
        "kv_label": s("RKVLabel", fontSize=8, textColor=C_GREY_MID,
                      fontName="Helvetica-Bold"),
        "kv_value": s("RKVValue", fontSize=9, textColor=C_WHITE,
                      fontName="Helvetica"),
    }


# ─── Table style helpers ───────────────────────────────────────────────────────

def _tbl_style(header_bg=C_BG_LIGHT, row_bg=C_BG_MID, alt_bg=C_BG_DARK):
    return TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0),  header_bg),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  C_WHITE),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0),  8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING",  (0, 0), (-1, 0),  6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [row_bg, alt_bg]),
        ("TEXTCOLOR",   (0, 1), (-1, -1), C_GREY_LIGHT),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 1), (-1, -1), 8),
        ("TOPPADDING",  (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#333355")),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
    ])


def _hr():
    return HRFlowable(width="100%", thickness=0.5, color=C_BG_LIGHT, spaceAfter=6)


# ─── Section builders ─────────────────────────────────────────────────────────

def _header(st, data: dict) -> list:
    jurisdiction = data.get("jurisdiction", data.get("entity_type", "Unknown"))
    tenant_id    = data.get("tenant_id", "")
    period       = data.get("period", data.get("tax_period", ""))
    generated    = datetime.utcnow().strftime("%d %B %Y %H:%M UTC")

    # Header banner table
    header_data = [[
        Paragraph("FinOps Ecosystem", st["subtitle"]),
        Paragraph("TAX ANALYSIS REPORT", st["title"]),
        Paragraph(f"Generated: {generated}", st["subtitle"]),
    ]]
    tbl = Table(header_data, colWidths=[CONTENT_W * 0.25, CONTENT_W * 0.5, CONTENT_W * 0.25])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), C_BG_DARK),
        ("TEXTCOLOR",   (0, 0), (-1, -1), C_WHITE),
        ("ALIGN",       (0, 0), (0, -1),  "LEFT"),
        ("ALIGN",       (1, 0), (1, -1),  "CENTER"),
        ("ALIGN",       (2, 0), (2, -1),  "RIGHT"),
        ("TOPPADDING",  (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))

    # Summary KV row
    summary = data.get("executive_summary", data.get("summary", ""))
    overall = data.get("overall_compliance_status", data.get("compliance_status", ""))
    status_colour = C_CRITICAL if "non" in overall.lower() else (
        C_HIGH if "risk" in overall.lower() else C_LOW
    )

    meta_data = [[
        Paragraph(f"<b>Tenant:</b> {tenant_id}", st["body_white"]),
        Paragraph(f"<b>Jurisdiction:</b> {jurisdiction}", st["body_white"]),
        Paragraph(f"<b>Period:</b> {period}", st["body_white"]),
        Paragraph(f"<b>Status:</b> <font color='#{_hex(status_colour)}'>{overall}</font>",
                  st["body_white"]),
    ]]
    meta_tbl = Table(meta_data, colWidths=[CONTENT_W / 4] * 4)
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), C_BG_MID),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("GRID",        (0, 0), (-1, -1), 0.3, C_BG_LIGHT),
    ]))

    elements = [tbl, Spacer(1, 4)]
    if summary:
        elements += [
            Paragraph(st["section"].name and "EXECUTIVE SUMMARY", st["section"]),
            Paragraph(summary, st["body"]),
        ]
    elements += [meta_tbl, Spacer(1, 6), _hr()]
    return elements


def _hex(colour) -> str:
    """Extract hex string from reportlab colour for inline use."""
    try:
        r, g, b = int(colour.red * 255), int(colour.green * 255), int(colour.blue * 255)
        return f"{r:02X}{g:02X}{b:02X}"
    except Exception:
        return "FFFFFF"


def _compliance_flags(st, data: dict) -> list:
    flags = data.get("compliance_flags", [])
    if not flags:
        return []

    elements = [Paragraph("COMPLIANCE FLAGS", st["section"])]

    for flag in flags:
        if isinstance(flag, str):
            flag = {"severity": "INFO", "message": flag, "action": ""}
        sev     = str(flag.get("severity", "INFO")).upper()
        msg     = flag.get("message", flag.get("description", ""))
        action  = flag.get("action", flag.get("recommendation", ""))
        colour  = SEVERITY_COLOURS.get(sev, C_INFO)

        row = [[
            Paragraph(f"<b>{sev}</b>", st["flag_text"]),
            Paragraph(msg, st["flag_text"]),
            Paragraph(action, st["flag_text"]),
        ]]
        tbl = Table(row, colWidths=[CONTENT_W * 0.10, CONTENT_W * 0.55, CONTENT_W * 0.35])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (0, -1), colour),
            ("BACKGROUND",    (1, 0), (-1, -1), C_BG_MID),
            ("TEXTCOLOR",     (0, 0), (-1, -1), C_WHITE),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("GRID",          (0, 0), (-1, -1), 0.3, C_BG_DARK),
        ]))
        elements.append(KeepTogether([tbl, Spacer(1, 2)]))

    elements.append(_hr())
    return elements


def _tax_items(st, data: dict) -> list:
    items = data.get("tax_items", data.get("tax_calculations", []))
    if not items:
        return []

    elements = [Paragraph("TAX ITEMS", st["section"])]
    rows = [["Description", "Amount", "Currency", "Rate", "Notes"]]
    for item in items:
        if isinstance(item, str):
            rows.append([item, "", "", "", ""])
            continue
        rows.append([
            item.get("description", item.get("name", "")),
            _fmt_num(item.get("amount", item.get("value", ""))),
            item.get("currency", ""),
            item.get("rate", item.get("tax_rate", "")),
            item.get("notes", item.get("note", "")),
        ])

    tbl = Table(rows, colWidths=[CONTENT_W * 0.32, CONTENT_W * 0.15,
                                  CONTENT_W * 0.10, CONTENT_W * 0.10,
                                  CONTENT_W * 0.33])
    tbl.setStyle(_tbl_style())
    elements += [tbl, Spacer(1, 4), _hr()]
    return elements


def _se_tax(st, data: dict) -> list:
    se = data.get("se_tax_computation", {})
    if not se:
        return []

    elements = [Paragraph("SELF-EMPLOYMENT TAX COMPUTATION (US)", st["section"])]
    rows = [["Component", "Amount (USD)"]]
    field_labels = [
        ("net_llc_income",          "Net LLC Income"),
        ("se_net_income",           "SE Net Income (×92.35%)"),
        ("ss_tax",                  "Social Security Tax (12.4%)"),
        ("medicare_tax",            "Medicare Tax (2.9%)"),
        ("additional_medicare",     "Additional Medicare (0.9%)"),
        ("total_se_tax",            "Total SE Tax"),
        ("se_tax_deduction",        "SE Tax Deduction (50%)"),
        ("net_se_tax_after_deduction", "Net SE Tax After Deduction"),
    ]
    for key, label in field_labels:
        if key in se:
            rows.append([label, _fmt_num(se[key])])

    tbl = Table(rows, colWidths=[CONTENT_W * 0.65, CONTENT_W * 0.35])
    style = _tbl_style()
    # Highlight total row
    for i, row in enumerate(rows):
        if "Total" in str(row[0]) and i > 0:
            style.add("FONTNAME", (0, i), (-1, i), "Helvetica-Bold")
            style.add("TEXTCOLOR", (0, i), (-1, i), C_ACCENT)
    tbl.setStyle(style)
    elements += [tbl, Spacer(1, 4), _hr()]
    return elements


def _quarterly_estimates(st, data: dict) -> list:
    qe = data.get("quarterly_estimates", data.get("estimated_quarterly_payments", []))
    if not qe:
        return []

    elements = [Paragraph("QUARTERLY ESTIMATED TAX PAYMENTS (US)", st["section"])]
    rows = [["Quarter", "Due Date", "Federal Tax", "SE Tax", "Total Due", "Status"]]
    for q in qe:
        if isinstance(q, dict):
            rows.append([
                q.get("quarter", ""),
                q.get("due_date", ""),
                _fmt_num(q.get("federal_tax", q.get("federal", ""))),
                _fmt_num(q.get("se_tax", "")),
                _fmt_num(q.get("total_due", q.get("total", ""))),
                q.get("status", q.get("note", "")),
            ])

    tbl = Table(rows, colWidths=[CONTENT_W * 0.08, CONTENT_W * 0.15, CONTENT_W * 0.15,
                                  CONTENT_W * 0.14, CONTENT_W * 0.15, CONTENT_W * 0.33])
    tbl.setStyle(_tbl_style())
    elements += [tbl, Spacer(1, 4), _hr()]
    return elements


def _journal_entries(st, data: dict) -> list:
    je = data.get("journal_entries", data.get("journal_entry", {}))
    if not je:
        return []

    elements = [Paragraph("SUGGESTED JOURNAL ENTRIES", st["section"])]

    # Handle both list-of-entries and single entry dict
    entries = je if isinstance(je, list) else [je]

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        desc = entry.get("description", entry.get("memo", ""))
        date = entry.get("date", entry.get("transaction_date", ""))
        if desc or date:
            elements.append(Paragraph(
                f"<b>{desc}</b>  {f'| Date: {date}' if date else ''}",
                st["body_white"]
            ))

        lines = entry.get("lines", entry.get("line_items", []))
        if lines:
            rows = [["Account", "Debit", "Credit", "Currency", "Notes"]]
            total_dr = 0.0
            total_cr = 0.0
            for line in lines:
                dr = _to_float(line.get("debit", line.get("dr", "")))
                cr = _to_float(line.get("credit", line.get("cr", "")))
                total_dr += dr
                total_cr += cr
                rows.append([
                    line.get("account", line.get("account_name", "")),
                    _fmt_num(dr) if dr else "",
                    _fmt_num(cr) if cr else "",
                    line.get("currency_code", line.get("currency", "")),
                    line.get("notes", line.get("description", "")),
                ])

            # Balance check row
            balanced = abs(total_dr - total_cr) < 0.01
            balance_text = f"✓ BALANCED  DR={_fmt_num(total_dr)}  CR={_fmt_num(total_cr)}" if balanced \
                else f"⚠ UNBALANCED  DR={_fmt_num(total_dr)}  CR={_fmt_num(total_cr)}"
            rows.append(["", _fmt_num(total_dr), _fmt_num(total_cr),
                         "TOTAL →", balance_text])

            tbl = Table(rows, colWidths=[CONTENT_W * 0.30, CONTENT_W * 0.13,
                                          CONTENT_W * 0.13, CONTENT_W * 0.10,
                                          CONTENT_W * 0.34])
            style = _tbl_style()
            last = len(rows) - 1
            style.add("FONTNAME",  (0, last), (-1, last), "Helvetica-Bold")
            style.add("TEXTCOLOR", (0, last), (-1, last),
                      C_LOW if balanced else C_CRITICAL)
            style.add("BACKGROUND", (0, last), (-1, last), C_BG_DARK)
            tbl.setStyle(style)
            elements += [tbl, Spacer(1, 3)]

    elements.append(_hr())
    return elements


def _compliance_calendar(st, data: dict) -> list:
    cal = data.get("compliance_calendar", data.get("key_dates", []))
    if not cal:
        return []

    elements = [Paragraph("COMPLIANCE CALENDAR", st["section"])]

    if isinstance(cal, dict):
        rows = [["Obligation", "Due Date"]]
        for k, v in cal.items():
            rows.append([k.replace("_", " ").title(), str(v)])
    elif isinstance(cal, list):
        rows = [["Obligation", "Due Date", "Notes"]]
        for item in cal:
            if isinstance(item, dict):
                rows.append([
                    item.get("obligation", item.get("description", "")),
                    item.get("due_date", item.get("date", "")),
                    item.get("notes", item.get("note", "")),
                ])
            else:
                rows.append([str(item), "", ""])
    else:
        return []

    tbl = Table(rows, colWidths=[CONTENT_W * 0.40, CONTENT_W * 0.25, CONTENT_W * 0.35])
    tbl.setStyle(_tbl_style())
    elements += [tbl, Spacer(1, 4), _hr()]
    return elements


def _suggestions(st, data: dict) -> list:
    sugg = data.get("strategic_suggestions", data.get("recommendations", []))
    if not sugg:
        return []

    elements = [Paragraph("STRATEGIC SUGGESTIONS", st["section"])]
    for i, s in enumerate(sugg, 1):
        if isinstance(s, dict):
            title  = s.get("title", s.get("area", f"Suggestion {i}"))
            detail = s.get("detail", s.get("description", s.get("action", "")))
            impact = s.get("impact", s.get("priority", ""))
            text   = f"<b>{i}. {title}</b>  {f'[{impact}]' if impact else ''}<br/>{detail}"
        else:
            text = f"<b>{i}.</b> {s}"
        elements.append(Paragraph(text, st["body"]))

    elements.append(_hr())
    return elements


def _disclaimer(st) -> list:
    text = (
        "DISCLAIMER: This report is generated by the FinOps AI Ecosystem and is intended "
        "for review by a qualified human operator before any action is taken. "
        "It does not constitute professional tax, legal, or accounting advice. "
        "All figures and suggestions must be verified against source documents and "
        "applicable regulations by a licensed professional. No final decisions should "
        "be made solely on the basis of this report."
    )
    return [
        _hr(),
        Paragraph(text, st["disclaimer"]),
        Paragraph(
            f"Generated by FinOps Ecosystem v3.1.0  |  {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            st["small"]
        ),
    ]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _fmt_num(val) -> str:
    if val is None or val == "":
        return ""
    try:
        f = float(str(val).replace(",", ""))
        if f == int(f):
            return f"{int(f):,}"
        return f"{f:,.2f}"
    except Exception:
        return str(val)


def _to_float(val) -> float:
    try:
        return float(str(val).replace(",", ""))
    except Exception:
        return 0.0


# ─── Background canvas (dark page colour) ─────────────────────────────────────

def _dark_canvas(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(C_BG_DARK)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # Page number
    canvas.setFillColor(C_GREY_MID)
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(PAGE_W - MARGIN, 8 * mm,
                           f"Page {doc.page}  |  FinOps Ecosystem — Confidential")
    canvas.restoreState()


# ─── Main entry point ─────────────────────────────────────────────────────────

def build_pdf(data: dict, output_path: str) -> str:
    """
    Build a professional dark-themed PDF tax report.

    Args:
        data:        Output dict from TaxAgentTZ.analyze() or TaxAgentUS.analyze()
        output_path: Full path to write the PDF, e.g. "reports/tenant_TZ_Q1_20260406.pdf"

    Returns:
        output_path on success.

    Raises:
        Exception on failure (caller should catch and log).
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=18 * mm,
    )

    st = _styles()

    story = []
    story += _header(st, data)
    story += _compliance_flags(st, data)
    story += _tax_items(st, data)
    story += _se_tax(st, data)
    story += _quarterly_estimates(st, data)
    story += _journal_entries(st, data)
    story += _compliance_calendar(st, data)
    story += _suggestions(st, data)
    story += _disclaimer(st)

    doc.build(story, onFirstPage=_dark_canvas, onLaterPages=_dark_canvas)
    return output_path


# ─── CLI test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Quick smoke test with mock data
    mock = {
        "jurisdiction": "Tanzania",
        "tenant_id": "fintech_tz",
        "period": "Q1 2026",
        "overall_compliance_status": "Compliant with flags",
        "executive_summary": (
            "Q1 2026 tax analysis for Fintech Corp Tanzania. VAT return due 20th April. "
            "One HIGH flag for WHT on imported services requires attention at payment date. "
            "Provisional tax instalment due within 3 months of Q1 end."
        ),
        "compliance_flags": [
            {"severity": "HIGH", "message": "WHT on imported services (Section 83) — 15% due at payment, not accrual.",
             "action": "Set payment reminder. Prepare WHT certificate for TRA."},
            {"severity": "INFO", "message": "VAT return due 20 April 2026.", "action": "File via TRA online portal."},
        ],
        "tax_items": [
            {"description": "Output VAT (Sales)", "amount": 1800000, "currency": "TZS", "rate": "18%", "notes": "Mainland"},
            {"description": "Input VAT (Purchases)", "amount": 450000, "currency": "TZS", "rate": "18%", "notes": "Recoverable"},
            {"description": "VAT Payable", "amount": 1350000, "currency": "TZS", "rate": "", "notes": "Net due to TRA"},
            {"description": "Provisional Tax Q1", "amount": 750000, "currency": "TZS", "rate": "30%", "notes": "Due 31 Mar 2026"},
        ],
        "journal_entries": [{
            "description": "VAT Return — Q1 2026",
            "date": "2026-03-31",
            "lines": [
                {"account": "VAT Control Account", "debit": 1350000, "credit": 0, "currency_code": "TZS", "notes": "Clear VAT payable"},
                {"account": "TRA VAT Payable", "debit": 0, "credit": 1350000, "currency_code": "TZS", "notes": "TRA liability"},
            ],
        }],
        "compliance_calendar": {
            "VAT Return Q1 2026": "20 April 2026",
            "Provisional Tax Q1": "31 March 2026",
            "Audited Accounts FY2025": "30 June 2026",
        },
        "strategic_suggestions": [
            {"title": "WHT Pre-payment Checklist", "impact": "HIGH",
             "detail": "Implement a payment-stage WHT checklist to ensure Section 83 deductions are applied correctly and TRA certificates are issued within 30 days."},
            {"title": "VAT Refund Claim Review", "impact": "MEDIUM",
             "detail": "Review input VAT claims for Q4 2025 — potential refund of TZS 120,000 identified."},
        ],
    }
    out = build_pdf(mock, "/tmp/test_tax_report.pdf")
    print(f"Test PDF generated: {out}")
    print(f"File size: {os.path.getsize(out):,} bytes")
