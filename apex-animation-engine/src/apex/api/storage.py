"""Project + job storage. SQLite for local development; the Repository interface is what a PostgreSQL
implementation must provide in production (see docs/ARCHITECTURE.md)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Optional


class Repository:
    def __init__(self, path: str = "apex.db"):
        self.path = path
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute("CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, title TEXT, spec TEXT, created REAL, updated REAL)")
            c.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, project TEXT, scene TEXT, status TEXT, progress REAL, "
                      "stage TEXT, message TEXT, video TEXT, qa TEXT, error TEXT, created REAL, updated REAL)")

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    # projects
    def save_project(self, pid: str, title: str, spec: dict) -> None:
        now = time.time()
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO projects VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title, spec=excluded.spec, updated=excluded.updated",
                      (pid, title, json.dumps(spec), now, now))

    def get_project(self, pid: str) -> Optional[dict]:
        with self._conn() as c:
            r = c.execute("SELECT spec FROM projects WHERE id=?", (pid,)).fetchone()
        return json.loads(r["spec"]) if r else None

    def list_projects(self) -> List[Dict[str, Any]]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT id, title, created, updated FROM projects ORDER BY updated DESC")]

    # jobs
    def create_job(self, project: str, scene: str) -> str:
        jid = uuid.uuid4().hex[:12]
        now = time.time()
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (jid, project, scene, "queued", 0.0, "", "", None, None, None, now, now))
        return jid

    def update_job(self, jid: str, **fields: Any) -> None:
        fields["updated"] = time.time()
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._lock, self._conn() as c:
            c.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), jid))

    def get_job(self, jid: str) -> Optional[dict]:
        with self._conn() as c:
            r = c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["qa"] = json.loads(d["qa"]) if d["qa"] else None
        return d
