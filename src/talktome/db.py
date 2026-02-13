import json
import os
import sqlite3
import time

# db lives in user home so it survives across projects
DB_DIR = os.path.join(os.path.expanduser("~"), ".talktome")
DB_PATH = os.path.join(DB_DIR, "bridge.db")


def _connect():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init():
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            name TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            registered_at REAL NOT NULL,
            last_seen REAL NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp REAL NOT NULL,
            read INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS context (
            owner TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (owner, key)
        );

        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            timestamp REAL NOT NULL,
            data TEXT NOT NULL DEFAULT '{}'
        );
    """)
    conn.close()


# --- registry operations ---


def register(name, path, metadata=None):
    now = time.time()
    entry = {
        "name": name,
        "path": path,
        "status": "active",
        "registered_at": now,
        "last_seen": now,
        "metadata": metadata or {},
    }
    conn = _connect()
    conn.execute(
        """INSERT INTO agents (name, path, status, registered_at, last_seen, metadata)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(name) DO UPDATE SET
               path=excluded.path, status='active',
               last_seen=excluded.last_seen, metadata=excluded.metadata""",
        (name, path, "active", now, now, json.dumps(metadata or {})),
    )
    conn.commit()
    conn.close()
    return entry


def deregister(name):
    conn = _connect()
    cursor = conn.execute("DELETE FROM agents WHERE name=?", (name,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def get_agent(name):
    conn = _connect()
    row = conn.execute("SELECT * FROM agents WHERE name=?", (name,)).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "name": row["name"],
        "path": row["path"],
        "status": row["status"],
        "registered_at": row["registered_at"],
        "last_seen": row["last_seen"],
        "metadata": json.loads(row["metadata"]),
    }


def list_agents():
    conn = _connect()
    rows = conn.execute("SELECT name FROM agents ORDER BY name").fetchall()
    conn.close()
    return [row["name"] for row in rows]


def update_status(name, status):
    conn = _connect()
    cursor = conn.execute(
        "UPDATE agents SET status=?, last_seen=? WHERE name=?",
        (status, time.time(), name),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


def update_metadata(name, metadata):
    conn = _connect()
    cursor = conn.execute(
        "UPDATE agents SET metadata=? WHERE name=?",
        (json.dumps(metadata), name),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


def is_registered(name):
    conn = _connect()
    row = conn.execute("SELECT 1 FROM agents WHERE name=?", (name,)).fetchone()
    conn.close()
    return row is not None


def agent_count():
    conn = _connect()
    row = conn.execute("SELECT COUNT(*) as c FROM agents").fetchone()
    conn.close()
    return row["c"]


# --- queue operations ---


def send_message(sender, receiver, message):
    now = time.time()
    entry = {"from": sender, "message": message, "timestamp": now}
    conn = _connect()
    conn.execute(
        "INSERT INTO messages (sender, receiver, message, timestamp) VALUES (?, ?, ?, ?)",
        (sender, receiver, message, now),
    )
    conn.commit()
    conn.close()
    return entry


def read_messages(agent):
    conn = _connect()
    rows = conn.execute(
        "SELECT sender, message, timestamp FROM messages WHERE receiver=? AND read=0 ORDER BY id",
        (agent,),
    ).fetchall()
    # mark as read
    conn.execute(
        "UPDATE messages SET read=1 WHERE receiver=? AND read=0",
        (agent,),
    )
    conn.commit()
    conn.close()
    return [
        {"from": r["sender"], "message": r["message"], "timestamp": r["timestamp"]}
        for r in rows
    ]


def peek_messages(agent):
    conn = _connect()
    rows = conn.execute(
        "SELECT sender, message, timestamp FROM messages WHERE receiver=? AND read=0 ORDER BY id",
        (agent,),
    ).fetchall()
    conn.close()
    return [
        {"from": r["sender"], "message": r["message"], "timestamp": r["timestamp"]}
        for r in rows
    ]


def clear_messages(agent):
    conn = _connect()
    cursor = conn.execute(
        "UPDATE messages SET read=1 WHERE receiver=? AND read=0",
        (agent,),
    )
    conn.commit()
    cleared = cursor.rowcount > 0
    conn.close()
    return cleared


def message_count(agent):
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) as c FROM messages WHERE receiver=? AND read=0",
        (agent,),
    ).fetchone()
    conn.close()
    return row["c"]


# --- context operations ---


def set_context(owner, key, value):
    conn = _connect()
    conn.execute(
        """INSERT INTO context (owner, key, value) VALUES (?, ?, ?)
           ON CONFLICT(owner, key) DO UPDATE SET value=excluded.value""",
        (owner, key, value),
    )
    conn.commit()
    conn.close()


def get_context(owner, key):
    conn = _connect()
    row = conn.execute(
        "SELECT value FROM context WHERE owner=? AND key=?",
        (owner, key),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return row["value"]


# --- activity operations ---


def log_activity(event, **kwargs):
    conn = _connect()
    conn.execute(
        "INSERT INTO activity (event, timestamp, data) VALUES (?, ?, ?)",
        (event, time.time(), json.dumps(kwargs)),
    )
    # prune to last 100
    conn.execute(
        """DELETE FROM activity WHERE id NOT IN
           (SELECT id FROM activity ORDER BY id DESC LIMIT 100)"""
    )
    conn.commit()
    conn.close()


def get_activity():
    conn = _connect()
    rows = conn.execute(
        "SELECT event, timestamp, data FROM activity ORDER BY id DESC LIMIT 100"
    ).fetchall()
    conn.close()
    # return newest-first, but reconstruct the flat dict format
    result = []
    for r in reversed(rows):
        entry = {"event": r["event"], "timestamp": r["timestamp"]}
        entry.update(json.loads(r["data"]))
        result.append(entry)
    return result


# --- test helper ---


def reset():
    conn = _connect()
    conn.executescript("""
        DELETE FROM agents;
        DELETE FROM messages;
        DELETE FROM context;
        DELETE FROM activity;
    """)
    conn.close()


# auto-init on import
init()
