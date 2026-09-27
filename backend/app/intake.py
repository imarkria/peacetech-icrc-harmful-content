"""How reports and detections enter the review queue.

Every copy of the same content becomes an Occurrence of one DetectedLink, so it is reviewed once. Two keys group
copies: the harmwatch group key (content fingerprints: same text, same image, near-duplicates) and the normalised
URL (the same post reported several times). A copy of an already reviewed link inherits its decision.
"""

import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import PRIORITY_RANK, DetectedLink, Occurrence, ReviewStatus

HOST_ALIASES = {"twitter.com": "x.com", "fb.com": "facebook.com", "telegram.me": "t.me", "vm.tiktok.com": "tiktok.com"}
HOST_PREFIXES = ("www.", "m.", "mobile.", "web.")
TRACKING_PARAMS = {"fbclid", "igshid", "igsh", "si", "s", "t", "ref", "ref_src", "ref_url", "_rdr", "mibextid", "feature"}
PLATFORMS = {"t.me": "Telegram", "facebook.com": "Facebook", "instagram.com": "Instagram", "tiktok.com": "TikTok",
             "x.com": "X"}


def normalize_url(url: str) -> str:
    """Same post, same string: lower-case host without www/m., no fragment, no tracking parameters."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    for prefix in HOST_PREFIXES:
        if host.startswith(prefix):
            host = host[len(prefix):]
            break
    host = HOST_ALIASES.get(host, host)
    query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                   if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_"))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(query), ""))


def platform_of(url: str) -> str:
    host = urlsplit(normalize_url(url)).hostname or ""
    return PLATFORMS.get(host, "Web")


def find_group(db: Session, group_key: str | None, normalized_url: str) -> DetectedLink | None:
    conditions = [DetectedLink.normalized_url == normalized_url]
    if group_key:
        conditions.append(DetectedLink.group_key == group_key)
    return db.scalars(select(DetectedLink).where(or_(*conditions)).order_by(DetectedLink.detected_at)).first()


def add_occurrence(link: DetectedLink, *, url: str, source: str, priority: str | None = None,
                   external_id: str | None = None, reporter_id: int | None = None, note: str | None = None,
                   seen_at: datetime | None = None) -> Occurrence:
    """Attach a copy to a link and raise the link's priority if the copy is more urgent."""
    if link.status == ReviewStatus.RESTRICTED.value:
        note = None  # CH-5: nothing that describes restricted content is kept
    occurrence = Occurrence(url=url, platform=platform_of(url), source=source, external_id=external_id,
                            reporter_id=reporter_id, note=note, seen_at=seen_at or datetime.now(timezone.utc))
    link.occurrences.append(occurrence)
    link.occurrence_count = len(link.occurrences)
    if priority and PRIORITY_RANK[priority] > PRIORITY_RANK[link.priority]:
        link.priority = priority
    return occurrence


def new_link(*, link_id: str, url: str, source: str, category: str, confidence: float, priority: str, context: str,
             status: str = ReviewStatus.PENDING.value, group_key: str | None = None,
             detected_at: datetime | None = None) -> DetectedLink:
    return DetectedLink(
        id=link_id, url=url, platform=platform_of(url), predicted_category=category, confidence=confidence,
        source=source, status=status, detected_at=detected_at or datetime.now(timezone.utc), context=context,
        priority=priority, group_key=group_key, normalized_url=normalize_url(url), occurrence_count=0,
    )


class RateLimiter:
    """Sliding window per key (client IP). In memory: per API process, reset on restart. Enough for the MVP."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit, self.window = limit, window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True
