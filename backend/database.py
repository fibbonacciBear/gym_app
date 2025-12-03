"""SQLite database operations."""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from backend.config import get_db_path, BASE_DIR

def init_database(user_id: str = "default") -> None:
    """Initialize database with required tables."""
    db_path = get_db_path(user_id)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Events table (append-only event log)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                schema_version INTEGER DEFAULT 1
            )
        """)

        # Indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type
            ON events(event_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_timestamp
            ON events(timestamp)
        """)

        # Projections table (derived state)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projections (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Aggregates table (time-based stats)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aggregates (
                period_type TEXT NOT NULL,
                period_key TEXT NOT NULL,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (period_type, period_key)
            )
        """)

        # Exercises table (library)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exercises (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                description TEXT,
                is_custom INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)

        conn.commit()

@contextmanager
def get_connection(user_id: str = "default", isolation_level: str = None):
    """
    Get database connection context manager.

    Args:
        user_id: User identifier
        isolation_level: Transaction isolation level (None/DEFERRED, IMMEDIATE, EXCLUSIVE)
                        Default None (DEFERRED) for reads, IMMEDIATE for writes
    """
    db_path = get_db_path(user_id)
    conn = sqlite3.connect(db_path, timeout=5.0)  # 5 second timeout for lock waits
    conn.row_factory = sqlite3.Row
    if isolation_level is not None:
        conn.isolation_level = isolation_level
    try:
        yield conn
    finally:
        conn.close()

def append_event(
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    user_id: str = "default",
    conn: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """Append an event to the event store."""
    timestamp = datetime.utcnow().isoformat() + "Z"

    def _append(connection):
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO events (event_id, timestamp, event_type, payload)
            VALUES (?, ?, ?, ?)
            """,
            (event_id, timestamp, event_type, json.dumps(payload))
        )

    if conn:
        # Use provided connection (transaction managed externally)
        _append(conn)
    else:
        # Create own connection and commit
        with get_connection(user_id) as connection:
            _append(connection)
            connection.commit()

    return {
        "event_id": event_id,
        "timestamp": timestamp,
        "event_type": event_type,
        "payload": payload
    }

def get_events(
    event_type: Optional[str] = None,
    user_id: str = "default",
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get events from the store, optionally filtered by type."""
    with get_connection(user_id) as conn:
        cursor = conn.cursor()

        if event_type:
            cursor.execute(
                """
                SELECT event_id, timestamp, event_type, payload
                FROM events
                WHERE event_type = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (event_type, limit)
            )
        else:
            cursor.execute(
                """
                SELECT event_id, timestamp, event_type, payload
                FROM events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,)
            )

        rows = cursor.fetchall()
        return [
            {
                "event_id": row["event_id"],
                "timestamp": row["timestamp"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload"])
            }
            for row in rows
        ]

def get_projection(key: str, user_id: str = "default", conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    """Get a projection by key."""
    def _get(connection):
        cursor = connection.cursor()
        cursor.execute(
            "SELECT data FROM projections WHERE key = ?",
            (key,)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row["data"])
        return None

    if conn:
        return _get(conn)
    else:
        with get_connection(user_id) as connection:
            return _get(connection)

def set_projection(key: str, data: Optional[Dict[str, Any]], user_id: str = "default", conn: Optional[sqlite3.Connection] = None) -> None:
    """Set a projection value."""
    timestamp = datetime.utcnow().isoformat() + "Z"

    def _set(connection):
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO projections (key, data, updated_at)
            VALUES (?, ?, ?)
            """,
            (key, json.dumps(data), timestamp)
        )

    if conn:
        # Use provided connection (transaction managed externally)
        _set(conn)
    else:
        # Create own connection and commit
        with get_connection(user_id) as connection:
            _set(connection)
            connection.commit()

def load_default_exercises(user_id: str = "default") -> None:
    """Load default exercises into database."""
    exercises_file = BASE_DIR / "data" / "exercises.json"

    if not exercises_file.exists():
        return

    with open(exercises_file) as f:
        data = json.load(f)

    with get_connection(user_id) as conn:
        cursor = conn.cursor()
        for ex in data["exercises"]:
            cursor.execute(
                """
                INSERT OR IGNORE INTO exercises (id, name, category, is_custom)
                VALUES (?, ?, ?, 0)
                """,
                (ex["id"], ex["name"], ex.get("category"))
            )
        conn.commit()

def get_exercises(user_id: str = "default") -> List[Dict[str, Any]]:
    """Get all exercises."""
    with get_connection(user_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, category, is_custom FROM exercises ORDER BY name")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_exercise(exercise_id: str, user_id: str = "default") -> Optional[Dict[str, Any]]:
    """Get a single exercise by ID."""
    with get_connection(user_id) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, category, is_custom FROM exercises WHERE id = ?",
            (exercise_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
