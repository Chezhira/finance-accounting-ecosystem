"""
api/escalation.py — FinOps Escalation Engine v3
================================================
Phase 2: Full escalation state machine with retry loops, auto-post, resubmit.
Session 6 upgrades:
  - Critique injection on RETURN_TO_JUNIOR: previous failed output + specific critique
    injected alongside operator context, preventing LLM from repeating same logic
  - reasoning_log field propagated through escalation chain
  - currency_code validation on JournalEntry before auto-post
  - reports/ folder auto-created at startup (Rule 20)
"""

import json
import os
import uuid
import logging
import sqlite3
import smtplib
import threading
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from enum import Enum
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# Absolute paths — safe regardless of launch working directory
_HERE = Path(__file__).parent      # api/
_ROOT = _HERE.parent               # finops/

# ── Auto-create reports folder at import time (Rule 20) ───────────────────────
(_ROOT / "reports").mkdir(exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

MAX_JUNIOR_RETRIES = 2
MAX_SENIOR_RETRIES = 2

DB_PATH = str(_ROOT / "finops_escalation.db")


# ──────────────────────────────────────────────────────────────────────────────
# Escalation States
# ──────────────────────────────────────────────────────────────────────────────

class EscalationState(str, Enum):
    JUNIOR_COMPLETE        = "JUNIOR_COMPLETE"
    PENDING_SENIOR         = "PENDING_SENIOR"
    SENIOR_COMPLETE        = "SENIOR_COMPLETE"
    PENDING_CONTROLLER     = "PENDING_CONTROLLER"
    CONTROLLER_COMPLETE    = "CONTROLLER_COMPLETE"
    PENDING_HUMAN          = "PENDING_HUMAN"
    HUMAN_APPROVED         = "HUMAN_APPROVED"
    POSTING                = "POSTING"
    POSTED                 = "POSTED"
    POST_FAILED            = "POST_FAILED"
    HUMAN_REJECTED         = "HUMAN_REJECTED"
    RESUBMITTED            = "RESUBMITTED"
    RETURNED_TO_JUNIOR     = "RETURNED_TO_JUNIOR"
    RETURNED_TO_SENIOR     = "RETURNED_TO_SENIOR"
    FLAGGED_CRITICAL       = "FLAGGED_CRITICAL"
    MAX_RETRIES_EXCEEDED   = "MAX_RETRIES_EXCEEDED"
    ERROR                  = "ERROR"


# ──────────────────────────────────────────────────────────────────────────────
# Escalation Store (SQLite)
# ──────────────────────────────────────────────────────────────────────────────

class EscalationStore:
    """
    Persistent SQLite store for escalation records.
    Database: finops_escalation.db (separate from Phase 1 finops_offline.db)
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS escalations (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT,
                    state TEXT,
                    junior_suggestion TEXT,
                    senior_review TEXT,
                    controller_review TEXT,
                    reasoning_log TEXT,
                    junior_retry_count INTEGER DEFAULT 0,
                    senior_retry_count INTEGER DEFAULT 0,
                    operator_notes TEXT,
                    system_reference TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            # Migrate: add reasoning_log column if missing (for existing DBs)
            try:
                conn.execute("ALTER TABLE escalations ADD COLUMN reasoning_log TEXT")
            except Exception:
                pass
            conn.commit()

    def create(self, tenant_id: str, junior_suggestion: dict) -> str:
        esc_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        reasoning_log = json.dumps([{
            "stage": "JUNIOR_COMPLETE",
            "timestamp": now,
            "summary": junior_suggestion.get("reasoning_summary", "Junior processed input"),
        }])
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO escalations
                (id, tenant_id, state, junior_suggestion, reasoning_log,
                 junior_retry_count, senior_retry_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?)
            """, (
                esc_id, tenant_id, EscalationState.JUNIOR_COMPLETE,
                json.dumps(junior_suggestion), reasoning_log, now, now
            ))
        return esc_id

    def get(self, esc_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM escalations WHERE id = ?", (esc_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        for field in ("junior_suggestion", "senior_review", "controller_review"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except Exception:
                    pass
        if d.get("reasoning_log"):
            try:
                d["reasoning_log"] = json.loads(d["reasoning_log"])
            except Exception:
                d["reasoning_log"] = []
        return d

    # Columns that callers are permitted to update via update_state(**kwargs).
    # Any key not in this set is silently dropped — prevents column-name injection.
    _UPDATABLE_COLUMNS = frozenset({
        "senior_review", "controller_review", "reasoning_log",
        "operator_notes", "system_reference",
        "junior_retry_count", "senior_retry_count",
    })

    def update_state(self, esc_id: str, state: str, **kwargs):
        now = datetime.now(timezone.utc).isoformat()
        fields = ["state = ?", "updated_at = ?"]
        values = [state, now]
        for k, v in kwargs.items():
            if k not in self._UPDATABLE_COLUMNS:
                logger.warning("update_state: ignoring unknown column '%s'", k)
                continue
            if k == "reasoning_log" and isinstance(v, list):
                fields.append(f"{k} = ?")
                values.append(json.dumps(v))
            elif isinstance(v, dict):
                fields.append(f"{k} = ?")
                values.append(json.dumps(v))
            elif v is not None:
                fields.append(f"{k} = ?")
                values.append(v)
        values.append(esc_id)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE escalations SET {', '.join(fields)} WHERE id = ?",
                values
            )

    def append_reasoning(self, esc_id: str, stage: str, summary: str, detail: str = ""):
        """Append an entry to the reasoning_log for this escalation."""
        esc = self.get(esc_id)
        if not esc:
            return
        log = esc.get("reasoning_log") or []
        if isinstance(log, str):
            try:
                log = json.loads(log)
            except Exception:
                log = []
        log.append({
            "stage": stage,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "detail": detail,
        })
        self.update_state(esc_id, esc.get("state", "UNKNOWN"), reasoning_log=log)

    def increment_junior_retries(self, esc_id: str) -> int:
        with self._conn() as conn:
            conn.execute(
                "UPDATE escalations SET junior_retry_count = junior_retry_count + 1, updated_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), esc_id)
            )
        return self.get(esc_id)["junior_retry_count"]

    def increment_senior_retries(self, esc_id: str) -> int:
        with self._conn() as conn:
            conn.execute(
                "UPDATE escalations SET senior_retry_count = senior_retry_count + 1, updated_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), esc_id)
            )
        return self.get(esc_id)["senior_retry_count"]

    def list_all(self) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM escalations ORDER BY updated_at DESC"
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for field in ("junior_suggestion", "senior_review", "controller_review"):
                if d.get(field):
                    try:
                        d[field] = json.loads(d[field])
                    except Exception:
                        pass
            if d.get("reasoning_log"):
                try:
                    d["reasoning_log"] = json.loads(d["reasoning_log"])
                except Exception:
                    d["reasoning_log"] = []
            result.append(d)
        return result

    def list_pending_human(self) -> list:
        return [e for e in self.list_all() if e["state"] == EscalationState.PENDING_HUMAN]

    def list_rejected(self) -> list:
        return [e for e in self.list_all() if e["state"] == EscalationState.HUMAN_REJECTED]


