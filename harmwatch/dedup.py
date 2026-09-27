"""Duplicate content: the same post, image or video seen several times (reposts, copies across platforms).

Every sighting joins a content group. The AI judge runs once per group, and the platform shows the group once with
all its copies, so one human decision covers every copy.

Fingerprints (the raw text and media are never stored, only these hashes):
- text_sha      sha256 of the normalised text, when it has at least MIN_WORDS_EXACT words
- text_simhash  64-bit SimHash of character 3-grams, when it has at least MIN_WORDS_NEAR words;
                near = Hamming <= SIMHASH_MAX. Measured on the sample posts: reposts with "RT @x:", "Forwarded
                from", added emojis or one word changed are 3-8 bits away; unrelated posts on the same topic 17+.
- media_sha     sha256 of the file
- media_phash   64-bit perceptual hash of an image; near = Hamming <= PHASH_MAX

Short texts never match: "Glory to Ukraine" is not a copy of every other post that says it. PHASH_MAX is kept tight
because memes made from the same template differ only by their text. A sighting joins the first group that matches
(exact fingerprints first); two existing groups are never merged.

Tables (same file as `detections`, data/harmwatch.db or HARMWATCH_DB):
    content_groups  one row per group, with the detection that represents it
    fingerprints    (kind, value) -> group
    sightings       where and when each copy was seen, and whether it was sent to the platform
"""

import hashlib
import re
import sqlite3
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path

from harmwatch import detections

MIN_WORDS_EXACT = 5
MIN_WORDS_NEAR = 8
SIMHASH_MAX = 9
PHASH_MAX = 4

SCHEMA = """
CREATE TABLE IF NOT EXISTS content_groups (
    group_key     TEXT PRIMARY KEY,
    detection_id  INTEGER REFERENCES detections(id),   -- the judgement that represents the group
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fingerprints (
    kind       TEXT NOT NULL CHECK (kind IN ('text_sha', 'text_simhash', 'media_sha', 'media_phash')),
    value      TEXT NOT NULL,
    group_key  TEXT NOT NULL REFERENCES content_groups(group_key),
    UNIQUE (kind, value)
);
CREATE TABLE IF NOT EXISTS sightings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    group_key     TEXT NOT NULL REFERENCES content_groups(group_key),
    platform      TEXT NOT NULL,        -- telegram | facebook | instagram | tiktok | x | sample
    post_id       TEXT,                 -- platform id, used to skip posts already seen
    url           TEXT,
    source        TEXT NOT NULL,        -- telegram | apify:<platform> | telegram_bot | community | sample
    posted_at     TEXT,
    reach         INTEGER,              -- views or plays when the platform gives them
    created_at    TEXT NOT NULL,
    published_at  TEXT,                 -- sent to the SignalSafe review queue
    UNIQUE (platform, post_id)
);
CREATE INDEX IF NOT EXISTS idx_sightings_group ON sightings (group_key);
"""


@dataclass
class MediaFile:
    kind: str  # image | video
    path: Path


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    conn = detections.connect(path)
    conn.executescript(SCHEMA)
    return conn


# --- fingerprints -------------------------------------------------------------------------------------------------

_URL = re.compile(r"https?://\S+|www\.\S+")
_MENTION = re.compile(r"@\w+")
_NON_WORD = re.compile(r"[^\w\s]+")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = _MENTION.sub(" ", _URL.sub(" ", text))
    return " ".join(_NON_WORD.sub(" ", text).split())


def simhash(normalised: str) -> int:
    shingles = [normalised[i:i + 3] for i in range(max(1, len(normalised) - 2))]
    weights = [0] * 64
    for shingle in shingles:
        h = int.from_bytes(hashlib.blake2b(shingle.encode(), digest_size=8).digest(), "big")
        for bit in range(64):
            weights[bit] += 1 if h >> bit & 1 else -1
    return sum(1 << bit for bit in range(64) if weights[bit] > 0)


def image_phash(path: Path) -> int | None:
    try:
        from PIL import Image

        from harmwatch.cascade import phash
    except ImportError:  # imagehash not installed: exact media matching only
        return None
    try:
        with Image.open(path) as img:
            return phash(img)
    except OSError:
        return None


