"""Collect public posts from Facebook, Instagram, TikTok and X through Apify, and send them through intake.

    python -m harmwatch.social --query "keyword" --platform facebook instagram tiktok x --max-items 20
    python -m harmwatch.social --platform tiktok --dataset-id <id>      # reuse a finished Apify run, no new cost

Needs APIFY_TOKEN. Each platform uses one Apify Actor for search and one for single post URLs (used by
`harmwatch.screen` for community reports); every Actor can be replaced with APIFY_<PLATFORM>_<SEARCH|URL>_ACTOR.
Actor runs cost money: --max-items caps each run.

Media is downloaded only when the local judge is on (CLASSIFIER=local), only from the platform's own CDN hosts, with
a size cap, into a temporary folder that is deleted after the post is judged. Nothing but hashes and URLs is kept.
"""

import argparse
import logging
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from harmwatch.dedup import MediaFile
from harmwatch.intake import Post, ingest

log = logging.getLogger(__name__)

MAX_BYTES = {"image": 15 * 1024 * 1024, "video": 100 * 1024 * 1024}
CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
                 "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic")
VIDEO_EXT = (".mp4", ".webm", ".mov", ".m3u8")
# Subtrees that describe people, not the post: never collected as media (avatars, profile pictures).
PERSON_KEYS = ("author", "owner", "user", "profile", "avatar", "music")


@dataclass
class Adapter:
    platform: str
    search_actor: str
    url_actor: str
    search_input: Callable[[str, int, bool], dict]
    url_input: Callable[[str, bool], dict]
    parse: Callable[[dict], Post | None]
    hosts: tuple[str, ...]  # CDN hosts media may be downloaded from
    url_hosts: tuple[str, ...]  # hosts of the post URLs this adapter can fetch

    def actor(self, kind: str) -> str:
        default = self.search_actor if kind == "search" else self.url_actor
        return os.getenv(f"APIFY_{self.platform.upper()}_{kind.upper()}_ACTOR", default)


# --- helpers ------------------------------------------------------------------------------------------------------

def _host_ok(url: str, hosts: tuple[str, ...]) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(host == h or host.endswith("." + h) for h in hosts)


def _kind(url: str) -> str | None:
    path = urlsplit(url).path.lower()
    return "image" if path.endswith(IMAGE_EXT) else "video" if path.endswith(VIDEO_EXT) else None


def cdn_media(item, hosts: tuple[str, ...]) -> list[tuple[str, str]]:
    """Every media URL on the platform's CDN found anywhere in an Actor item, skipping people's pictures."""
    found = []

    def visit(value, key=""):
        if any(k in key.lower() for k in PERSON_KEYS):
            return
        if isinstance(value, dict):
            for k, v in value.items():
                visit(v, k)
        elif isinstance(value, list):
            for v in value:
                visit(v, key)
        elif isinstance(value, str) and _host_ok(value, hosts) and (kind := _kind(value)):
            if (kind, value) not in found:
                found.append((kind, value))

    visit(item)
    return found


def _merge(first: list[tuple[str, str]], rest: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return list(dict.fromkeys([m for m in first if m[1]] + rest))


def _iso(value) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc).isoformat()
    return str(value)


def _int(value) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _get(obj, *names):
    """apify-client returns dicts (v1) or objects (v2)."""
    for name in names:
        value = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
        if value is not None:
            return value
    return None


# --- platforms ----------------------------------------------------------------------------------------------------

def parse_facebook(item: dict) -> Post | None:
    post_id = item.get("post_id") or item.get("postId")
    if not post_id:
        return None
    videos = item.get("video_files") or {}
    known = [("video", videos.get("video_sd_file")), ("video", videos.get("video_hd_file"))] if isinstance(videos, dict) else []
    return Post(
        platform="facebook", post_id=str(post_id), text=item.get("message") or item.get("text") or "",
        url=item.get("url") or item.get("post_url") or f"https://www.facebook.com/{post_id}",
        posted_at=_iso(item.get("timestamp") or item.get("time")),
        reach=_int(item.get("reactions_count") or item.get("likes")),
        media_urls=_merge(known[:1], cdn_media(item, FACEBOOK.hosts)),
    )


def parse_instagram(item: dict) -> Post | None:
    if not item.get("id") and not item.get("shortCode"):
        return None
    known = [("video", item.get("videoUrl"))] + [("image", u) for u in item.get("images") or []]
    if not item.get("videoUrl") and not item.get("images"):
        known.append(("image", item.get("displayUrl")))
    return Post(
        platform="instagram", post_id=str(item.get("id") or item.get("shortCode")), text=item.get("caption") or "",
        url=item.get("url") or f"https://www.instagram.com/p/{item.get('shortCode')}/",
        posted_at=_iso(item.get("timestamp")), reach=_int(item.get("videoViewCount") or item.get("likesCount")),
        media_urls=_merge(known, cdn_media(item, INSTAGRAM.hosts)),
    )


