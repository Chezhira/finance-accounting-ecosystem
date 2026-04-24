"""
Mersi Distribution — Weekly Finance Health Report
===================================================
Runs the 9-point finance health check against QBO + Fishbowl,
renders a clean HTML report, and emails it to the configured recipients.

Usage:
    python reports/weekly_health_report.py               # current month, mock data
    python reports/weekly_health_report.py --live        # live QBO + Fishbowl
    python reports/weekly_health_report.py --period 2026-04 --live

Schedule: every Friday 7 AM EAT — gives Zahidah the report before the
Miami work day starts, so she can review before sharing with Faris.

To switch from mock to live:
    1.  Set ACCOUNTING_SYSTEM=quickbooks in .env
    2.  Fill in QB_* and FISHBOWL_* credentials
    3.  Run with --live  (or set REPORT_MODE=live in .env)

Nothing is posted or modified. Read-only.
"""

import argparse
import os
import smtplib
import sys
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ── path setup so this script runs from any working directory ──────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from audits.mersi_health_check import MersiHealthCheck, HealthCheckReport

# ── colour palette ─────────────────────────────────────────────────────────
COLORS = {
    "RED":   {"bg": "#FDEDED", "border": "#E53935", "badge_bg": "#E53935", "badge_text": "#FFFFFF", "dot": "#E53935"},
    "AMBER": {"bg": "#FFF8E1", "border": "#F9A825", "badge_bg": "#F9A825", "badge_text": "#000000", "dot": "#F9A825"},
    "GREEN": {"bg": "#E8F5E9", "border": "#43A047", "badge_bg": "#43A047", "badge_text": "#FFFFFF", "dot": "#43A047"},
}

STATUS_LABEL = {"RED": "🔴 Action Required", "AMBER": "⚠️ Monitor", "GREEN": "✅ Clear"}
STATUS_WORD  = {"RED": "RED",                 "AMBER": "AMBER",      "GREEN": "GREEN"}


# ─────────────────────────────────────────────────────────────────────────────
# HTML RENDERER
# ─────────────────────────────────────────────────────────────────────────────

def _risk_line(value_at_risk: float, border_color: str, risk_str: str) -> str:
    if value_at_risk == 0:
        return ""
    return (
        '<div style="margin-top:8px;font-size:13px;color:#555;">'
        'Total value at risk this week: '
        f'<strong style="color:{border_color};">{risk_str}</strong>'
        '</div>'
    )


def render_html(report: HealthCheckReport) -> str:
    week_of    = datetime.now().strftime("%-d %B %Y")
    run_time   = datetime.now().strftime("%A, %-d %b %Y at %H:%M EAT")
    oc         = COLORS[report.overall_status]
    risk_str   = f"${report.total_value_at_risk:,.0f}" if report.total_value_at_risk else "$0"

    # ── summary banner ────────────────────────────────────────────────────
    if report.overall_status == "RED":
        banner_msg = (
            f"<strong>{report.red_count} item{'s' if report.red_count != 1 else ''} "
            f"need{'s' if report.red_count == 1 else ''} immediate attention</strong> — "
            f"review the findings below and action before close."
        )
    elif report.overall_status == "AMBER":
        banner_msg = (
            f"<strong>{report.amber_count} item{'s' if report.amber_count != 1 else ''} to monitor</strong> — "
            f"no immediate action required, but keep an eye on the flagged areas."
        )
    else:
        banner_msg = "<strong>Everything looks clean this week.</strong> All nine checks passed."

    # ── individual check cards ─────────────────────────────────────────────
    cards_html = ""
    for c in report.checks:
        col    = COLORS[c.status]
        action = ""
        if c.action_required:
            action = f"""
            <div style="margin-top:10px;padding:10px 14px;background:#FAFAFA;
                        border-left:3px solid {col['border']};border-radius:3px;
                        font-size:13px;color:#333;">
              <strong>Action:</strong> {c.action_required}
            </div>"""

        risk_badge = ""
        if c.value_at_risk and c.value_at_risk > 0:
            risk_badge = (
                f'<span style="margin-left:12px;padding:2px 10px;border-radius:12px;'
                f'background:#F3F3F3;font-size:12px;color:#555;">'
                f'${c.value_at_risk:,.0f} at risk</span>'
            )

        cards_html += f"""
        <div style="margin-bottom:14px;border:1px solid {col['border']};
                    border-left:4px solid {col['border']};border-radius:6px;
                    background:{col['bg']};padding:14px 18px;">
          <div style="display:flex;align-items:center;justify-content:space-between;
                      flex-wrap:wrap;gap:6px;">
            <div style="font-size:14px;font-weight:600;color:#111;">
              {c.check_name}
            </div>
            <div>
              <span style="padding:3px 10px;border-radius:12px;font-size:12px;font-weight:700;
                           background:{col['badge_bg']};color:{col['badge_text']};">
                {STATUS_WORD[c.status]}
              </span>
              {risk_badge}
            </div>
          </div>
          <p style="margin:8px 0 4px;font-size:13px;color:#222;">{c.summary}</p>
          <p style="margin:0;font-size:12px;color:#666;">{c.detail}</p>
          {action}
        </div>"""

    # ── scorecard row ──────────────────────────────────────────────────────
    def score_cell(count, status, label):
        col = COLORS[status]
        return f"""
        <td style="width:33%;text-align:center;padding:16px 8px;">
          <div style="font-size:28px;font-weight:700;color:{col['border']};">{count}</div>
          <div style="font-size:12px;color:#666;margin-top:2px;">{label}</div>
        </td>"""

    scorecards = (
        score_cell(report.red_count,   "RED",   "Action Required") +
        score_cell(report.amber_count, "AMBER", "Monitor") +
        score_cell(report.green_count, "GREEN", "Clear")
    )

    # ── footer note ────────────────────────────────────────────────────────
    mode_note = "Live data — QBO + Fishbowl" if "mock" not in str(report.run_at).lower() else "Mock data — switch to live when credentials are ready"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mersi Finance Health — Week of {week_of}</title>
