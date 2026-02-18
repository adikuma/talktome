import json
import os
import sqlite3
import time

# store the database in the user home directory so it persists across projects
DB_DIR = os.path.join(os.path.expanduser("~"), ".talktome")
DB_PATH = os.path.join(DB_DIR, "bridge.db")


# open a connection to the sqlite database with wal mode for concurrency
def connect():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# create all tables if they do not already exist
def init():
    conn = connect()
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

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            agent TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            result TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            timestamp REAL NOT NULL,
            data TEXT NOT NULL DEFAULT '{}'
        );
    """)
    conn.close()


# registry operations, manage agent registration and status
# register or update an agent with its name and project path
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
    conn = connect()
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


# remove an agent from the registry by name
def deregister(name):
    conn = connect()
    cursor = conn.execute("DELETE FROM agents WHERE name=?", (name,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


# fetch a single agent record by name, returns none if not found
def get_agent(name):
    conn = connect()
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


# return a sorted list of all registered agent names
def list_agents():
    conn = connect()
    rows = conn.execute("SELECT name FROM agents ORDER BY name").fetchall()
    conn.close()
    return [row["name"] for row in rows]


# change an agents status and update its last seen timestamp
def update_status(name, status):
    conn = connect()
    cursor = conn.execute(
        "UPDATE agents SET status=?, last_seen=? WHERE name=?",
        (status, time.time(), name),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


# replace the metadata json blob for an agent
def update_metadata(name, metadata):
    conn = connect()
    cursor = conn.execute(
        "UPDATE agents SET metadata=? WHERE name=?",
        (json.dumps(metadata), name),
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


# check if an agent with this name exists in the registry
def is_registered(name):
    conn = connect()
    row = conn.execute("SELECT 1 FROM agents WHERE name=?", (name,)).fetchone()
    conn.close()
    return row is not None


# return the total number of registered agents
def agent_count():
    conn = connect()
    row = conn.execute("SELECT COUNT(*) as c FROM agents").fetchone()
    conn.close()
    return row["c"]


# queue operations, store and retrieve messages between agents
# insert a new message into the mailbox for the receiver
def send_message(sender, receiver, message):
    now = time.time()
    entry = {"from": sender, "message": message, "timestamp": now}
    conn = connect()
    conn.execute(
        "INSERT INTO messages (sender, receiver, message, timestamp) VALUES (?, ?, ?, ?)",
        (sender, receiver, message, now),
    )
    conn.commit()
    conn.close()
    return entry


# read all unread messages for an agent and mark them as read
def read_messages(agent):
    conn = connect()
    rows = conn.execute(
        "SELECT sender, message, timestamp FROM messages WHERE receiver=? AND read=0 ORDER BY id",
        (agent,),
    ).fetchall()
    # mark all fetched messages as read so they are not returned again
    conn.execute(
        "UPDATE messages SET read=1 WHERE receiver=? AND read=0",
        (agent,),
    )
    conn.commit()
    conn.close()
    return [
        {"from": r["sender"], "message": r["message"], "timestamp": r["timestamp"]} for r in rows
    ]


# peek at unread messages without marking them as read
def peek_messages(agent):
    conn = connect()
    rows = conn.execute(
        "SELECT sender, message, timestamp FROM messages WHERE receiver=? AND read=0 ORDER BY id",
        (agent,),
    ).fetchall()
    conn.close()
    return [
        {"from": r["sender"], "message": r["message"], "timestamp": r["timestamp"]} for r in rows
    ]


# mark all unread messages for an agent as read without returning them
def clear_messages(agent):
    conn = connect()
    cursor = conn.execute(
        "UPDATE messages SET read=1 WHERE receiver=? AND read=0",
        (agent,),
    )
    conn.commit()
    cleared = cursor.rowcount > 0
    conn.close()
    return cleared


# count the number of unread messages waiting for an agent
def message_count(agent):
    conn = connect()
    row = conn.execute(
        "SELECT COUNT(*) as c FROM messages WHERE receiver=? AND read=0",
        (agent,),
    ).fetchone()
    conn.close()
    return row["c"]


# task operations, create and manage tasks assigned to agents
# create a new task with pending status assigned to an agent
def create_task(task_id, agent, description):
    now = time.time()
    conn = connect()
    conn.execute(
        "INSERT INTO tasks (id, agent, description, status, created_at, updated_at) VALUES (?, ?, ?, 'pending', ?, ?)",
        (task_id, agent, description, now, now),
    )
    conn.commit()
    conn.close()
    return {
        "id": task_id,
        "agent": agent,
        "description": description,
        "status": "pending",
        "result": None,
        "created_at": now,
        "updated_at": now,
    }


# fetch a single task by its id, returns none if not found
def get_task(task_id):
    conn = connect()
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "id": row["id"],
        "agent": row["agent"],
        "description": row["description"],
        "status": row["status"],
        "result": row["result"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# return all tasks sorted by newest first
def get_tasks():
    conn = connect()
    rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "agent": r["agent"],
            "description": r["description"],
            "status": r["status"],
            "result": r["result"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


# return all tasks assigned to a specific agent, newest first
def get_agent_tasks(agent):
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE agent=? ORDER BY created_at DESC", (agent,)
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "agent": r["agent"],
            "description": r["description"],
            "status": r["status"],
            "result": r["result"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


# return only pending tasks for an agent, oldest first so they process in order
def get_pending_tasks(agent):
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE agent=? AND status='pending' ORDER BY created_at",
        (agent,),
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "agent": r["agent"],
            "description": r["description"],
            "status": r["status"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


# update a tasks status and optional result, returns none if task not found
def update_task(task_id, status=None, result=None):
    conn = connect()
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if row is None:
        conn.close()
        return None
    new_status = status or row["status"]
    new_result = result if result is not None else row["result"]
    now = time.time()
    conn.execute(
        "UPDATE tasks SET status=?, result=?, updated_at=? WHERE id=?",
        (new_status, new_result, now, task_id),
    )
    conn.commit()
    conn.close()
    return {
        "id": task_id,
        "agent": row["agent"],
        "description": row["description"],
        "status": new_status,
        "result": new_result,
        "created_at": row["created_at"],
        "updated_at": now,
    }


# context operations, key value store scoped per agent


# store or overwrite a context value for an agent
def set_context(owner, key, value):
    conn = connect()
    conn.execute(
        """INSERT INTO context (owner, key, value) VALUES (?, ?, ?)
           ON CONFLICT(owner, key) DO UPDATE SET value=excluded.value""",
        (owner, key, value),
    )
    conn.commit()
    conn.close()


# retrieve a context value for an agent, returns none if not set
def get_context(owner, key):
    conn = connect()
    row = conn.execute(
        "SELECT value FROM context WHERE owner=? AND key=?",
        (owner, key),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return row["value"]


# activity operations, log and retrieve recent events for the dashboard


# record an activity event with arbitrary keyword data
def log_activity(event, **kwargs):
    conn = connect()
    conn.execute(
        "INSERT INTO activity (event, timestamp, data) VALUES (?, ?, ?)",
        (event, time.time(), json.dumps(kwargs)),
    )
    # keep only the last 100 entries to prevent unbounded growth
    conn.execute(
        """DELETE FROM activity WHERE id NOT IN
           (SELECT id FROM activity ORDER BY id DESC LIMIT 100)"""
    )
    conn.commit()
    conn.close()


# return the last 100 activity events as a list of flat dicts
def get_activity():
    conn = connect()
    rows = conn.execute(
        "SELECT event, timestamp, data FROM activity ORDER BY id DESC LIMIT 100"
    ).fetchall()
    conn.close()
    # merge the json data back into each event dict for a flat structure
    result = []
    for r in reversed(rows):
        entry = {"event": r["event"], "timestamp": r["timestamp"]}
        entry.update(json.loads(r["data"]))
        result.append(entry)
    return result


# test helper, wipes all data from every table


# clear all tables, used by tests to reset state between runs
def reset():
    conn = connect()
    conn.executescript("""
        DELETE FROM agents;
        DELETE FROM messages;
        DELETE FROM context;
        DELETE FROM tasks;
        DELETE FROM activity;
    """)
    conn.close()


# automatically create tables when the module is first imported
init()
