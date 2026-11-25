"""SQLite storage for chat sessions."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .core import Message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class SessionInfo:
    """Summary of a stored session for listing."""

    id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int


class SessionStore:
    """A small SQLite-backed store for sessions and their messages."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = Path(path).expanduser() if str(path) != ":memory:" else path
        if isinstance(self.path, Path):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._conn:
            self._conn.execute("PRAGMA foreign_keys = ON")
            if isinstance(self.path, Path):
                self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL,
                    model       TEXT,
                    reply_mode  TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id      INTEGER NOT NULL
                        REFERENCES sessions(id) ON DELETE CASCADE,
                    seq             INTEGER NOT NULL,
                    role            TEXT NOT NULL,
                    content         TEXT NOT NULL,
                    tool_calls_json TEXT,
                    created_at      TEXT NOT NULL,
                    UNIQUE(session_id, seq)
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_session_seq "
                "ON messages(session_id, seq)"
            )

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()

    def create_session(
        self,
        title: str,
        *,
        model: str | None = None,
        reply_mode: str | None = None,
    ) -> int:
        """Create a session and return its id."""
        now = _now()
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO sessions(title, created_at, updated_at, model, reply_mode) "
                "VALUES (?, ?, ?, ?, ?)",
                (title, now, now, model, reply_mode),
            )
        return int(cursor.lastrowid)

    def append_messages(
        self,
        session_id: int,
        messages: Sequence[Message],
        *,
        title: str | None = None,
    ) -> None:
        """Append messages to a session in order."""
        if not messages:
            return
        with self._conn:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(seq), 0) AS last_seq FROM messages "
                "WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            seq = int(row["last_seq"])
            created_at = _now()
            for message in messages:
                seq += 1
                tool_calls = (
                    json.dumps(message.tool_calls, ensure_ascii=False)
                    if message.tool_calls
                    else None
                )
                self._conn.execute(
                    "INSERT INTO messages(session_id, seq, role, content, "
                    "tool_calls_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (session_id, seq, message.role, message.content, tool_calls, created_at),
                )
            if title is None:
                self._conn.execute(
                    "UPDATE sessions SET updated_at = ? WHERE id = ?",
                    (created_at, session_id),
                )
            else:
                self._conn.execute(
                    "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                    (title, created_at, session_id),
                )

    def list_sessions(self, limit: int = 20) -> list[SessionInfo]:
        """Return recent sessions, newest first."""
        rows = self._conn.execute(
            "SELECT s.id, s.title, s.created_at, s.updated_at, "
            "(SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count "
            "FROM sessions s ORDER BY s.updated_at DESC, s.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            SessionInfo(
                id=int(row["id"]),
                title=str(row["title"]),
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
                message_count=int(row["message_count"]),
            )
            for row in rows
        ]

    def get_session(self, session_id: int) -> SessionInfo | None:
        """Return a session summary by id, if it exists."""
        row = self._conn.execute(
            "SELECT s.id, s.title, s.created_at, s.updated_at, "
            "(SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count "
            "FROM sessions s WHERE s.id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return SessionInfo(
            id=int(row["id"]),
            title=str(row["title"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            message_count=int(row["message_count"]),
        )

    def load_messages(self, session_id: int) -> list[Message]:
        """Load all messages of a session in their original order."""
        rows = self._conn.execute(
            "SELECT role, content, tool_calls_json FROM messages "
            "WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
        messages: list[Message] = []
        for row in rows:
            tool_calls = (
                json.loads(row["tool_calls_json"])
                if row["tool_calls_json"]
                else None
            )
            messages.append(Message(row["role"], row["content"], tool_calls))
        return messages

    def delete_session(self, session_id: int) -> bool:
        """Delete a session and its messages. Returns True if it existed."""
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM sessions WHERE id = ?", (session_id,)
            )
        return cursor.rowcount > 0
