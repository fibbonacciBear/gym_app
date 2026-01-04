"""Database operations supporting both SQLite and PostgreSQL."""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from backend.config import USE_POSTGRES, get_database_url, get_db_path, BASE_DIR

# Import based on database type
if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import sql
else:
    import sqlite3


def init_database(user_id: str = "default") -> None:
    """Initialize database with required tables."""
    if USE_POSTGRES:
        _init_postgres()
    else:
        _init_sqlite(user_id)


def _init_postgres() -> None:
    """Initialize PostgreSQL database."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Events table (append-only event log)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    event_id VARCHAR(255) UNIQUE NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    event_type VARCHAR(100) NOT NULL,
                    payload JSONB NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    schema_version INTEGER DEFAULT 1
                )
            """)

            # Indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_user_id
                ON events(user_id)
            """)
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
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    key VARCHAR(255) NOT NULL,
                    data JSONB NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, key)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_projections_user_id
                ON projections(user_id)
            """)

            # Exercises table (library)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS exercises (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    exercise_id VARCHAR(255) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    category VARCHAR(100),
                    description TEXT,
                    is_custom BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, exercise_id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_exercises_user_id
                ON exercises(user_id)
            """)

        conn.commit()


def _init_sqlite(user_id: str) -> None:
    """Initialize SQLite database."""
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
    
    Works with both PostgreSQL and SQLite based on configuration.
    
    Args:
        user_id: User identifier (only used for SQLite multi-user setup)
        isolation_level: Transaction isolation level
    """
    if USE_POSTGRES:
        conn = psycopg2.connect(get_database_url())
        conn.autocommit = False
        if isolation_level:
            conn.set_isolation_level(isolation_level)
        try:
            yield conn
        finally:
            conn.close()
    else:
        db_path = get_db_path(user_id)
        conn = sqlite3.connect(db_path, timeout=5.0)
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
    conn=None
) -> Dict[str, Any]:
    """Append an event to the event store."""
    timestamp = datetime.utcnow().isoformat() + "Z"

    def _append_postgres(connection):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO events (event_id, user_id, timestamp, event_type, payload)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (event_id, user_id, timestamp, event_type, json.dumps(payload))
            )

    def _append_sqlite(connection):
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
        if USE_POSTGRES:
            _append_postgres(conn)
        else:
            _append_sqlite(conn)
    else:
        # Create own connection and commit
        with get_connection(user_id) as connection:
            if USE_POSTGRES:
                _append_postgres(connection)
            else:
                _append_sqlite(connection)
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
    if USE_POSTGRES:
        return _get_events_postgres(event_type, user_id, limit)
    else:
        return _get_events_sqlite(event_type, user_id, limit)


def _get_events_postgres(event_type: Optional[str], user_id: str, limit: int) -> List[Dict[str, Any]]:
    """Get events from PostgreSQL."""
    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            if event_type:
                cursor.execute(
                    """
                    SELECT event_id, timestamp, event_type, payload
                    FROM events
                    WHERE user_id = %s AND event_type = %s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (user_id, event_type, limit)
                )
            else:
                cursor.execute(
                    """
                    SELECT event_id, timestamp, event_type, payload
                    FROM events
                    WHERE user_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (user_id, limit)
                )

            rows = cursor.fetchall()
            return [
                {
                    "event_id": row["event_id"],
                    "timestamp": row["timestamp"].isoformat() + "Z" if hasattr(row["timestamp"], "isoformat") else row["timestamp"],
                    "event_type": row["event_type"],
                    "payload": row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"])
                }
                for row in rows
            ]


def _get_events_sqlite(event_type: Optional[str], user_id: str, limit: int) -> List[Dict[str, Any]]:
    """Get events from SQLite."""
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


def get_projection(key: str, user_id: str = "default", conn=None) -> Optional[Dict[str, Any]]:
    """Get a projection by key."""
    if USE_POSTGRES:
        return _get_projection_postgres(key, user_id, conn)
    else:
        return _get_projection_sqlite(key, user_id, conn)


def _get_projection_postgres(key: str, user_id: str, conn=None) -> Optional[Dict[str, Any]]:
    """Get projection from PostgreSQL."""
    def _get(connection):
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                "SELECT value FROM projections WHERE user_id = %s AND key = %s",
                (user_id, key)
            )
            row = cursor.fetchone()
            if row:
                data = row["value"]
                # PostgreSQL JSONB returns native Python types (dict, list, etc.)
                if isinstance(data, (dict, list)):
                    return data
                # Fallback for string-encoded JSON
                return json.loads(data) if data else None
            return None

    if conn:
        return _get(conn)
    else:
        with get_connection(user_id) as connection:
            return _get(connection)


def _get_projection_sqlite(key: str, user_id: str, conn=None) -> Optional[Dict[str, Any]]:
    """Get projection from SQLite."""
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


def set_projection(key: str, data: Optional[Dict[str, Any]], user_id: str = "default", conn=None) -> None:
    """Set a projection value."""
    if USE_POSTGRES:
        _set_projection_postgres(key, data, user_id, conn)
    else:
        _set_projection_sqlite(key, data, user_id, conn)


