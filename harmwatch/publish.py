"""Send flagged sightings to the SignalSafe review queue (POST /api/detections on the backend).

    python -m harmwatch.publish

Needs SIGNALSAFE_INGEST_TOKEN (same value as INGEST_TOKEN in backend/.env) and SIGNALSAFE_API_URL.
Each sighting carries its content group key: copies of the same content become one queue item with several
occurrences, reviewed once. Only groups routed for review are sent. Restricted groups (possible minor) are never
sent: the platform has no restricted channel yet. The post text is never sent, only the neutral summary and labels.
"""

import json
import os
import urllib.error
import urllib.request

from harmwatch import dedup
from harmwatch.detect import REVIEW_ROUTES

PUBLISH_ROUTES = REVIEW_ROUTES
COMMUNITY_SOURCES = {"telegram_bot", "community"}  # the broader local community; everything else is detection
ROUTE_LABELS = {"explicit_alert": "Explicit media", "priority_review": "Priority review",
                "standard_review": "Review", "judge_error": "Not judged"}
# The text classifiers (claude, keywords) give a confidence level, not a probability.
LEVEL_CONFIDENCE = {"high": 0.9, "medium": 0.7, "low": 0.4}


def enabled() -> bool:
    return bool(os.getenv("SIGNALSAFE_INGEST_TOKEN"))


def confidence_of(row: dict) -> float:
    """P(sexual) from the local judge when available, else the classifier's level, else the judge's scores."""
    details = json.loads(row.get("full_result_json") or "{}")
    if isinstance(details.get("p_sexual"), (int, float)):
        return round(float(details["p_sexual"]), 3)
    if details.get("confidence") in LEVEL_CONFIDENCE:
        return LEVEL_CONFIDENCE[details["confidence"]]
    scores = [s for s in (row.get("sexual_violence"), row.get("sexual_harassment")) if s is not None]
    return max(scores) / 100 if scores else 0.0


def context_of(row: dict) -> str:
    if row["route"] == "explicit_alert":
        return "Explicit media detected by the safety filter. Do not open the link without precautions."
    if row["route"] == "judge_error":
        return "The model could not judge this item. Please assess it."
    category = row.get("category") if row.get("category") not in (None, "none") else "no category"
    return f"{ROUTE_LABELS[row['route']]} ({category}). {row.get('summary') or ''}".strip()[:2000]


def to_detection(row: dict) -> dict | None:
    """Payload for POST /api/detections, or None when the sighting has no web link to review."""
    url = row.get("url") or ""
    if not url.startswith(("http://", "https://")):
        return None
    return {
        "external_id": f"s{row['id']}",
        "group_key": row["group_key"],
        "url": url,
        "predicted_category": "sexual_violence",  # the policy only covers sexual violence
        "confidence": confidence_of(row),
        "priority": row["priority"] if row["priority"] != "none" else "standard",
        "source": "PUBLIC" if row["source"] in COMMUNITY_SOURCES else "SCRAP",
        "detected_at": row["created_at"],
        "context": context_of(row),
    }


def post_json(path: str, payload: dict | None = None, method: str = "POST"):
    api_url = os.getenv("SIGNALSAFE_API_URL", "http://localhost:8000").rstrip("/")
    request = urllib.request.Request(
        f"{api_url}{path}", method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json", "X-Ingest-Token": os.environ["SIGNALSAFE_INGEST_TOKEN"]},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read() or "null")


def publish_pending(db=None) -> tuple[int, int]:
    """Send every unsent sighting of a group routed for review. Returns (sent, skipped without a web link)."""
    conn = dedup.connect(db)
    sent = skipped = 0
    try:
        for row in dedup.unpublished(conn, PUBLISH_ROUTES):
            payload = to_detection(row)
            if payload is None:
                skipped += 1
                continue
            post_json("/api/detections", payload)
            dedup.mark_published(conn, row["id"])
            sent += 1
    finally:
        conn.close()
    return sent, skipped


def main():
    from dotenv import load_dotenv

    load_dotenv()
    if not enabled():
        raise SystemExit("Set SIGNALSAFE_INGEST_TOKEN (same value as INGEST_TOKEN in backend/.env).")
    try:
        sent, skipped = publish_pending()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"The backend refused the item: {exc.code} {exc.read().decode(errors='replace')}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"Cannot reach the backend: {exc.reason}")
    print(f"Sent {sent} sightings to the review queue. Skipped {skipped} without a web link.")


if __name__ == "__main__":
    main()
