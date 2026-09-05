"""Persistent long-term memory for AI-OS.

Memory is kept outside the LLM in a small SQLite database so it survives
process restarts and can be queried, updated, and audited deterministically.
The legacy ``remember``/``recall`` functions remain available to existing
conversation code.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core.config import MEMORY_FOLDER

DEFAULT_MEMORY_DB = Path(MEMORY_FOLDER) / "long_term_memory.db"


@dataclass(frozen=True)
class MemoryRecord:
    """A durable memory item."""

    id: int
    key: str
    value: str
    category: str
    importance: int
    confidence: float
    source: str
    created_at: str
    updated_at: str


class MemoryStore:
    """Thread-safe persistent memory store backed by SQLite."""

    CATEGORIES = {"fact", "preference", "person", "event", "goal", "context"}

    def __init__(self, path: str | Path = DEFAULT_MEMORY_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL COLLATE NOCASE,
                    value TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'fact',
                    importance INTEGER NOT NULL DEFAULT 5,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    source TEXT NOT NULL DEFAULT 'user',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(key, category)
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT NOT NULL,
                    category TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT 'update'
                )
                """
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_memory_key ON memories(key)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_memory_category ON memories(category)")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _validate_category(cls, category: str) -> str:
        normalized = category.strip().lower()
        if normalized not in cls.CATEGORIES:
            raise ValueError(f"Unknown memory category: {category}")
        return normalized

    @staticmethod
    def _validate_importance(importance: int) -> int:
        if not 1 <= importance <= 10:
            raise ValueError("importance must be between 1 and 10")
        return importance

    @staticmethod
    def _validate_confidence(confidence: float) -> float:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        return confidence

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(**dict(row))

    def remember(
        self,
        key: str,
        value: str,
        *,
        category: str = "fact",
        importance: int = 5,
        confidence: float = 1.0,
        source: str = "user",
        reason: str = "update",
    ) -> MemoryRecord:
        """Create or update a memory and retain the previous value in history."""
        key = key.strip().lower()
        value = value.strip()
        if not key or not value:
            raise ValueError("key and value must be non-empty")
        category = self._validate_category(category)
        importance = self._validate_importance(importance)
        confidence = self._validate_confidence(confidence)
        source = source.strip() or "unknown"
        now = self._now()

        with self._lock, self._connect() as db:
            existing = db.execute(
                "SELECT * FROM memories WHERE key = ? AND category = ?",
                (key, category),
            ).fetchone()

            if existing is None:
                cursor = db.execute(
                    """
                    INSERT INTO memories
                    (key, value, category, importance, confidence, source, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (key, value, category, importance, confidence, source, now, now),
                )
                memory_id = int(cursor.lastrowid)
            else:
                memory_id = int(existing["id"])
                db.execute(
                    """
                    INSERT INTO memory_history
                    (memory_id, key, old_value, new_value, category, changed_at, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (memory_id, key, existing["value"], value, category, now, reason),
                )
                db.execute(
                    """
                    UPDATE memories
                    SET value = ?, importance = ?, confidence = ?, source = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (value, importance, confidence, source, now, memory_id),
                )

            row = db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            return self._row_to_record(row)

    def recall(
        self,
        key: str,
        *,
        category: Optional[str] = None,
    ) -> Optional[MemoryRecord]:
        """Return the highest-importance/confidence memory for a key."""
        key = key.strip().lower()
        if not key:
            return None
        params: list[Any] = [key]
        query = "SELECT * FROM memories WHERE key = ?"
        if category is not None:
            category = self._validate_category(category)
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY importance DESC, confidence DESC, updated_at DESC LIMIT 1"

        with self._lock, self._connect() as db:
            row = db.execute(query, params).fetchone()
            return self._row_to_record(row) if row else None

    def search(
        self,
        query: str,
        *,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Search durable memories by key/value text."""
        query = query.strip().lower()
        if not query:
            return []
        if limit < 1:
            raise ValueError("limit must be positive")
        params: list[Any] = [f"%{query}%", f"%{query}%"]
        sql = "SELECT * FROM memories WHERE (key LIKE ? OR value LIKE ?)"
        if category is not None:
            category = self._validate_category(category)
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY importance DESC, confidence DESC, updated_at DESC LIMIT ?"
        params.append(limit)

        with self._lock, self._connect() as db:
            rows = db.execute(sql, params).fetchall()
            return [self._row_to_record(row) for row in rows]

    def list(self, *, category: Optional[str] = None) -> list[MemoryRecord]:
        """List memories, ordered by importance and recency."""
        params: list[Any] = []
        sql = "SELECT * FROM memories"
        if category is not None:
            category = self._validate_category(category)
            sql += " WHERE category = ?"
            params.append(category)
        sql += " ORDER BY importance DESC, updated_at DESC, id DESC"
        with self._lock, self._connect() as db:
            rows = db.execute(sql, params).fetchall()
            return [self._row_to_record(row) for row in rows]

    def history(self, key: str, *, category: Optional[str] = None) -> list[dict[str, Any]]:
        """Return prior values for a memory, newest first."""
        key = key.strip().lower()
        params: list[Any] = [key]
        sql = "SELECT * FROM memory_history WHERE key = ?"
        if category is not None:
            category = self._validate_category(category)
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY changed_at DESC, id DESC"
        with self._lock, self._connect() as db:
            return [dict(row) for row in db.execute(sql, params).fetchall()]

    def forget(self, key: str, *, category: Optional[str] = None) -> int:
        """Delete a memory explicitly. Returns the number of deleted records."""
        key = key.strip().lower()
        params: list[Any] = [key]
        sql = "DELETE FROM memories WHERE key = ?"
        if category is not None:
            category = self._validate_category(category)
            sql += " AND category = ?"
            params.append(category)
        with self._lock, self._connect() as db:
            cursor = db.execute(sql, params)
            return cursor.rowcount

    def clear(self) -> None:
        """Clear all memories and their change history."""
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM memory_history")
            db.execute("DELETE FROM memories")


# One process-wide store used by the conversation layer.
memory_store = MemoryStore()


def remember(key: str, value: str) -> MemoryRecord:
    """Backward-compatible shorthand for storing a user fact."""
    return memory_store.remember(key, value)


def recall(key: str) -> Optional[str]:
    """Backward-compatible shorthand returning only the stored value."""
    record = memory_store.recall(key)
    return record.value if record else None


def load_memory() -> dict[str, str]:
    """Compatibility helper exposing the simple key/value view."""
    return {record.key: record.value for record in memory_store.list()}


def save_memory(memory: dict[str, str]) -> None:
    """Compatibility helper for legacy callers that replace the key/value map."""
    for key, value in memory.items():
        remember(key, value)
