import json
import sqlite3
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


class RunArchive:
    def __init__(self, db_path: str = "./run_archive.sqlite3"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS archived_runs (
                        id TEXT PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        ticker TEXT NOT NULL,
                        stage TEXT,
                        market TEXT,
                        simulated_date TEXT,
                        horizon TEXT,
                        action TEXT,
                        rationale TEXT,
                        source TEXT,
                        result_json TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_archived_runs_created_at ON archived_runs(created_at DESC)"
                )
                conn.commit()
            finally:
                conn.close()

    def store_run(
        self,
        *,
        ticker: str,
        stage: Optional[str],
        market: str,
        simulated_date: Optional[str],
        horizon: str,
        action: str,
        rationale: str,
        result_json: str,
        source: str = "ui",
    ) -> str:
        run_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()

        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO archived_runs (
                        id, created_at, ticker, stage, market, simulated_date,
                        horizon, action, rationale, source, result_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        created_at,
                        ticker,
                        stage,
                        market,
                        simulated_date,
                        horizon,
                        action,
                        rationale,
                        source,
                        result_json,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        return run_id

    def get_runs(self, limit: int = 100) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT id, created_at, ticker, stage, market, simulated_date, horizon,
                       action, rationale, source, result_json
                FROM archived_runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        finally:
            conn.close()

        return [
            {
                "id": row["id"],
                "timestamp": row["created_at"],
                "ticker": row["ticker"],
                "stage": row["stage"],
                "market": row["market"],
                "simulated_date": row["simulated_date"],
                "horizon": row["horizon"],
                "action": row["action"],
                "rationale": row["rationale"],
                "source": row["source"],
                "result_json": row["result_json"],
            }
            for row in rows
        ]

    def clear_all(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM archived_runs")
                conn.commit()
            finally:
                conn.close()

    def count(self) -> int:
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) AS count FROM archived_runs").fetchone()
            return int(row["count"] if row else 0)
        finally:
            conn.close()


_run_archive_instance: Optional[RunArchive] = None


def get_run_archive() -> RunArchive:
    global _run_archive_instance
    if _run_archive_instance is None:
        _run_archive_instance = RunArchive()
    return _run_archive_instance


def initialize_run_archive(db_path: str = "./run_archive.sqlite3") -> RunArchive:
    global _run_archive_instance
    _run_archive_instance = RunArchive(db_path=db_path)
    return _run_archive_instance