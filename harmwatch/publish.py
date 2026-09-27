"""Send flagged posts to the SignalSafe review queue (POST /api/detections on the backend).

    python -m harmwatch.publish

Needs SIGNALSAFE_INGEST_TOKEN (same value as INGEST_TOKEN in backend/.env) and SIGNALSAFE_API_URL.
Only Harmful and Potentially harmful posts are sent. Escalated posts (possible minor) are never sent:
the platform has no restricted handling for them yet. The post text is not sent either, only the
neutral summary and the labels; reviewers open the link to see the post.
"""

import json
import os
import urllib.error
import urllib.request

from harmwatch import db
from harmwatch.triage import HARMFUL, POTENTIAL

PUBLISHED_BUCKETS = (HARMFUL, POTENTIAL)
BUCKET_LABELS = {HARMFUL: "Harmful", POTENTIAL: "Potentially harmful"}
# The classifiers give a confidence level, not a probability; the queue shows a percentage.
CONFIDENCE = {"high": 0.9, "medium": 0.7, "low": 0.4}


def enabled() -> bool:
    return bool(os.getenv("SIGNALSAFE_INGEST_TOKEN"))


def to_detection(item: dict) -> dict | None:
    """Payload for POST /api/detections, or None when the post has no web link to review."""
    url = item["url"] or ""
    if not url.startswith(("http://", "https://")):
        return None
    c = item["result"]
    labels = ", ".join(c.harm_types) or "no harm type"
    context = f"{BUCKET_LABELS[item['bucket']]} ({labels}). {c.summary} {c.rationale}".strip()
    return {
        "external_id": str(item["id"]),
        "url": url,
        "predicted_category": "sexual_violence",  # the policy only covers sexual violence
        "confidence": CONFIDENCE[c.confidence],
        "source": "PUBLIC" if item["source"] == "volunteer" else "SCRAP",
        "detected_at": item["classified_at"],
        "context": context[:2000],
    }


def _post(api_url: str, token: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/detections",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Ingest-Token": token},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read())


def publish_pending(conn) -> tuple[int, int]:
    """Send every unpublished flagged post. Returns (sent, skipped without a web link)."""
    api_url = os.getenv("SIGNALSAFE_API_URL", "http://localhost:8000")
    token = os.environ["SIGNALSAFE_INGEST_TOKEN"]
    sent = skipped = 0
    for item in db.unpublished(conn, PUBLISHED_BUCKETS):
        payload = to_detection(item)
        if payload is None:
            skipped += 1
            continue
        link = _post(api_url, token, payload)
        db.mark_published(conn, item["id"], link["id"])
        sent += 1
    return sent, skipped


def main():
    if not enabled():
        raise SystemExit("Set SIGNALSAFE_INGEST_TOKEN (same value as INGEST_TOKEN in backend/.env).")
    with db.connect() as conn:
        try:
            sent, skipped = publish_pending(conn)
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"The backend refused the post: {exc.code} {exc.read().decode(errors='replace')}")
        except urllib.error.URLError as exc:
            raise SystemExit(f"Cannot reach the backend: {exc.reason}")
    print(f"Sent {sent} posts to the review queue. Skipped {skipped} without a web link.")


if __name__ == "__main__":
    main()
