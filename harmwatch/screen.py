"""Screen community reports with the model before they reach reviewers.

    python -m harmwatch.screen            # once
    python -m harmwatch.screen --every 60 # keep polling (seconds)

The backend holds anonymous community reports (web form, browser extension) in SCREENING. For each one this fetches
the post (Apify for Facebook, Instagram, TikTok and X; the collector's Telegram session for t.me links), runs it
through intake (same duplicate groups and judge as detection) and sends the outcome back:

    flagged      -> queue, with the model's priority        not_flagged -> queue, lowest priority (never dropped)
    restricted   -> hidden, never shown (possible minor)    unavailable -> queue, marked "not screened"

A report of content already in the queue is merged into it. Reports the backend does not hear back about reach the
queue anyway after SCREENING_TIMEOUT_MINUTES.
"""

import argparse
import logging
import time
from collections import Counter
from urllib.parse import urlsplit

from harmwatch import dedup, publish
from harmwatch.detect import REVIEW_ROUTES
from harmwatch.intake import Post, ingest

log = logging.getLogger(__name__)


def fetch_post(url: str) -> Post | None:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    if host in ("t.me", "telegram.me"):
        from harmwatch.collector import fetch_telegram_post

        return fetch_telegram_post(url)
    from harmwatch.social import fetch_url

    return fetch_url(url)


def outcome_for(post: Post | None, region: str | None = None, db=None) -> dict:
    if post is None:
        return {"outcome": "unavailable"}
    result = ingest(post, source="community", region=region, db=db)
    conn = dedup.connect(db)
    try:  # the report itself carries this sighting to the platform: publish.py must not send it again
        dedup.mark_published(conn, result.sighting_id)
    finally:
        conn.close()
    d = result.detection
    if d is None:
        return {"outcome": "unavailable", "group_key": result.group_key}
    if d["restricted"]:
        return {"outcome": "restricted"}
    if d["route"] in REVIEW_ROUTES:
        return {"outcome": "flagged", "priority": d["priority"] if d["priority"] != "none" else "standard",
                "confidence": publish.confidence_of(d), "summary": publish.context_of(d)[:1000],
                "group_key": result.group_key}
    return {"outcome": "not_flagged", "summary": (d.get("summary") or "")[:1000], "group_key": result.group_key}


def screen_pending(region: str | None = None, fetch=fetch_post, db=None) -> Counter:
    stats = Counter()
    for item in publish.post_json("/api/intake/screening", method="GET"):
        try:
            result = outcome_for(fetch(item["url"]), region=region, db=db)
        except Exception as exc:  # one failing report must not block the others
            log.warning("report %s: %s", item["id"], type(exc).__name__)
            result = {"outcome": "unavailable"}
        publish.post_json(f"/api/intake/screening/{item['id']}", result)
        stats[result["outcome"]] += 1
    return stats


def main():
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--every", type=int, help="poll again every N seconds")
    parser.add_argument("--region", help="policy region (default: REGION or global)")
    args = parser.parse_args()
    if not publish.enabled():
        raise SystemExit("Set SIGNALSAFE_INGEST_TOKEN (same value as INGEST_TOKEN in backend/.env).")
    while True:
        stats = screen_pending(region=args.region)
        print("Screened: " + (", ".join(f"{k} {v}" for k, v in stats.items()) or "nothing waiting"))
        if not args.every:
            break
        time.sleep(args.every)


if __name__ == "__main__":
    main()