</head>
<body style="margin:0;padding:0;background:#F4F6F9;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#F4F6F9;padding:32px 16px;">
    <tr><td align="center">
      <table width="620" cellpadding="0" cellspacing="0"
             style="max-width:620px;width:100%;background:#FFFFFF;
                    border-radius:8px;overflow:hidden;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08);">

        <!-- HEADER -->
        <tr>
          <td style="background:#1A2F5A;padding:24px 32px;">
            <div style="color:#FFFFFF;font-size:20px;font-weight:700;letter-spacing:0.3px;">
              Mersi Distribution
            </div>
            <div style="color:#A8C0E8;font-size:13px;margin-top:4px;">
              Weekly Finance Health Check — Week of {week_of}
            </div>
          </td>
        </tr>

        <!-- OVERALL STATUS BANNER -->
        <tr>
          <td style="background:{oc['bg']};border-bottom:3px solid {oc['border']};
                     padding:18px 32px;">
            <div style="display:flex;align-items:center;gap:12px;">
              <span style="font-size:22px;font-weight:800;color:{oc['border']};">
                {report.overall_status}
              </span>
              <span style="font-size:14px;color:#333;">
                {banner_msg}
              </span>
            </div>
            {_risk_line(report.total_value_at_risk, oc['border'], risk_str)}
          </td>
        </tr>

        <!-- SCORECARD -->
        <tr>
          <td style="padding:0 32px;">
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="border-bottom:1px solid #EBEBEB;">
              <tr>{scorecards}</tr>
            </table>
          </td>
        </tr>

        <!-- CHECK RESULTS -->
        <tr>
          <td style="padding:24px 32px 8px;">
            <div style="font-size:15px;font-weight:700;color:#1A2F5A;margin-bottom:16px;">
              Check Results
            </div>
            {cards_html}
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="padding:20px 32px 28px;border-top:1px solid #EBEBEB;">
            <div style="font-size:12px;color:#999;line-height:1.7;">
              Generated: {run_time}<br>
              Period: {report.period}<br>
              Data source: {mode_note}<br>
              <br>
              <strong style="color:#555;">Zahidah Murira</strong><br>
              <span style="color:#999;">Finance · Mersi Distribution</span>
            </div>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    return html


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL SENDER
# ─────────────────────────────────────────────────────────────────────────────

