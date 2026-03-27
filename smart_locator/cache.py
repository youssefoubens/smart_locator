"""SQLite-backed suggestion cache."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_CACHE_PATH = Path.home() / ".smart_locator" / "cache.db"


class SmartLocatorCache:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path or DEFAULT_CACHE_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS suggestions (
                    url TEXT NOT NULL,
                    query TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (url, query)
                )
                """
            )

    def get(self, url: str, query: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM suggestions WHERE url = ? AND query = ?",
                (url, query),
            ).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def set(self, url: str, query: str, payload: Dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "REPLACE INTO suggestions (url, query, payload) VALUES (?, ?, ?)",
                (url, query, json.dumps(payload)),
            )

    def invalidate(self, url: str, query: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM suggestions WHERE url = ? AND query = ?",
                (url, query),
            )

    def clear(self) -> int:
        with self._connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM suggestions").fetchone()[0]
            connection.execute("DELETE FROM suggestions")
        return int(count)