def _set_projection_postgres(key: str, data: Optional[Dict[str, Any]], user_id: str, conn=None) -> None:
    """Set projection in PostgreSQL."""
    timestamp = datetime.utcnow()

    def _set(connection):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO projections (user_id, key, value, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, key)
                DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
                """,
                (user_id, key, json.dumps(data), timestamp)
            )

    if conn:
        _set(conn)
    else:
        with get_connection(user_id) as connection:
            _set(connection)
            connection.commit()


def _set_projection_sqlite(key: str, data: Optional[Dict[str, Any]], user_id: str, conn=None) -> None:
    """Set projection in SQLite."""
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
        _set(conn)
    else:
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

    if USE_POSTGRES:
        _load_exercises_postgres(data["exercises"], user_id)
    else:
        _load_exercises_sqlite(data["exercises"], user_id)


def _load_exercises_postgres(exercises: List[Dict], user_id: str) -> None:
    """Load exercises into PostgreSQL."""
    with get_connection(user_id) as conn:
        with conn.cursor() as cursor:
            for ex in exercises:
                cursor.execute(
                    """
                    INSERT INTO exercises (user_id, exercise_id, name, category, is_custom)
                    VALUES (%s, %s, %s, %s, FALSE)
                    ON CONFLICT (user_id, exercise_id) DO NOTHING
                    """,
                    (user_id, ex["id"], ex["name"], ex.get("category"))
                )
        conn.commit()


def _load_exercises_sqlite(exercises: List[Dict], user_id: str) -> None:
    """Load exercises into SQLite."""
    with get_connection(user_id) as conn:
        cursor = conn.cursor()
        for ex in exercises:
            cursor.execute(
                """
                INSERT OR IGNORE INTO exercises (id, name, category, is_custom)
                VALUES (?, ?, ?, 0)
                """,
                (ex["id"], ex["name"], ex.get("category"))
            )
        conn.commit()


def get_exercises(user_id: str = "default", include_shared: bool = False) -> List[Dict[str, Any]]:
    """
    Get exercises for a user.
    
    Args:
        user_id: The user ID to fetch exercises for
        include_shared: If True and user_id != "default", includes both shared (default) 
                       and user's custom exercises. If False, only returns exercises for user_id.
    
    Returns:
        List of exercise dictionaries
    """
    if USE_POSTGRES:
        return _get_exercises_postgres(user_id, include_shared)
    else:
        return _get_exercises_sqlite(user_id, include_shared)


def _get_exercises_postgres(user_id: str, include_shared: bool = False) -> List[Dict[str, Any]]:
    """
    Get exercises from PostgreSQL.
    
    If include_shared=True and user_id != "default", returns both shared (default) 
    and user's custom exercises.
    """
    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            if include_shared and user_id != "default":
                # Return both shared AND user's custom exercises
                cursor.execute(
                    """SELECT exercise_id as id, name, category, is_custom 
                       FROM exercises 
                       WHERE user_id IN (%s, 'default') 
                       ORDER BY name""",
                    (user_id,)
                )
            else:
                # Return only exercises for this user_id
                cursor.execute(
                    """SELECT exercise_id as id, name, category, is_custom 
                       FROM exercises 
                       WHERE user_id = %s 
                       ORDER BY name""",
                    (user_id,)
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


def _get_exercises_sqlite(user_id: str, include_shared: bool = False) -> List[Dict[str, Any]]:
    """
    Get exercises from SQLite.
    
    Note: SQLite uses separate database files per user, so include_shared is handled
    by querying both the user's DB and the default DB if needed.
    """
    exercises = []
    
    # Get exercises from user's own database
    with get_connection(user_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, category, is_custom FROM exercises ORDER BY name")
        rows = cursor.fetchall()
        exercises = [dict(row) for row in rows]
    
    # If include_shared and not already on default, also fetch from default
    if include_shared and user_id != "default":
        try:
            with get_connection("default") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, category, is_custom FROM exercises ORDER BY name")
                rows = cursor.fetchall()
                shared_exercises = [dict(row) for row in rows]
                
                # Deduplicate by id (user's custom exercises take precedence)
                existing_ids = {ex['id'] for ex in exercises}
                for ex in shared_exercises:
                    if ex['id'] not in existing_ids:
                        exercises.append(ex)
                
                # Re-sort combined list
                exercises.sort(key=lambda x: x['name'])
        except Exception as e:
            # If default DB doesn't exist, just return user's exercises
            print(f"Warning: Could not load shared exercises: {e}")
    
    return exercises


def get_exercise(exercise_id: str, user_id: str = "default") -> Optional[Dict[str, Any]]:
    """Get a single exercise by ID."""
    if USE_POSTGRES:
        return _get_exercise_postgres(exercise_id, user_id)
    else:
        return _get_exercise_sqlite(exercise_id, user_id)


def _get_exercise_postgres(exercise_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Get exercise from PostgreSQL."""
    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                "SELECT exercise_id as id, name, category, is_custom FROM exercises WHERE user_id = %s AND exercise_id = %s",
                (user_id, exercise_id)
            )
            row = cursor.fetchone()
            return dict(row) if row else None


def _get_exercise_sqlite(exercise_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Get exercise from SQLite."""
    with get_connection(user_id) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, category, is_custom FROM exercises WHERE id = ?",
            (exercise_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
