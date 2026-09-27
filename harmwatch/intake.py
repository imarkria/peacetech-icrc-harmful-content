"""One path for every source: fingerprint the post, find its content group, judge it once per group, record the
sighting. Media is downloaded to a temporary folder and deleted as soon as the post is processed.

    source (Apify, Telegram collector, community bot, screening) -> Post -> ingest() -> sightings / detections
                                                                                -> publish.py -> SignalSafe queue
"""

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from harmwatch import dedup, detect

log = logging.getLogger(__name__)


@dataclass
class Post:
    platform: str                      # telegram | facebook | instagram | tiktok | x | sample
    text: str = ""
    url: str | None = None
    post_id: str | None = None
    posted_at: str | None = None
    reach: int | None = None
    media_urls: list[tuple[str, str]] = field(default_factory=list)  # (image | video, url), downloaded when judged


@dataclass
class Ingested:
    sighting_id: int
    group_key: str
    detection: dict | None             # the row of `detections` representing the group, if it could be judged
    duplicate: bool                    # the content was already known (another copy, or this same post again)
    new: bool                          # False when this exact post had already been ingested


def ingest(post: Post, *, source: str, region: str | None = None, download=None, db=None) -> Ingested:
    conn = dedup.connect(db)
    try:
        known = dedup.known_sighting(conn, post.platform, post.post_id)
        if known:
            return Ingested(known["id"], known["group_key"], dedup.group_detection(conn, known["group_key"]),
                            duplicate=True, new=False)
        with tempfile.TemporaryDirectory(prefix="harmwatch-") as tmp:
            media = _download_all(post, Path(tmp), download) if detect.uses_local_judge() else []
            fps = dedup.fingerprints(post.text, media)
            group_key = dedup.find_group(conn, fps)
            duplicate = group_key is not None
            group_key = group_key or dedup.new_group(conn)
            dedup.add_fingerprints(conn, group_key, fps)

            detection = dedup.group_detection(conn, group_key)
            if detection is None or detection["route"] == "judge_error":  # judge once per group, retry failures
                judged = detect.detect_post(post.text, media, url=post.url, source=source, region=region, db=db)
                if judged is not None:
                    dedup.set_group_detection(conn, group_key, judged["id"])
                    detection = judged
        # the temporary folder, and every media file in it, is gone here
        sighting_id = dedup.record_sighting(conn, group_key, platform=post.platform, source=source,
                                            post_id=post.post_id, url=post.url, posted_at=post.posted_at,
                                            reach=post.reach)
        return Ingested(sighting_id, group_key, detection, duplicate=duplicate, new=True)
    finally:
        conn.close()


def _download_all(post: Post, folder: Path, download) -> list[dedup.MediaFile]:
    if download is None:
        from harmwatch.social import download_media as download
    files = []
    for kind, url in post.media_urls[:detect.MAX_MEDIA]:
        try:
            files.append(download(url, kind, folder))
        except Exception as exc:  # one broken media file must not lose the post; never log the signed URL
            log.warning("%s post %s: %s media not downloaded (%s)", post.platform, post.post_id, kind,
                        type(exc).__name__)
    return files