def parse_tiktok(item: dict) -> Post | None:
    if not item.get("id"):
        return None
    meta = item.get("videoMeta") or {}
    known = [("video", u) for u in item.get("mediaUrls") or []] or [("image", meta.get("coverUrl"))]
    return Post(
        platform="tiktok", post_id=str(item["id"]), text=item.get("text") or "", url=item.get("webVideoUrl"),
        posted_at=_iso(item.get("createTimeISO")), reach=_int(item.get("playCount")),
        media_urls=_merge(known, []),  # TikTok CDN links expire fast: only the Actor's own copies are used
    )


def parse_x(item: dict) -> Post | None:
    if not item.get("id"):
        return None
    known = []
    for media in (item.get("extendedEntities") or {}).get("media") or []:
        variants = [v for v in (media.get("video_info") or {}).get("variants") or [] if v.get("content_type") == "video/mp4"]
        if variants:
            known.append(("video", max(variants, key=lambda v: v.get("bitrate") or 0)["url"]))
        else:
            known.append(("image", media.get("media_url_https")))
    return Post(
        platform="x", post_id=str(item["id"]), text=item.get("fullText") or item.get("text") or "",
        url=item.get("url") or item.get("twitterUrl"), posted_at=_iso(item.get("createdAt")),
        reach=_int(item.get("viewCount") or item.get("retweetCount")),
        media_urls=_merge(known, cdn_media(item, X.hosts)),
    )


FACEBOOK = Adapter(
    "facebook", "danek/facebook-search-ppr", "apify/facebook-posts-scraper",
    search_input=lambda q, n, media: {"query": q, "search_type": "posts", "max_posts": n, "recent_posts": True},
    url_input=lambda url, media: {"startUrls": [{"url": url}], "resultsLimit": 1},
    parse=parse_facebook, hosts=("fbcdn.net",), url_hosts=("facebook.com", "fb.com", "fb.watch"),
)
INSTAGRAM = Adapter(
    "instagram", "apify/instagram-scraper", "apify/instagram-scraper",
    search_input=lambda q, n, media: {"search": q.lstrip("#"), "searchType": "hashtag", "searchLimit": 1,
                                      "resultsType": "posts", "resultsLimit": n},
    url_input=lambda url, media: {"directUrls": [url], "resultsType": "posts", "resultsLimit": 1},
    parse=parse_instagram, hosts=("cdninstagram.com", "fbcdn.net"), url_hosts=("instagram.com",),
)
TIKTOK = Adapter(
    "tiktok", "clockworks/tiktok-scraper", "clockworks/tiktok-scraper",
    search_input=lambda q, n, media: {"searchQueries": [q], "resultsPerPage": n, "shouldDownloadVideos": media,
                                      "shouldDownloadCovers": media},
    url_input=lambda url, media: {"postURLs": [url], "shouldDownloadVideos": media, "shouldDownloadCovers": media},
    parse=parse_tiktok, hosts=("api.apify.com", "tiktokcdn.com", "tiktokcdn-us.com", "tiktokcdn-eu.com"),
    url_hosts=("tiktok.com",),
)
X = Adapter(
    "x", "apidojo/tweet-scraper", "apidojo/tweet-scraper",
    search_input=lambda q, n, media: {"searchTerms": [q], "maxItems": n, "sort": "Latest"},
    url_input=lambda url, media: {"startUrls": [url], "maxItems": 1},
    parse=parse_x, hosts=("pbs.twimg.com", "video.twimg.com"), url_hosts=("x.com", "twitter.com"),
)
ADAPTERS = {a.platform: a for a in (FACEBOOK, INSTAGRAM, TIKTOK, X)}


def adapter_for_url(url: str) -> Adapter | None:
    host = (urlsplit(url).hostname or "").lower()
    return next((a for a in ADAPTERS.values() if any(host == h or host.endswith("." + h) for h in a.url_hosts)), None)


# --- Apify --------------------------------------------------------------------------------------------------------

def apify_client():
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise SystemExit("Set APIFY_TOKEN (https://console.apify.com/settings/integrations).")
    from apify_client import ApifyClient

    return ApifyClient(token)


def run_actor(client, actor: str, run_input: dict) -> list[dict]:
    run = client.actor(actor).call(run_input=run_input)
    if run is None or _get(run, "status") != "SUCCEEDED":
        raise RuntimeError(f"Apify Actor {actor} did not succeed: {_get(run, 'status') if run else 'no run'}")
    return dataset_items(client, _get(run, "default_dataset_id", "defaultDatasetId"))


