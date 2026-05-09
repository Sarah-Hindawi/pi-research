"""
SQLite-backed chat history store.
Provides full audit trail of all queries + answers with sources.
"""
import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from config import get_settings

settings = get_settings()


def _get_conn() -> sqlite3.Connection:
    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.sqlite_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Call once at startup."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                created_at  TEXT NOT NULL,
                label       TEXT
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL REFERENCES sessions(id),
                role        TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content     TEXT NOT NULL,
                sources     TEXT,          -- JSON array of source citations
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, created_at);
        """)


def create_session(label: str | None = None) -> str:
    """Create a new chat session and return its ID."""
    session_id = str(uuid.uuid4())
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (id, created_at, label) VALUES (?, ?, ?)",
            (session_id, _now(), label),
        )
    return session_id


def add_message(
    session_id: str,
    role: str,
    content: str,
    sources: list[dict] | None = None,
) -> str:
    """Append a message to a session. Returns message ID."""
    msg_id = str(uuid.uuid4())
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO messages (id, session_id, role, content, sources, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (msg_id, session_id, role, content, json.dumps(sources or []), _now()),
        )
    return msg_id


def get_history(session_id: str) -> list[dict]:
    """Return all messages for a session in chronological order."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content, sources, created_at FROM messages "
            "WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
    return [
        {
            "role": r["role"],
            "content": r["content"],
            "sources": json.loads(r["sources"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def get_sessions() -> list[dict]:
    """Return all sessions ordered by most recent activity."""
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT s.id, s.label, s.created_at,
                   MAX(m.created_at) as last_activity
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            GROUP BY s.id
            ORDER BY last_activity DESC
        """).fetchall()
    return [dict(r) for r in rows]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
