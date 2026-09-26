"""SQLite storage. The database lives in data/ (git-ignored)."""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from harmwatch.schema import Classification

DB_PATH = Path(os.getenv("HARMWATCH_DB", Path(__file__).resolve().parent.parent / "data" / "harmwatch.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id          INTEGER PRIMARY KEY,
    source      TEXT NOT NULL,          -- telegram | volunteer | sample
    channel     TEXT,
    side        TEXT,                   -- optional, for neutrality checks
    url         TEXT,
    text        TEXT NOT NULL,
    posted_at   TEXT,
    views       INTEGER,
    forwards    INTEGER,
    reporter    TEXT,                   -- volunteer who flagged it
    note        TEXT,                   -- volunteer context
    platform    TEXT,                   -- reported by an outside user
    location    TEXT,
    targets     TEXT,                   -- JSON list, e.g. ["child", "woman"]
    kinds       TEXT,                   -- JSON list, e.g. ["threat"]
    contact     TEXT,                   -- empty = anonymous
    created_at  TEXT NOT NULL,
    UNIQUE (channel, url)
);
CREATE TABLE IF NOT EXISTS classifications (
    post_id     INTEGER PRIMARY KEY REFERENCES posts(id),
    backend     TEXT NOT NULL,
    result      TEXT NOT NULL,          -- Classification JSON
    bucket      TEXT NOT NULL,
    priority    REAL NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY,
    post_id     INTEGER NOT NULL REFERENCES posts(id),
    decision    TEXT NOT NULL,          -- yes | no | not_processed
    note        TEXT,
    reviewer    TEXT,
    created_at  TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


REPORT_COLUMNS = ["platform", "location", "targets", "kinds", "contact"]


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(posts)")}
    for column in REPORT_COLUMNS:  # databases created before these columns existed
        if column not in existing:
            conn.execute(f"ALTER TABLE posts ADD COLUMN {column} TEXT")
    return conn


def add_post(conn, *, source, text, channel=None, side=None, url=None, posted_at=None,
             views=None, forwards=None, reporter=None, note=None, platform=None,
             location=None, targets=None, kinds=None, contact=None) -> int | None:
    """Insert a post; returns its id, or None if it was already stored."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO posts (source, channel, side, url, text, posted_at, views, forwards,"
        " reporter, note, platform, location, targets, kinds, contact, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (source, channel, side, url, text, posted_at, views, forwards, reporter, note, platform, location,
         json.dumps(targets) if targets else None, json.dumps(kinds) if kinds else None, contact, now()),
    )
    conn.commit()
    return cur.lastrowid if cur.rowcount else None


def get_post(conn, post_id: int) -> sqlite3.Row:
    return conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()


def unclassified(conn) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT p.* FROM posts p LEFT JOIN classifications c ON c.post_id = p.id WHERE c.post_id IS NULL"
    ).fetchall()


def save_classification(conn, post_id: int, backend: str, c: Classification, bucket: str, priority: float):
    conn.execute(
        "INSERT OR REPLACE INTO classifications VALUES (?,?,?,?,?,?)",
        (post_id, backend, c.model_dump_json(), bucket, priority, now()),
    )
    conn.commit()


def save_decision(conn, post_id: int, decision: str, note: str, reviewer: str):
    conn.execute(
        "INSERT INTO decisions (post_id, decision, note, reviewer, created_at) VALUES (?,?,?,?,?)",
        (post_id, decision, note, reviewer, now()),
    )
    conn.commit()


def queue(conn, include_decided: bool = False) -> list[dict]:
    """Classified posts with their latest decision, highest priority first."""
    rows = conn.execute(
        """
        SELECT p.*, c.backend, c.result, c.bucket, c.priority,
               (SELECT decision FROM decisions d WHERE d.post_id = p.id ORDER BY d.id DESC LIMIT 1) AS decision
        FROM posts p JOIN classifications c ON c.post_id = p.id
        ORDER BY c.priority DESC, p.id
        """
    ).fetchall()
    items = [
        dict(r) | {
            "result": Classification(**json.loads(r["result"])),
            "targets": json.loads(r["targets"]) if r["targets"] else [],
            "kinds": json.loads(r["kinds"]) if r["kinds"] else [],
        }
        for r in rows
    ]
    return items if include_decided else [i for i in items if i["decision"] is None]


def export_decisions(conn) -> list[dict]:
    """Human decisions joined with model labels: the feedback dataset."""
    rows = conn.execute(
        """
        SELECT p.id, p.channel, p.side, p.text, c.backend, c.result, c.bucket, d.decision, d.note, d.created_at
        FROM decisions d JOIN posts p ON p.id = d.post_id JOIN classifications c ON c.post_id = p.id
        ORDER BY d.id
        """
    ).fetchall()
    return [dict(r) | {"result": json.loads(r["result"])} for r in rows]
