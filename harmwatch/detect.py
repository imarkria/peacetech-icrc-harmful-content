"""Judge one post (text + downloaded media) and return the row of `detections` that represents it.

- CLASSIFIER=local (default): our Qwen model through `harmwatch.analyze` (safety filter, pre-filter, judge) on the
  text and on each media file. Needs the judge server (scripts/serve_llm.sh). The post keeps its most serious row.
- CLASSIFIER=keywords: offline baseline for tests and demos, text only, written to `detections` in the same shape.
  Media is not analysed in this mode; a media-only post gets no row.
"""

import hashlib
import os

from harmwatch import detections
from harmwatch.classify import backend_name, classify
from harmwatch.dedup import MediaFile
from harmwatch.triage import ESCALATE, HARMFUL, NOT_HARMFUL, POTENTIAL, triage

MAX_MEDIA = 4  # media files judged per post
# Most serious first. The routes are those of harmwatch/analyze.py (docs/platform/README.md).
ROUTE_RANK = {"restricted_escalation": 6, "explicit_alert": 5, "priority_review": 4, "standard_review": 3,
              "judge_error": 2, "not_flagged": 1, "filtered_out": 0}
REVIEW_ROUTES = ("explicit_alert", "priority_review", "standard_review", "judge_error")
BUCKET_ROUTES = {ESCALATE: ("restricted_escalation", "urgent"), HARMFUL: ("priority_review", "high"),
                 POTENTIAL: ("standard_review", "standard"), NOT_HARMFUL: ("not_flagged", "none")}


def uses_local_judge() -> bool:
    return backend_name() == "local"


def default_region() -> str:
    return os.getenv("REGION", "global")


def detect_post(text: str, media: list[MediaFile], *, url: str | None, source: str, region: str | None = None,
                db=None) -> dict | None:
    region = region or default_region()
    rows = []
    if uses_local_judge():
        from harmwatch.analyze import analyze

        if text.strip():
            rows.append(analyze({"modality": "text", "text": text, "url": url, "source": source}, region=region))
        for m in media[:MAX_MEDIA]:
            rows.append(analyze({"modality": m.kind, "path": str(m.path), "url": url, "source": source}, region=region))
    elif text.strip():
        rows.append(classify_text(text, url=url, source=source, region=region, db=db))
    return max(rows, key=lambda r: ROUTE_RANK.get(r["route"], 0)) if rows else None


def classify_text(text: str, *, url: str | None, source: str, region: str, db=None) -> dict:
    """Keyword baseline classification of the text, stored as a `detections` row (CH-5 applied by insert)."""
    c, backend = classify(text)
    bucket = triage(c)
    route, priority = BUCKET_ROUTES[bucket]
    flagged = bucket in (HARMFUL, POTENTIAL)
    row = {
        "source": source, "url": url, "modality": "text", "region": region, "model": backend,
        "media_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "sexual": int(flagged), "category": c.harm_types[0] if c.harm_types else "none",
        "route": route, "priority": priority, "summary": c.summary, "possible_minor": int(bucket == ESCALATE),
        "full_result_json": {"classifier": backend, "bucket": bucket, "harm_types": c.harm_types,
                             "confidence": c.confidence, "rationale": c.rationale},
    }
    conn = detections.connect(db)
    try:
        return detections.get_detection(conn, detections.insert_detection(conn, row))
    finally:
        conn.close()
