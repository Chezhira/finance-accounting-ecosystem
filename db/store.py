"""
Database Layer — Finance & Accounting AI Ecosystem
SQLite offline + Postgres sync + Tenant management
"""

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent   # finops/
SQLITE_PATH = os.environ.get("FINOPS_SQLITE_PATH", str(_ROOT / "finops_offline.db"))

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tenants (
    id                  TEXT PRIMARY KEY,
    display_name        TEXT NOT NULL,
    jurisdiction        TEXT NOT NULL,
    accounting_standard TEXT NOT NULL,
    country             TEXT NOT NULL,
    currency            TEXT NOT NULL,
    notes               TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suggestions (
    id               TEXT PRIMARY KEY,
    tenant_id        TEXT NOT NULL,
    jurisdiction     TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending',
    agent            TEXT NOT NULL DEFAULT 'junior_accountant',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    suggestion_json  TEXT NOT NULL,
    synced           INTEGER NOT NULL DEFAULT 0,
    sync_attempted_at TEXT,
    human_decision   TEXT,
    human_notes      TEXT,
    decided_by       TEXT,
    decided_at       TEXT
);

CREATE TABLE IF NOT EXISTS ingestion_log (
    id            TEXT PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    source        TEXT NOT NULL,
    filename      TEXT,
    received_at   TEXT NOT NULL,
    raw_preview   TEXT,
    suggestion_id TEXT
);

CREATE TABLE IF NOT EXISTS sync_log (
    id         TEXT PRIMARY KEY,
    synced_at  TEXT NOT NULL,
    record_ids TEXT NOT NULL,
    status     TEXT NOT NULL,
    error_msg  TEXT
);
"""

# Seed tenants added on first run
DEFAULT_TENANTS = [
    {
        "id": "chezsolutions_tz",
        "display_name": "Chezsolutions Tanzania",
        "jurisdiction": "TZ",
        "accounting_standard": "IFRS",
        "country": "Tanzania",
        "currency": "TZS",
        "notes": "Primary Tanzania entity — TRA registered",
    },
    {
        "id": "family_llc_us",
        "display_name": "Family LLC (United States)",
        "jurisdiction": "US",
        "accounting_standard": "US_GAAP",
        "country": "United States",
        "currency": "USD",
        "notes": "US family-owned LLC — pass-through taxation",
    },
]


class OfflineStore:

    def __init__(self, db_path: str = SQLITE_PATH):
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(SCHEMA_SQL)
        self._seed_tenants()

    def _seed_tenants(self):
        """Add default tenants if none exist."""
        with self._conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0]
            if count == 0:
                now = datetime.now(timezone.utc).isoformat()
                for t in DEFAULT_TENANTS:
                    conn.execute(
                        """INSERT OR IGNORE INTO tenants
                           (id, display_name, jurisdiction, accounting_standard,
                            country, currency, notes, created_at, updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (t["id"], t["display_name"], t["jurisdiction"],
                         t["accounting_standard"], t["country"], t["currency"],
                         t.get("notes", ""), now, now)
                    )

    # ── TENANT MANAGEMENT ──────────────────────

    def list_tenants(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM tenants ORDER BY display_name ASC").fetchall()
        return [dict(r) for r in rows]

    def get_tenant(self, tenant_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
        return dict(row) if row else None

    def create_tenant(
        self,
        tenant_id: str,
        display_name: str,
        jurisdiction: str,
        accounting_standard: str,
        country: str,
        currency: str,
        notes: str = "",
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        # Sanitise tenant_id: lowercase, underscores only
        safe_id = tenant_id.lower().replace(" ", "_").replace("-", "_")[:40]
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO tenants
                   (id, display_name, jurisdiction, accounting_standard,
                    country, currency, notes, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (safe_id, display_name, jurisdiction, accounting_standard,
                 country, currency, notes, now, now)
            )
        logger.info(f"[Store] Tenant created: {safe_id}")
        return self.get_tenant(safe_id)

    def delete_tenant(self, tenant_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))
        return cur.rowcount > 0

    # ── SUGGESTIONS ────────────────────────────

    def save_suggestion(self, suggestion: dict, tenant_id: str, jurisdiction: str) -> str:
        suggestion_id = suggestion.get("suggestion_id") or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO suggestions
                   (id, tenant_id, jurisdiction, status, agent, created_at, updated_at, suggestion_json, synced)
                   VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, 0)""",
                (suggestion_id, tenant_id, jurisdiction,
                 suggestion.get("agent", "junior_accountant"),
                 now, now, json.dumps(suggestion))
            )
        return suggestion_id

    def get_suggestion(self, suggestion_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM suggestions WHERE id = ?", (suggestion_id,)).fetchone()
        if row:
            d = dict(row)
            d["suggestion_json"] = json.loads(d["suggestion_json"])
            return d
        return None

    def list_suggestions(self, tenant_id: str, status: Optional[str] = None, limit: int = 50) -> list[dict]:
        sql = "SELECT * FROM suggestions WHERE tenant_id = ?"
        params: list = [tenant_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["suggestion_json"] = json.loads(d["suggestion_json"])
            result.append(d)
        return result

    def update_decision(self, suggestion_id: str, decision: str, decided_by: str, notes: str = "") -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                """UPDATE suggestions
                   SET status=?, human_decision=?, human_notes=?,
                       decided_by=?, decided_at=?, updated_at=?
                   WHERE id=?""",
                (decision, decision, notes, decided_by, now, now, suggestion_id)
            )
        return cur.rowcount > 0

    def get_unsynced(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM suggestions WHERE synced = 0 ORDER BY created_at ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_synced(self, suggestion_ids: list[str]):
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.executemany(
                "UPDATE suggestions SET synced=1, sync_attempted_at=? WHERE id=?",
                [(now, sid) for sid in suggestion_ids]
            )

    def log_ingestion(self, tenant_id: str, source: str, filename: str, raw_preview: str, suggestion_id: str):
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO ingestion_log
                   (id, tenant_id, source, filename, received_at, raw_preview, suggestion_id)
                   VALUES (?,?,?,?,?,?,?)""",
                (str(uuid.uuid4()), tenant_id, source, filename, now, raw_preview[:500], suggestion_id)
            )

    def stats(self, tenant_id: str) -> dict:
        with self._conn() as conn:
            total    = conn.execute("SELECT COUNT(*) FROM suggestions WHERE tenant_id=?", (tenant_id,)).fetchone()[0]
            pending  = conn.execute("SELECT COUNT(*) FROM suggestions WHERE tenant_id=? AND UPPER(status) IN ('PENDING','PENDING_REVIEW')", (tenant_id,)).fetchone()[0]
            approved = conn.execute("SELECT COUNT(*) FROM suggestions WHERE tenant_id=? AND UPPER(status)='APPROVED'", (tenant_id,)).fetchone()[0]
            rejected = conn.execute("SELECT COUNT(*) FROM suggestions WHERE tenant_id=? AND UPPER(status)='REJECTED'", (tenant_id,)).fetchone()[0]
            escalated= conn.execute("SELECT COUNT(*) FROM suggestions WHERE tenant_id=? AND UPPER(status) IN ('ESCALATED','ESCALATE')", (tenant_id,)).fetchone()[0]
            unsynced = conn.execute("SELECT COUNT(*) FROM suggestions WHERE tenant_id=? AND synced=0", (tenant_id,)).fetchone()[0]
        return {"total": total, "pending": pending, "approved": approved,
                "rejected": rejected, "escalated": escalated, "unsynced": unsynced}


# ── POSTGRES SYNC ──────────────────────────────

class PostgresSyncManager:

    def __init__(self, offline_store: OfflineStore):
        self.store = offline_store
        self.postgres_url = os.environ.get("FINOPS_POSTGRES_URL")

    def is_online(self) -> bool:
        if not self.postgres_url:
            return False
        try:
            import psycopg2
            conn = psycopg2.connect(self.postgres_url, connect_timeout=3)
            conn.close()
            return True
        except Exception:
            return False

    def sync(self) -> dict:
        if not self.is_online():
            return {"status": "offline", "synced": 0}
        unsynced = self.store.get_unsynced()
        if not unsynced:
            return {"status": "ok", "synced": 0}
        try:
            import psycopg2
            conn = psycopg2.connect(self.postgres_url)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS suggestions (
                    id TEXT PRIMARY KEY, tenant_id TEXT, jurisdiction TEXT,
                    status TEXT, agent TEXT, created_at TIMESTAMPTZ,
                    updated_at TIMESTAMPTZ, suggestion_json JSONB,
                    synced BOOLEAN DEFAULT TRUE, human_decision TEXT,
                    human_notes TEXT, decided_by TEXT, decided_at TIMESTAMPTZ
                )
            """)
            synced_ids = []
            for record in unsynced:
                cur.execute("""
                    INSERT INTO suggestions
                    (id,tenant_id,jurisdiction,status,agent,created_at,updated_at,
                     suggestion_json,synced,human_decision,human_notes,decided_by,decided_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,true,%s,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE SET
                        status=EXCLUDED.status, updated_at=EXCLUDED.updated_at,
                        suggestion_json=EXCLUDED.suggestion_json,
                        human_decision=EXCLUDED.human_decision,
                        human_notes=EXCLUDED.human_notes,
                        decided_by=EXCLUDED.decided_by,
                        decided_at=EXCLUDED.decided_at, synced=true
                """, (
                    record["id"], record["tenant_id"], record["jurisdiction"],
                    record["status"], record["agent"], record["created_at"],
                    record["updated_at"], record["suggestion_json"],
                    record.get("human_decision"), record.get("human_notes"),
                    record.get("decided_by"), record.get("decided_at")
                ))
                synced_ids.append(record["id"])
            conn.commit()
            cur.close()
            conn.close()
            self.store.mark_synced(synced_ids)
            return {"status": "ok", "synced": len(synced_ids)}
        except Exception as e:
            return {"status": "error", "error": str(e), "synced": 0}
