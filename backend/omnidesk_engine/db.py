from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from omnidesk_engine.schemas import (
    AppSettings,
    AuditEntry,
    TaskRun,
    TeachSession,
    WorkflowDefinition,
    utc_now_iso,
)


class Database:
    """Indexed local SQLite store for tasks, workflows, audit logs, and reversible journals."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(self.db_path, timeout=15.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

                CREATE TABLE IF NOT EXISTS operation_journal (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    op_type TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    dest_path TEXT NOT NULL,
                    sha256 TEXT,
                    reverted INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_journal_task ON operation_journal(task_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    category TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    risk TEXT,
                    task_id TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp DESC);

                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_workflows_updated ON workflows(updated_at DESC);

                CREATE TABLE IF NOT EXISTS teach_sessions (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_teach_started ON teach_sessions(started_at DESC);

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS provider_prefs (
                    provider_id TEXT PRIMARY KEY,
                    base_url TEXT,
                    selected_models TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def save_task(self, task: TaskRun) -> None:
        task.updated_at = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (id, status, created_at, updated_at, payload)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                (task.id, task.status.value, task.created_at, task.updated_at, task.model_dump_json()),
            )

    def get_task(self, task_id: str) -> TaskRun | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return TaskRun.model_validate_json(row["payload"]) if row else None

    def list_tasks(self, limit: int = 50) -> list[TaskRun]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [TaskRun.model_validate_json(r["payload"]) for r in rows]

    def delete_task(self, task_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.execute("DELETE FROM operation_journal WHERE task_id = ?", (task_id,))
            return cur.rowcount > 0

    def clear_history(self) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM tasks")
            conn.execute("DELETE FROM operation_journal")
            conn.execute("DELETE FROM audit_log")
            return cur.rowcount

    def record_journal(
        self,
        task_id: str,
        step_id: str,
        op_type: str,
        source_path: str,
        dest_path: str,
        sha256: str | None = None,
    ) -> str:
        entry_id = f"jrn-{uuid.uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO operation_journal
                    (id, task_id, step_id, op_type, source_path, dest_path, sha256, reverted, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (entry_id, task_id, step_id, op_type, source_path, dest_path, sha256, utc_now_iso()),
            )
        return entry_id

    def get_journal_entries(self, task_id: str, include_reverted: bool = False) -> list[dict[str, Any]]:
        query = (
            "SELECT * FROM operation_journal WHERE task_id = ? "
            + ("" if include_reverted else "AND reverted = 0 ")
            + "ORDER BY rowid DESC"
        )
        with self._connect() as conn:
            rows = conn.execute(query, (task_id,)).fetchall()
            return [dict(r) for r in rows]

    def mark_journal_reverted(self, entry_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE operation_journal SET reverted = 1 WHERE id = ?", (entry_id,))

    def add_audit(
        self,
        category: str,
        action: str,
        detail: str,
        risk: str | None = None,
        task_id: str | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            id=f"aud-{uuid.uuid4().hex[:12]}",
            timestamp=utc_now_iso(),
            category=category,
            action=action,
            detail=detail,
            risk=risk,
            task_id=task_id,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (id, timestamp, category, action, detail, risk, task_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.timestamp,
                    entry.category,
                    entry.action,
                    entry.detail,
                    entry.risk,
                    entry.task_id,
                ),
            )
        return entry

    def list_audit(self, limit: int = 100) -> list[AuditEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [AuditEntry(**dict(r)) for r in rows]

    def save_workflow(self, wf: WorkflowDefinition) -> WorkflowDefinition:
        wf.updated_at = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO workflows (id, name, version, updated_at, payload)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    version = excluded.version,
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                (wf.id, wf.name, wf.version, wf.updated_at, wf.model_dump_json()),
            )
        return wf

    def get_workflow(self, wf_id: str) -> WorkflowDefinition | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM workflows WHERE id = ?", (wf_id,)).fetchone()
            return WorkflowDefinition.model_validate_json(row["payload"]) if row else None

    def list_workflows(self) -> list[WorkflowDefinition]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM workflows ORDER BY updated_at DESC").fetchall()
            return [WorkflowDefinition.model_validate_json(r["payload"]) for r in rows]

    def delete_workflow(self, wf_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM workflows WHERE id = ?", (wf_id,))
            return cur.rowcount > 0

    def save_teach_session(self, session: TeachSession) -> TeachSession:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO teach_sessions (id, status, started_at, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    payload = excluded.payload
                """,
                (session.id, session.status, session.started_at, session.model_dump_json()),
            )
        return session

    def get_teach_session(self, session_id: str) -> TeachSession | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM teach_sessions WHERE id = ?", (session_id,)).fetchone()
            return TeachSession.model_validate_json(row["payload"]) if row else None

    def list_teach_sessions(self) -> list[TeachSession]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM teach_sessions ORDER BY started_at DESC LIMIT 30"
            ).fetchall()
            return [TeachSession.model_validate_json(r["payload"]) for r in rows]

    def get_settings(self) -> AppSettings:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM settings WHERE key = 'app'").fetchone()
            if row:
                return AppSettings.model_validate_json(row["payload"])
        defaults = AppSettings()
        self.save_settings(defaults)
        return defaults

    def save_settings(self, settings: AppSettings) -> AppSettings:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO settings (key, payload, updated_at)
                VALUES ('app', ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (settings.model_dump_json(), utc_now_iso()),
            )
        return settings

    def get_provider_pref(self, provider_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT base_url, selected_models FROM provider_prefs WHERE provider_id = ?",
                (provider_id,),
            ).fetchone()
            if not row:
                return {"base_url": None, "selected_models": {}}
            return {
                "base_url": row["base_url"],
                "selected_models": json.loads(row["selected_models"]),
            }

    def save_provider_pref(
        self,
        provider_id: str,
        base_url: str | None,
        selected_models: dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO provider_prefs (provider_id, base_url, selected_models, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    base_url = excluded.base_url,
                    selected_models = excluded.selected_models,
                    updated_at = excluded.updated_at
                """,
                (provider_id, base_url, json.dumps(selected_models), utc_now_iso()),
            )