def dataset_items(client, dataset_id: str) -> list[dict]:
    return list(client.dataset(dataset_id).iterate_items())


def collect(adapter: Adapter, client, query: str, max_items: int) -> list[Post]:
    items = run_actor(client, adapter.actor("search"), adapter.search_input(query, max_items, _want_media()))
    return [p for p in map(adapter.parse, items) if p is not None]


def fetch_url(url: str, client=None) -> Post | None:
    """The post behind one URL (for community screening), or None if the platform is not supported or it failed."""
    adapter = adapter_for_url(url)
    if adapter is None:
        return None
    try:
        items = run_actor(client or apify_client(), adapter.actor("url"), adapter.url_input(url, _want_media()))
    except Exception as exc:
        log.warning("could not fetch a %s post: %s", adapter.platform, type(exc).__name__)
        return None
    posts = [p for p in map(adapter.parse, items) if p is not None]
    if posts and not posts[0].url:
        posts[0].url = url
    return posts[0] if posts else None


def _want_media() -> bool:
    from harmwatch.detect import uses_local_judge

    return uses_local_judge()


# --- media --------------------------------------------------------------------------------------------------------

def download_media(url: str, kind: str, folder: Path) -> MediaFile:
    """Download one media file from an allowed CDN host into `folder` (redirects checked hop by hop)."""
    import httpx

    hosts = tuple(h for a in ADAPTERS.values() for h in a.hosts)
    cap = MAX_BYTES[kind]
    target = folder / f"media-{len(list(folder.iterdir()))}"
    with httpx.Client(timeout=httpx.Timeout(10, read=60), follow_redirects=False) as http:
        for _ in range(4):
            if not _host_ok(url, hosts):
                raise ValueError("media host not allowed")
            # Videos saved by the TikTok Actor sit in private Apify storage: the token goes in a header, never the URL.
            headers = {"Authorization": f"Bearer {os.environ['APIFY_TOKEN']}"} \
                if _host_ok(url, ("api.apify.com",)) and os.getenv("APIFY_TOKEN") else {}
            with http.stream("GET", url, headers=headers) as response:
                if response.is_redirect:
                    url = str(response.next_request.url)
                    continue
                response.raise_for_status()
                mime = response.headers.get("content-type", "").split(";")[0].strip().lower()
                if mime not in CONTENT_TYPES or not mime.startswith(kind):
                    raise ValueError(f"unexpected content type {mime!r}")
                size = 0
                path = target.with_suffix(CONTENT_TYPES[mime])
                with path.open("wb") as out:
                    for chunk in response.iter_bytes(256 * 1024):
                        size += len(chunk)
                        if size > cap:
                            raise ValueError("file larger than the size limit")
                        out.write(chunk)
                if size == 0:
                    raise ValueError("empty file")
                return MediaFile(kind=kind, path=path)
    raise ValueError("too many redirects")


# --- command line -------------------------------------------------------------------------------------------------

def main():
    from dotenv import load_dotenv

    from harmwatch import publish

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--query", help="search terms (Instagram: one hashtag)")
    parser.add_argument("--platform", nargs="+", choices=sorted(ADAPTERS), default=sorted(ADAPTERS))
    parser.add_argument("--max-items", type=int, default=20, help="posts per platform (caps the Apify cost)")
    parser.add_argument("--dataset-id", help="read a finished Apify dataset instead of starting a run (one platform)")
    parser.add_argument("--region", help="policy region (default: REGION or global)")
    args = parser.parse_args()
    if not args.dataset_id and not args.query:
        parser.error("--query is required unless --dataset-id is given")
    if args.dataset_id and len(args.platform) != 1:
        parser.error("--dataset-id needs exactly one --platform")

    client = apify_client()
    for name in args.platform:
        adapter = ADAPTERS[name]
        if args.dataset_id:
            posts = [p for p in map(adapter.parse, dataset_items(client, args.dataset_id)) if p is not None]
        else:
            posts = collect(adapter, client, args.query, args.max_items)
        stats = Counter()
        for post in posts:
            result = ingest(post, source=f"apify:{name}", region=args.region)
            stats["new" if result.new else "already seen"] += 1
            stats["copy of known content"] += result.new and result.duplicate
            stats["flagged"] += bool(result.detection and result.detection["route"] in publish.PUBLISH_ROUTES)
        print(f"{name}: {len(posts)} posts, " + ", ".join(f"{k} {v}" for k, v in stats.items()))
    if publish.enabled():
        sent, _ = publish.publish_pending()
        print(f"Sent {sent} sightings to the review queue.")


if __name__ == "__main__":
    main()
