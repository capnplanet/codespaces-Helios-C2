from __future__ import annotations
import sqlite3
import time
from pathlib import Path
from typing import Optional


class RiskStore:
    def __init__(self, path: str, window_seconds: int = 300):
        self.path = Path(path)
        self.window_seconds = window_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_counts (
                    tenant TEXT PRIMARY KEY,
                    count INTEGER NOT NULL,
                    last_reset REAL NOT NULL
                )
                """
            )
            conn.commit()

    def _reset_if_needed(self, conn: sqlite3.Connection, tenant: str, now: float) -> None:
        cur = conn.execute("SELECT count, last_reset FROM tenant_counts WHERE tenant = ?", (tenant,))
        row = cur.fetchone()
        if not row:
            conn.execute(
                "INSERT OR REPLACE INTO tenant_counts (tenant, count, last_reset) VALUES (?, ?, ?)",
                (tenant, 0, now),
            )
            return
        count, last_reset = row
        if now - last_reset > self.window_seconds:
            conn.execute(
                "UPDATE tenant_counts SET count = ?, last_reset = ? WHERE tenant = ?",
                (0, now, tenant),
            )

    def increment_and_get(self, tenant: str, now: Optional[float] = None) -> int:
        now = now or time.time()
        with sqlite3.connect(self.path) as conn:
            self._reset_if_needed(conn, tenant, now)
            conn.execute("UPDATE tenant_counts SET count = count + 1 WHERE tenant = ?", (tenant,))
            conn.commit()
            cur = conn.execute("SELECT count FROM tenant_counts WHERE tenant = ?", (tenant,))
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def get(self, tenant: str, now: Optional[float] = None) -> int:
        now = now or time.time()
        with sqlite3.connect(self.path) as conn:
            self._reset_if_needed(conn, tenant, now)
            cur = conn.execute("SELECT count FROM tenant_counts WHERE tenant = ?", (tenant,))
            row = cur.fetchone()
            return int(row[0]) if row else 0