def send_email(html_body: str, report: HealthCheckReport):
    smtp_host = os.environ.get("REPORT_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("REPORT_SMTP_PORT", "587"))
    smtp_user = os.environ.get("REPORT_SMTP_USER", "")
    smtp_pass = os.environ.get("REPORT_SMTP_PASSWORD", "")
    from_addr = os.environ.get("REPORT_FROM_EMAIL", smtp_user)
    from_name = os.environ.get("REPORT_FROM_NAME", "Zahidah Murira")
    to_addr   = os.environ.get("REPORT_TO_EMAIL", smtp_user)
    cc_addr   = os.environ.get("REPORT_CC_EMAIL", "")   # add Faris here when ready

    if not smtp_user or not smtp_pass:
        print("⚠️  Email not configured — REPORT_SMTP_USER / REPORT_SMTP_PASSWORD not set.")
        print("   Report saved to reports/latest_health_report.html instead.")
        return False

    status_tag = {
        "RED":   "🔴 Action Required",
        "AMBER": "⚠️ Monitor",
        "GREEN": "✅ All Clear",
    }[report.overall_status]

    week_of = datetime.now().strftime("%-d %b %Y")
    subject  = f"Mersi Financials — {week_of}  |  {status_tag}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{from_name} <{from_addr}>"
    msg["To"]      = to_addr
    if cc_addr:
        msg["Cc"] = cc_addr

    # Plain text fallback
    plain = (
        f"Mersi Finance Health Check — Week of {week_of}\n\n"
        f"Overall: {report.overall_status}\n"
        f"Red: {report.red_count}  Amber: {report.amber_count}  Green: {report.green_count}\n"
        f"Total value at risk: ${report.total_value_at_risk:,.0f}\n\n"
    )
    for c in report.checks:
        plain += f"[{c.status}] {c.check_name}\n  {c.summary}\n"
        if c.action_required:
            plain += f"  Action: {c.action_required}\n"
        plain += "\n"
    plain += f"\n—\nZahidah Murira | Finance, Mersi Distribution"

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    recipients = [to_addr] + ([cc_addr] if cc_addr else [])

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, recipients, msg.as_string())
        print(f"✅  Email sent → {to_addr}" + (f", {cc_addr}" if cc_addr else ""))
        return True
    except Exception as e:
        print(f"❌  Email failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# SAVE LOCAL COPY
# ─────────────────────────────────────────────────────────────────────────────

def save_local(html_body: str):
    out_dir = ROOT / "reports"
    out_dir.mkdir(exist_ok=True)

    # always overwrite the 'latest' copy
    latest = out_dir / "latest_health_report.html"
    latest.write_text(html_body, encoding="utf-8")

    # also save a dated archive copy
    stamp   = datetime.now().strftime("%Y-%m-%d")
    archive = out_dir / f"health_report_{stamp}.html"
    archive.write_text(html_body, encoding="utf-8")

    print(f"📄  Report saved → {latest}")
    print(f"📦  Archive copy → {archive}")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run and email the Mersi weekly finance health check.")
    parser.add_argument("--period",  default=None,
                        help="Period to check, YYYY-MM (default: current month)")
    parser.add_argument("--live",    action="store_true",
                        help="Use live QBO + Fishbowl credentials (default: mock)")
    parser.add_argument("--no-email", action="store_true",
                        help="Generate report but do not send email")
    args = parser.parse_args()

    # ── load .env if present ───────────────────────────────────────────────
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

    # ── determine mode ─────────────────────────────────────────────────────
    env_mode  = os.environ.get("REPORT_MODE", "mock").lower()
    live_mode = args.live or (env_mode == "live")
    qbo_mode  = "quickbooks" if live_mode else "mock"
    fb_mode   = "live"       if live_mode else "mock"

    period = args.period or datetime.now().strftime("%Y-%m")

    print(f"\n{'='*54}")
    print(f"  Mersi Finance Health Check")
    print(f"  Period : {period}")
    print(f"  Mode   : {'LIVE — QBO + Fishbowl' if live_mode else 'MOCK (safe — no real API calls)'}")
    print(f"{'='*54}\n")

    # ── run health check ───────────────────────────────────────────────────
    checker = MersiHealthCheck(qbo_mode=qbo_mode, fishbowl_mode=fb_mode)
    report  = checker.run(period=period)

    print(f"Overall: {report.overall_status}  |  "
          f"🔴 {report.red_count}  ⚠️ {report.amber_count}  ✅ {report.green_count}  |  "
          f"Value at risk: ${report.total_value_at_risk:,.0f}\n")

    for c in report.checks:
        icon = {"RED": "🔴", "AMBER": "⚠️ ", "GREEN": "✅"}[c.status]
        print(f"  {icon}  {c.check_name}")
        print(f"       {c.summary}")
        if c.action_required:
            print(f"       → {c.action_required}")
        print()

    # ── render ─────────────────────────────────────────────────────────────
    html = render_html(report)
    save_local(html)

    # ── send ───────────────────────────────────────────────────────────────
    if not args.no_email:
        send_email(html, report)
    else:
        print("📭  --no-email set, skipping send.")

    print("\nDone.\n")
    return 0 if report.overall_status != "RED" else 1


if __name__ == "__main__":
    sys.exit(main())
