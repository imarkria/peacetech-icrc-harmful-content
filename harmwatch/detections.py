"""SQLite output for the platform: one row per analysed item in the table `detections`.

Same database file as the rest of the platform (data/harmwatch.db, or HARMWATCH_DB). This module only ADDS the table
`detections`; the tables of harmwatch/db.py are untouched. The same SQL is published in docs/platform/schema.sql
(a test checks that both stay identical).

Rule CH-5 (policy/children.md) is applied twice: by `insert_detection` (possible_minor → restricted = 1 and every
content field left empty) and by CHECK constraints in the table itself, so no code path can store content for a
restricted item. The raw media and the raw text are never stored: only a sha256 hash and the URL.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "harmwatch.db"

SCHEMA = """\
-- harmwatch: table `detections` (written by harmwatch/analyze.py, read by the platform).
-- Percentages are 0-100 integers. NULL = not computed (item not judged, restricted, or not applicable).
CREATE TABLE IF NOT EXISTS detections (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at        TEXT NOT NULL,                 -- UTC, ISO 8601
    source            TEXT,                          -- who sent the item: telegram | volunteer | extension | cli ...
    url               TEXT,                          -- where the item was seen (never the media itself)
    modality          TEXT NOT NULL CHECK (modality IN ('text', 'image', 'meme', 'video')),
    media_hash        TEXT NOT NULL,                 -- sha256 of the file (or of the text)
    filter_score      REAL,                          -- fast pre-filter P(sexual), 0-1; NULL for text (no filter)
    filter_passed     INTEGER CHECK (filter_passed IN (0, 1)),
    sexual_violence   INTEGER CHECK (sexual_violence BETWEEN 0 AND 100),
    sexual_harassment INTEGER CHECK (sexual_harassment BETWEEN 0 AND 100),
    hate              INTEGER CHECK (hate BETWEEN 0 AND 100),
    misogyny          INTEGER CHECK (misogyny BETWEEN 0 AND 100),
    other_violence    INTEGER CHECK (other_violence BETWEEN 0 AND 100),
    sexual            INTEGER CHECK (sexual IN (0, 1)),   -- decision of the AI judge
    category          TEXT,                          -- e.g. sexualised_insult, threat_incitement, none
    primary_relation  TEXT,                          -- SV-REL-1..5 (policy/core.md) or NULL
    route             TEXT NOT NULL,                 -- see docs/platform/README.md
    priority          TEXT NOT NULL CHECK (priority IN ('urgent', 'high', 'standard', 'none')),
    flagged_start_s   REAL,                          -- video: start of the flagged passage (seconds)
    flagged_end_s     REAL,                          -- video: end of the flagged passage (seconds)
    summary           TEXT,                          -- one neutral, non-graphic sentence
    explicit_alert    INTEGER NOT NULL DEFAULT 0 CHECK (explicit_alert IN (0, 1)),
    possible_minor    INTEGER NOT NULL DEFAULT 0 CHECK (possible_minor IN (0, 1)),
    restricted        INTEGER NOT NULL DEFAULT 0 CHECK (restricted IN (0, 1)),
    model             TEXT,                          -- what took the decision (judge model, pre-filter or safety filter)
    prompt_version    TEXT,                          -- frozen prompt of the judge, e.g. sv_prompt_v3
    region            TEXT NOT NULL,
    latency_ms        INTEGER,
    full_result_json  TEXT,                          -- details (no media, no raw text; reduced when restricted)
    -- CH-5: a possible minor is always restricted, and a restricted row carries no content.
    CHECK (possible_minor = 0 OR restricted = 1),
    CHECK (restricted = 0 OR (sexual_violence IS NULL AND sexual_harassment IS NULL AND hate IS NULL
                              AND misogyny IS NULL AND other_violence IS NULL AND sexual IS NULL
                              AND category IS NULL AND primary_relation IS NULL AND summary IS NULL
                              AND flagged_start_s IS NULL AND flagged_end_s IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_detections_created_at ON detections (created_at);
CREATE INDEX IF NOT EXISTS idx_detections_priority ON detections (priority);
CREATE INDEX IF NOT EXISTS idx_detections_sexual ON detections (sexual);
"""

COLUMNS = ("created_at", "source", "url", "modality", "media_hash", "filter_score", "filter_passed",
           "sexual_violence", "sexual_harassment", "hate", "misogyny", "other_violence", "sexual", "category",
           "primary_relation", "route", "priority", "flagged_start_s", "flagged_end_s", "summary", "explicit_alert",
           "possible_minor", "restricted", "model", "prompt_version", "region", "latency_ms", "full_result_json")
# Emptied for restricted rows (CH-5): nothing that describes the content may be stored.
CONTENT_FIELDS = ("sexual_violence", "sexual_harassment", "hate", "misogyny", "other_violence", "sexual", "category",
                  "primary_relation", "summary", "flagged_start_s", "flagged_end_s")
RESTRICTED_JSON_KEYS = ("modality", "restricted_reason", "rule_notes", "explicit_alert", "filter", "error")


def db_path() -> Path:
    """HARMWATCH_DB if set (read at call time), else data/harmwatch.db like harmwatch/db.py."""
    return Path(os.getenv("HARMWATCH_DB") or DEFAULT_DB)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    p = Path(path) if path else db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def apply_ch5(row: dict) -> dict:
    """possible_minor → restricted = 1, content fields empty, details reduced to non-content keys."""
    row = dict(row)
    if row.get("possible_minor"):
        row["restricted"] = 1
    if row.get("restricted"):
        for k in CONTENT_FIELDS:
            row[k] = None
        full = row.get("full_result_json")
        if isinstance(full, str):
            full = json.loads(full)
        if isinstance(full, dict):
            row["full_result_json"] = {k: full[k] for k in RESTRICTED_JSON_KEYS if k in full} | {"restricted": True}
    return row


def insert_detection(conn: sqlite3.Connection, row: dict) -> int:
    """Insert one detection (CH-5 applied first); returns its id."""
    unknown = set(row) - set(COLUMNS)
    if unknown:
        raise ValueError(f"unknown detections columns: {sorted(unknown)}")
    row = apply_ch5({"created_at": now(), **row})
    if isinstance(row.get("full_result_json"), dict):
        row["full_result_json"] = json.dumps(row["full_result_json"], ensure_ascii=False)
    for k in ("filter_passed", "sexual", "explicit_alert", "possible_minor", "restricted"):
        if isinstance(row.get(k), bool):
            row[k] = int(row[k])
    cols = [c for c in COLUMNS if c in row]
    cur = conn.execute(f"INSERT INTO detections ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                       [row[c] for c in cols])
    conn.commit()
    return cur.lastrowid


def get_detection(conn: sqlite3.Connection, detection_id: int) -> dict | None:
    r = conn.execute("SELECT * FROM detections WHERE id = ?", (detection_id,)).fetchone()
    return dict(r) if r else None
