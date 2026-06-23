import os
import aiosqlite
from datetime import datetime, timedelta, timezone

DB_PATH = os.getenv("SQLITE_DB_PATH", "./sessions.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    created_at TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'discovery'
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    was_blocked INTEGER NOT NULL DEFAULT 0,
    validator_retries INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS blocked_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    reason TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Migrate existing sessions table to add mode column if missing
MIGRATIONS = [
    "ALTER TABLE sessions ADD COLUMN mode TEXT NOT NULL DEFAULT 'discovery'",
]


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        # Run migrations safely (ignore errors for already-applied ones)
        for migration in MIGRATIONS:
            try:
                await db.execute(migration)
            except Exception:
                pass
        # Seed default settings
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('default_mode', 'discovery')"
        )
        await db.commit()


# ── Settings ──────────────────────────────────────────────────────────────────

async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
    return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await db.commit()


async def get_default_mode() -> str:
    return await get_setting("default_mode", "discovery")


async def set_default_mode(mode: str):
    await set_setting("default_mode", mode)


# ── Sessions ──────────────────────────────────────────────────────────────────

async def create_session(session_id: str, subject: str, mode: str = "discovery"):
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO sessions (session_id, subject, created_at, mode) VALUES (?, ?, ?, ?)",
            (session_id, subject, now, mode),
        )
        await db.commit()


async def get_session_mode(session_id: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT mode FROM sessions WHERE session_id = ?", (session_id,)
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else "discovery"


async def update_session_mode(session_id: str, mode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sessions SET mode = ? WHERE session_id = ?", (mode, session_id)
        )
        await db.commit()


# ── Messages ──────────────────────────────────────────────────────────────────

async def log_message(
    session_id: str,
    role: str,
    content: str,
    was_blocked: bool = False,
    validator_retries: int = 0,
):
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO messages (session_id, role, content, timestamp, was_blocked, validator_retries)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, role, content, now, int(was_blocked), validator_retries),
        )
        await db.commit()


async def log_blocked_attempt(session_id: str, content: str, reason: str):
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO blocked_attempts (session_id, content, reason, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, content, reason, now),
        )
        await db.commit()


async def get_session_messages_public(session_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT role, content, timestamp FROM messages
               WHERE session_id = ? AND was_blocked = 0 ORDER BY id ASC""",
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [{"role": row["role"], "content": row["content"], "timestamp": row["timestamp"]} for row in rows]


async def get_session_history(session_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT role, content FROM messages WHERE session_id = ? AND was_blocked = 0 ORDER BY id ASC",
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


async def check_rate_limit(session_id: str, max_messages: int = 30, window_hours: int = 1) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """SELECT COUNT(*) FROM messages
               WHERE session_id = ? AND role = 'user' AND was_blocked = 0 AND timestamp > ?""",
            (session_id, cutoff),
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] < max_messages


async def get_audit_log(session_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ) as cursor:
            session = await cursor.fetchone()

        if not session:
            return None

        async with db.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,)
        ) as cursor:
            messages = [dict(row) for row in await cursor.fetchall()]

        async with db.execute(
            "SELECT * FROM blocked_attempts WHERE session_id = ? ORDER BY id ASC", (session_id,)
        ) as cursor:
            blocked = [dict(row) for row in await cursor.fetchall()]

    return {
        "session": dict(session),
        "messages": messages,
        "blocked_attempts": blocked,
    }


async def get_all_sessions() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("SELECT * FROM sessions ORDER BY created_at DESC") as cursor:
            sessions = [dict(row) for row in await cursor.fetchall()]

        result = []
        for s in sessions:
            sid = s["session_id"]

            async with db.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = ? AND role = 'user'", (sid,)
            ) as cursor:
                msg_count = (await cursor.fetchone())[0]

            async with db.execute(
                "SELECT COUNT(*) FROM blocked_attempts WHERE session_id = ?", (sid,)
            ) as cursor:
                blocked_count = (await cursor.fetchone())[0]

            async with db.execute(
                "SELECT COALESCE(SUM(validator_retries), 0) FROM messages WHERE session_id = ?",
                (sid,),
            ) as cursor:
                retry_count = (await cursor.fetchone())[0]

            result.append({
                **s,
                "message_count": msg_count,
                "blocked_count": blocked_count,
                "validator_retry_count": retry_count,
            })

    return result