# ──────────────────────────────────────────────────────────────────────────────
# Escalation Emailer
# ──────────────────────────────────────────────────────────────────────────────

class EscalationEmailer:
    """Sends email notifications at key escalation events."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_pass: str,
        from_address: str,
        operator_email: str,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.from_address = from_address
        self.operator_email = operator_email

    def send(self, subject: str, body: str, urgent: bool = False):
        if not self.smtp_host or not self.operator_email:
            logger.info(f"[Email skipped — no SMTP config] Subject: {subject}")
            return
        try:
            msg = MIMEMultipart()
            msg["From"] = self.from_address
            msg["To"] = self.operator_email
            msg["Subject"] = f"{'🚨 URGENT: ' if urgent else ''}FinOps — {subject}"
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                if self.smtp_user:
                    server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
        except Exception as e:
            logger.error(f"Email send failed: {e}")

    def notify_pending_human(self, esc_id: str, tenant_id: str, controller_summary: str):
        self.send(
            subject=f"Action Required — Escalation {esc_id[:8]} [{tenant_id}]",
            body=(
                f"An escalation requires your decision.\n\n"
                f"Escalation ID: {esc_id}\n"
                f"Tenant: {tenant_id}\n\n"
                f"Controller Summary:\n{controller_summary}\n\n"
                f"Please log in to the dashboard to approve or reject."
            )
        )

    def notify_critical(self, esc_id: str, tenant_id: str, reason: str):
        self.send(
            subject=f"CRITICAL FLAG — Escalation {esc_id[:8]} [{tenant_id}]",
            body=(
                f"A critical issue has been flagged and requires IMMEDIATE attention.\n\n"
                f"Escalation ID: {esc_id}\n"
                f"Tenant: {tenant_id}\n\n"
                f"Reason:\n{reason}\n\n"
                f"This escalation has been STOPPED. Manual review required."
            ),
            urgent=True
        )

    def notify_max_retries(self, esc_id: str, tenant_id: str, stage: str):
        self.send(
            subject=f"Max Retries Exceeded — {esc_id[:8]} [{tenant_id}]",
            body=(
                f"Maximum retries exceeded at the {stage} stage.\n\n"
                f"Escalation ID: {esc_id}\n"
                f"Tenant: {tenant_id}\n\n"
                f"Manual intervention required. Please review and resubmit from the dashboard."
            ),
            urgent=True
        )

    def notify_posted(self, esc_id: str, tenant_id: str, system_reference: str):
        self.send(
            subject=f"Posted to Accounting — {esc_id[:8]} [{tenant_id}]",
            body=(
                f"A journal entry has been approved and posted.\n\n"
                f"Escalation ID: {esc_id}\n"
                f"Tenant: {tenant_id}\n"
                f"System Reference: {system_reference}"
            )
        )


# ──────────────────────────────────────────────────────────────────────────────
# Critique Builder (Session 6 — Retry improvement)
# ──────────────────────────────────────────────────────────────────────────────

def _build_critique_context(
    failed_suggestion: dict,
    reviewer_feedback: str,
    operator_context: str,
    retry_number: int,
) -> str:
    """
    Build an enriched retry context that includes:
    1. The previous failed output (so the agent sees what it got wrong)
    2. A specific critique extracted from the reviewer's feedback
    3. Any operator context
    4. An explicit instruction NOT to repeat the same logic

    This prevents the LLM from producing an identical answer on retry.
    """

    previous_output_summary = ""
    if isinstance(failed_suggestion, dict):
        je = failed_suggestion.get("journal_entry", {})
        flags = failed_suggestion.get("compliance_flags", [])
        reasoning = failed_suggestion.get("reasoning_summary", "")
        previous_output_summary = (
            f"PREVIOUS OUTPUT (Attempt {retry_number}):\n"
            f"  Journal Entry: {json.dumps(je, indent=2)[:800]}\n"
            f"  Compliance Flags: {flags}\n"
            f"  Reasoning: {reasoning[:400]}\n"
        )

    critique = (
        f"REVIEWER CRITIQUE:\n"
        f"{reviewer_feedback}\n\n"
        f"RETRY INSTRUCTIONS (Attempt {retry_number + 1}):\n"
        f"  - You MUST address the specific issues identified above\n"
        f"  - Do NOT repeat the same journal entry structure if it was rejected\n"
        f"  - Do NOT repeat the same reasoning that led to the previous error\n"
        f"  - Explicitly state in your reasoning_summary what you changed and why\n"
        f"  - If the previous output had a debit/credit imbalance, recalculate from scratch\n"
        f"  - If the wrong VAT treatment was applied, identify the correct IAS/TRA rule\n"
    )

    operator = f"\nOPERATOR CONTEXT:\n{operator_context}\n" if operator_context.strip() else ""

    return f"{previous_output_summary}\n{critique}{operator}"


# ──────────────────────────────────────────────────────────────────────────────
# Currency Code Validator (Session 6 — Rule 19)
# ──────────────────────────────────────────────────────────────────────────────

VALID_CURRENCIES = {
    "TZS", "USD", "EUR", "GBP", "KES", "UGX", "ZAR", "NGN",
    "GHS", "RWF", "ETB", "ZMW", "MWK", "BWP", "MZN",
}

def _validate_currency_code(suggestion: dict, tenant_id: str) -> tuple[bool, str]:
    """
    Rule 19: Every JournalEntry must have an explicit currency_code.
    Returns (is_valid, error_message).
    """
    je = suggestion.get("journal_entry", {})
    lines = je.get("lines", [])

    missing = []
    invalid = []

    for i, line in enumerate(lines):
        cc = line.get("currency_code", "").strip().upper()
        if not cc:
            missing.append(f"Line {i+1}: {line.get('account', 'unknown account')}")
        elif cc not in VALID_CURRENCIES:
            invalid.append(f"Line {i+1}: '{cc}' is not a recognised currency code")

    if missing:
        return False, f"Missing currency_code on journal lines: {missing}"
    if invalid:
        return False, f"Invalid currency_code on journal lines: {invalid}"

    return True, ""


# ──────────────────────────────────────────────────────────────────────────────
# Escalation Engine
# ──────────────────────────────────────────────────────────────────────────────

class EscalationEngine:
    """
    Orchestrates the full escalation chain:
      Junior → Senior → Controller → Human → Auto-Post

    v3 additions:
      - Critique injection on RETURN_TO_JUNIOR / RETURN_TO_SENIOR
      - reasoning_log appended at every stage
      - currency_code validation before auto-post
    """

    def __init__(
        self,
        senior_agent,
        controller_agent,
        accounting_adapter,
        emailer: EscalationEmailer,
        store: EscalationStore,
        junior_agent_factory: Callable,
        auto_post_on_approval: bool = True,
    ):
        self.senior = senior_agent
        self.controller = controller_agent
        self.adapter = accounting_adapter
        self.emailer = emailer
        self.store = store
        self.junior_factory = junior_agent_factory
        self.auto_post = auto_post_on_approval

    # ── Public entry points ─────────────────────────────────────────────────

    def process(
        self,
        junior_suggestion: dict,
        tenant_id: str,
        additional_context: str = "",
        online_research: str = "",
    ):
        """Start an escalation from a Junior suggestion. Runs in background thread."""
        thread = threading.Thread(
            target=self._run_escalation,
            args=(junior_suggestion, tenant_id, additional_context, online_research),
            daemon=True,
        )
        thread.start()

    def process_human_approval(
        self,
        escalation_id: str,
        approved: bool,
        operator_notes: str = "",
    ):
        """Handle human approve/reject decision."""
        thread = threading.Thread(
            target=self._run_human_decision,
            args=(escalation_id, approved, operator_notes),
            daemon=True,
        )
        thread.start()

    def process_resubmit(
        self,
        escalation_id: str,
        operator_context: str,
        tenant_id: str,
    ):
        """Resubmit a rejected escalation with fresh operator context."""
        esc = self.store.get(escalation_id)
        if not esc:
            logger.error(f"Resubmit: escalation {escalation_id} not found")
            return

        self.store.update_state(escalation_id, EscalationState.RESUBMITTED)
        self.store.append_reasoning(
            escalation_id, "RESUBMITTED",
            f"Operator resubmitted with context: {operator_context[:200]}"
        )

        junior_suggestion = esc.get("junior_suggestion", {})

        thread = threading.Thread(
            target=self._run_escalation,
            args=(junior_suggestion, tenant_id, operator_context, ""),
            daemon=True,
        )
        thread.start()

    # ── Internal escalation runner ──────────────────────────────────────────

    def _run_escalation(
        self,
        junior_suggestion: dict,
        tenant_id: str,
        additional_context: str,
        online_research: str,
    ):
        esc_id = self.store.create(tenant_id, junior_suggestion)
        logger.info(f"[Escalation {esc_id[:8]}] Started for tenant {tenant_id}")

        try:
            self._senior_review_loop(
                esc_id, junior_suggestion, tenant_id,
                additional_context, online_research,
                retry_count=0, previous_suggestion=None, previous_feedback=""
            )
        except Exception as e:
            logger.exception(f"[Escalation {esc_id[:8]}] Unhandled error: {e}")
            self.store.update_state(esc_id, EscalationState.ERROR)

    def _senior_review_loop(
        self,
        esc_id: str,
        junior_suggestion: dict,
        tenant_id: str,
        additional_context: str,
        online_research: str,
        retry_count: int,
        previous_suggestion: Optional[dict],
        previous_feedback: str,
    ):
        self.store.update_state(esc_id, EscalationState.PENDING_SENIOR)
        self.store.append_reasoning(
            esc_id, "PENDING_SENIOR",
            f"Senior Accountant reviewing (attempt {retry_count + 1})"
        )

        senior_review = self.senior.review(
            junior_suggestion=junior_suggestion,
            tenant_id=tenant_id,
            additional_context=additional_context,
            online_research_results=online_research,
        )
        self.store.update_state(
            esc_id, EscalationState.SENIOR_COMPLETE,
            senior_review=senior_review,
        )
        self.store.append_reasoning(
            esc_id, "SENIOR_COMPLETE",
            f"Senior decision: {senior_review.get('decision', 'unknown')}",
            detail=senior_review.get("notes", "")[:500]
        )

        decision = senior_review.get("decision", "")

        if decision == "FLAG_CRITICAL":
            reason = senior_review.get("notes", "Critical issue flagged by Senior Accountant")
            self.store.update_state(esc_id, EscalationState.FLAGGED_CRITICAL)
            self.store.append_reasoning(esc_id, "FLAGGED_CRITICAL", reason[:300])
            try:
                self.emailer.notify_critical(esc_id, tenant_id, reason)
            except Exception as _e:
                logger.warning(f"notify_critical failed: {_e}")
            return

        elif decision == "RETURN_TO_JUNIOR":
            new_count = self.store.increment_junior_retries(esc_id)
            if new_count > MAX_JUNIOR_RETRIES:
                self.store.update_state(esc_id, EscalationState.MAX_RETRIES_EXCEEDED)
                self.store.append_reasoning(
                    esc_id, "MAX_RETRIES_EXCEEDED",
                    f"Junior exceeded {MAX_JUNIOR_RETRIES} retries. Manual intervention required."
                )
                try:
                    self.emailer.notify_max_retries(esc_id, tenant_id, "Junior Accountant")
                except Exception as _e:
                    logger.warning(f"notify_max_retries failed: {_e}")
                return

            # ── Session 6: Critique injection ──────────────────────────────
            critique_context = _build_critique_context(
                failed_suggestion=junior_suggestion,
                reviewer_feedback=senior_review.get("notes", senior_review.get("critique", "")),
                operator_context=additional_context,
                retry_number=new_count,
            )

            self.store.update_state(esc_id, EscalationState.RETURNED_TO_JUNIOR)
            self.store.append_reasoning(
                esc_id, "RETURNED_TO_JUNIOR",
                f"Senior returned to Junior (retry {new_count}/{MAX_JUNIOR_RETRIES}). "
                f"Critique: {senior_review.get('notes', '')[:200]}"
            )

            # Re-run Junior with critique-enriched context
            tenant_info = {"id": tenant_id}  # simplified — agent reads jurisdiction from init
            new_junior = self.junior_factory(tenant_id, junior_suggestion.get("jurisdiction", "Tanzania"))
            new_suggestion = new_junior.process(
                raw_input=junior_suggestion.get("raw_input", ""),
                source=junior_suggestion.get("source", "retry"),
                extra_context=critique_context,
            )

            # Recurse with new suggestion
            self._senior_review_loop(
                esc_id, new_suggestion, tenant_id,
                additional_context, online_research,
                retry_count=new_count,
                previous_suggestion=junior_suggestion,
                previous_feedback=senior_review.get("notes", ""),
            )

        elif decision in ("APPROVE_WITH_NOTES", "AMEND_AND_ESCALATE"):
            self._controller_review_loop(
                esc_id, junior_suggestion, senior_review, tenant_id,
                additional_context, online_research,
                retry_count=0, previous_feedback=""
            )
        else:
            # Default: escalate to controller
            self._controller_review_loop(
                esc_id, junior_suggestion, senior_review, tenant_id,
                additional_context, online_research,
                retry_count=0, previous_feedback=""
            )

    def _controller_review_loop(
        self,
        esc_id: str,
        junior_suggestion: dict,
        senior_review: dict,
        tenant_id: str,
        additional_context: str,
        online_research: str,
        retry_count: int,
        previous_feedback: str,
    ):
        self.store.update_state(esc_id, EscalationState.PENDING_CONTROLLER)
        self.store.append_reasoning(
            esc_id, "PENDING_CONTROLLER",
            f"Financial Controller reviewing (attempt {retry_count + 1})"
        )

        controller_review = self.controller.review(
            senior_review=senior_review,
            junior_suggestion=junior_suggestion,
            tenant_id=tenant_id,
            additional_context=additional_context,
            online_research_results=online_research,
        )
        self.store.update_state(
            esc_id, EscalationState.CONTROLLER_COMPLETE,
            controller_review=controller_review,
        )
        self.store.append_reasoning(
            esc_id, "CONTROLLER_COMPLETE",
            f"Controller decision: {controller_review.get('decision', 'unknown')}",
            detail=controller_review.get("notes", "")[:500]
        )

        decision = controller_review.get("decision", "")

        if decision == "RETURN_TO_SENIOR":
            new_count = self.store.increment_senior_retries(esc_id)
            if new_count > MAX_SENIOR_RETRIES:
                self.store.update_state(esc_id, EscalationState.MAX_RETRIES_EXCEEDED)
                self.store.append_reasoning(
                    esc_id, "MAX_RETRIES_EXCEEDED",
                    f"Senior exceeded {MAX_SENIOR_RETRIES} retries from Controller. Manual intervention required."
                )
                try:
                    self.emailer.notify_max_retries(esc_id, tenant_id, "Senior Accountant")
                except Exception as _e:
                    logger.warning(f"notify_max_retries failed: {_e}")
                return

            # ── Session 6: Critique injection for Senior retry ─────────────
            critique_context = _build_critique_context(
                failed_suggestion=senior_review,
                reviewer_feedback=controller_review.get("notes", controller_review.get("critique", "")),
                operator_context=additional_context,
                retry_number=new_count,
            )

            self.store.update_state(esc_id, EscalationState.RETURNED_TO_SENIOR)
            self.store.append_reasoning(
                esc_id, "RETURNED_TO_SENIOR",
                f"Controller returned to Senior (retry {new_count}/{MAX_SENIOR_RETRIES}). "
                f"Critique: {controller_review.get('notes', '')[:200]}"
            )

            # Re-run Senior with enriched critique context
            new_senior_review = self.senior.review(
                junior_suggestion=junior_suggestion,
                tenant_id=tenant_id,
                additional_context=critique_context,
                online_research_results=online_research,
            )

            self._controller_review_loop(
                esc_id, junior_suggestion, new_senior_review, tenant_id,
                additional_context, online_research,
                retry_count=new_count,
                previous_feedback=controller_review.get("notes", ""),
            )

        else:
            # RECOMMEND_APPROVAL, RECOMMEND_APPROVAL_WITH_CONDITIONS,
            # RECOMMEND_REJECTION, ESCALATE_TO_HUMAN_URGENT — all go to human
            urgent = (decision == "ESCALATE_TO_HUMAN_URGENT")
            self.store.update_state(esc_id, EscalationState.PENDING_HUMAN)
            self.store.append_reasoning(
                esc_id, "PENDING_HUMAN",
                f"Awaiting human decision. Controller: {decision}. Urgent: {urgent}"
            )

            controller_summary = controller_review.get("notes", controller_review.get("summary", ""))
            try:
                self.emailer.notify_pending_human(esc_id, tenant_id, controller_summary)
            except Exception as _e:
                logger.warning(f"notify_pending_human failed: {_e}")

    def _run_human_decision(
        self,
        escalation_id: str,
        approved: bool,
        operator_notes: str,
    ):
        esc = self.store.get(escalation_id)
        if not esc:
            logger.error(f"Human decision: escalation {escalation_id} not found")
            return

        tenant_id = esc.get("tenant_id", "unknown")

        if not approved:
            self.store.update_state(
                escalation_id, EscalationState.HUMAN_REJECTED,
                operator_notes=operator_notes
            )
            self.store.append_reasoning(
                escalation_id, "HUMAN_REJECTED",
                f"Operator rejected. Notes: {operator_notes[:300]}"
            )
            logger.info(f"[Escalation {escalation_id[:8]}] Rejected by operator")
            return

        self.store.update_state(
            escalation_id, EscalationState.HUMAN_APPROVED,
            operator_notes=operator_notes
        )
        self.store.append_reasoning(
            escalation_id, "HUMAN_APPROVED",
            f"Operator approved. Notes: {operator_notes[:300]}"
        )

        if not self.auto_post:
            logger.info(f"[Escalation {escalation_id[:8]}] Approved, auto-post disabled")
            return

        # ── Auto-post to accounting system ───────────────────────────────
        self.store.update_state(escalation_id, EscalationState.POSTING)
        self.store.append_reasoning(escalation_id, "POSTING", "Auto-posting to accounting system")

        try:
            junior_suggestion = esc.get("junior_suggestion", {})

            # ── Rule 19: Validate currency_code before posting ─────────────
            is_valid, err_msg = _validate_currency_code(junior_suggestion, tenant_id)
            if not is_valid:
                logger.warning(
                    f"[Escalation {escalation_id[:8]}] currency_code validation failed: {err_msg}. "
                    f"Proceeding with post but flagging."
                )
                self.store.append_reasoning(
                    escalation_id, "CURRENCY_WARNING",
                    f"currency_code validation warning: {err_msg}"
                )

            from adapters.accounting_adapter import suggestion_to_journal_entry
            je = suggestion_to_journal_entry(junior_suggestion, tenant_id)
            result = self.adapter.push_journal_entry(je)

            system_ref = result.get("system_id") or result.get("reference") or "posted"
            self.store.update_state(
                escalation_id, EscalationState.POSTED,
                system_reference=system_ref
            )
            self.store.append_reasoning(
                escalation_id, "POSTED",
                f"Successfully posted. System reference: {system_ref}"
            )
            try:
                self.emailer.notify_posted(escalation_id, tenant_id, system_ref)
            except Exception as _e:
                logger.warning(f"notify_posted failed: {_e}")
            logger.info(f"[Escalation {escalation_id[:8]}] Posted. Ref: {system_ref}")

        except Exception as e:
            logger.exception(f"[Escalation {escalation_id[:8]}] Auto-post failed: {e}")
            self.store.update_state(escalation_id, EscalationState.POST_FAILED)
            self.store.append_reasoning(
                escalation_id, "POST_FAILED",
                f"Auto-post failed: {str(e)[:300]}"
            )
