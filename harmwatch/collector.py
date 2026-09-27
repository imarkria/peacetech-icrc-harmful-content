"""Collect recent posts from public Telegram channels (text and metadata only).

    python -m harmwatch.collector --limit 200

Needs TELEGRAM_API_ID / TELEGRAM_API_HASH from https://my.telegram.org and
TELEGRAM_CHANNELS (comma-separated usernames). The first run asks for a phone
number and login code in the terminal, then stores a session file in data/.
Media is never downloaded. Posts go through harmwatch.intake (duplicate groups,
judge once per group); flagged ones are sent to the review queue when
SIGNALSAFE_INGEST_TOKEN is set.
"""

import argparse
import asyncio
import os
import re
from collections import Counter

from dotenv import load_dotenv

from harmwatch import db, publish
from harmwatch.intake import Post, ingest

T_ME_POST = re.compile(r"^https?://(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z0-9_]{4,})/(\d+)")


def _client():
    from telethon import TelegramClient

    session = str(db.DB_PATH.parent / "telegram")
    return TelegramClient(session, int(os.environ["TELEGRAM_API_ID"]), os.environ["TELEGRAM_API_HASH"])


def _post(channel: str, msg) -> Post:
    return Post(platform="telegram", post_id=f"{channel}/{msg.id}", text=msg.message or "",
                url=f"https://t.me/{channel}/{msg.id}", posted_at=msg.date.isoformat(), reach=msg.views)


async def collect(limit: int) -> Counter:
    channels = [c.strip().lstrip("@") for c in os.environ["TELEGRAM_CHANNELS"].split(",") if c.strip()]
    stats = Counter()
    async with _client() as client:
        for channel in channels:
            async for msg in client.iter_messages(channel, limit=limit):
                if not msg.message:  # media-only post: skip, we keep text only
                    continue
                result = ingest(_post(channel, msg), source="telegram")
                stats["new" if result.new else "already seen"] += 1
                stats["copy of known content"] += result.new and result.duplicate
            print(f"{channel}: done")
    return stats


def fetch_telegram_post(url: str) -> Post | None:
    """One public channel post by its t.me link (used to screen community reports). None if not configured."""
    match = T_ME_POST.match(url)
    if not match or not os.getenv("TELEGRAM_API_ID"):
        return None
    channel, message_id = match.group(1), int(match.group(2))

    async def fetch():
        async with _client() as client:
            return await client.get_messages(channel, ids=message_id)

    msg = asyncio.run(fetch())
    return _post(channel, msg) if msg and msg.message else None


def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100, help="posts per channel")
    args = parser.parse_args()
    stats = asyncio.run(collect(args.limit))
    print(", ".join(f"{k} {v}" for k, v in stats.items()) or "No posts.")
    if publish.enabled():
        sent, _ = publish.publish_pending()
        print(f"Sent {sent} flagged sightings to the review queue.")


if __name__ == "__main__":
    main()