def fingerprints(text: str, media: list[MediaFile]) -> list[tuple[str, str]]:
    fps = []
    normalised = normalize_text(text)
    words = normalised.split()
    if len(words) >= MIN_WORDS_EXACT:
        fps.append(("text_sha", hashlib.sha256(normalised.encode()).hexdigest()))
    if len(words) >= MIN_WORDS_NEAR:
        fps.append(("text_simhash", f"{simhash(normalised):016x}"))
    for m in media:
        fps.append(("media_sha", hashlib.sha256(m.path.read_bytes()).hexdigest()))
        if m.kind == "image" and (p := image_phash(m.path)) is not None:
            fps.append(("media_phash", f"{p:016x}"))
    return fps


# --- groups -------------------------------------------------------------------------------------------------------

NEAR_LIMITS = {"text_simhash": SIMHASH_MAX, "media_phash": PHASH_MAX}


def find_group(conn, fps: list[tuple[str, str]]) -> str | None:
    """Exact match first (any kind), then the closest near match within the limits."""
    for kind, value in fps:
        row = conn.execute("SELECT group_key FROM fingerprints WHERE kind = ? AND value = ?", (kind, value)).fetchone()
        if row:
            return row["group_key"]
    best = None
    for kind, value in fps:
        if kind not in NEAR_LIMITS:
            continue
        target = int(value, 16)
        for row in conn.execute("SELECT value, group_key FROM fingerprints WHERE kind = ?", (kind,)):
            distance = (int(row["value"], 16) ^ target).bit_count()
            if distance <= NEAR_LIMITS[kind] and (best is None or distance < best[0]):
                best = (distance, row["group_key"])
    return best[1] if best else None


def new_group(conn) -> str:
    key = f"g-{uuid.uuid4().hex[:16]}"
    conn.execute("INSERT INTO content_groups (group_key, created_at) VALUES (?, ?)", (key, detections.now()))
    conn.commit()
    return key


def add_fingerprints(conn, group_key: str, fps: list[tuple[str, str]]):
    conn.executemany("INSERT OR IGNORE INTO fingerprints (kind, value, group_key) VALUES (?, ?, ?)",
                     [(kind, value, group_key) for kind, value in fps])
    conn.commit()


def group_detection(conn, group_key: str) -> dict | None:
    row = conn.execute("SELECT d.* FROM content_groups g JOIN detections d ON d.id = g.detection_id "
                       "WHERE g.group_key = ?", (group_key,)).fetchone()
    return dict(row) if row else None


def set_group_detection(conn, group_key: str, detection_id: int):
    conn.execute("UPDATE content_groups SET detection_id = ? WHERE group_key = ?", (detection_id, group_key))
    conn.commit()


# --- sightings ----------------------------------------------------------------------------------------------------

def known_sighting(conn, platform: str, post_id: str | None) -> dict | None:
    if not post_id:
        return None
    row = conn.execute("SELECT * FROM sightings WHERE platform = ? AND post_id = ?", (platform, post_id)).fetchone()
    return dict(row) if row else None


def record_sighting(conn, group_key: str, *, platform: str, source: str, post_id: str | None = None,
                    url: str | None = None, posted_at: str | None = None, reach: int | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO sightings (group_key, platform, post_id, url, source, posted_at, reach, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (group_key, platform, post_id, url, source, posted_at, reach, detections.now()),
    )
    conn.commit()
    return cur.lastrowid


def unpublished(conn, routes: tuple[str, ...]) -> list[dict]:
    """Sightings not yet sent whose group was judged into one of `routes`. Restricted groups never qualify."""
    marks = ",".join("?" * len(routes))
    rows = conn.execute(
        f"""
        SELECT s.id, s.group_key, s.platform, s.url, s.source, s.created_at, s.reach,
               d.route, d.priority, d.category, d.summary, d.sexual_violence, d.sexual_harassment,
               d.full_result_json, d.model
        FROM sightings s
        JOIN content_groups g ON g.group_key = s.group_key
        JOIN detections d ON d.id = g.detection_id
        WHERE s.published_at IS NULL AND d.restricted = 0 AND d.route IN ({marks})
        ORDER BY s.id
        """,
        routes,
    ).fetchall()
    return [dict(r) for r in rows]


def mark_published(conn, sighting_id: int):
    conn.execute("UPDATE sightings SET published_at = ? WHERE id = ?", (detections.now(), sighting_id))
    conn.commit()
