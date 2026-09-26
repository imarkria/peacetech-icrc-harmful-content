"""Collect recent posts from public Telegram channels (text and metadata only).

    python -m harmwatch.collector --limit 200

Needs TELEGRAM_API_ID / TELEGRAM_API_HASH from https://my.telegram.org and
TELEGRAM_CHANNELS (comma-separated usernames). The first run asks for a phone
number and login code in the terminal, then stores a session file in data/.
Media is never downloaded.
"""

import argparse
import asyncio
import os

from dotenv import load_dotenv

from harmwatch import db
from harmwatch.pipeline import classify_pending


async def collect(limit: int) -> int:
    from telethon import TelegramClient

    channels = [c.strip().lstrip("@") for c in os.environ["TELEGRAM_CHANNELS"].split(",") if c.strip()]
    session = str(db.DB_PATH.parent / "telegram")
    added = 0
    async with TelegramClient(session, int(os.environ["TELEGRAM_API_ID"]), os.environ["TELEGRAM_API_HASH"]) as client:
        with db.connect() as conn:
            for channel in channels:
                async for msg in client.iter_messages(channel, limit=limit):
                    if not msg.message:  # media-only post: skip, we keep text only
                        continue
                    post_id = db.add_post(
                        conn, source="telegram", text=msg.message, channel=channel,
                        url=f"https://t.me/{channel}/{msg.id}", posted_at=msg.date.isoformat(),
                        views=msg.views, forwards=msg.forwards,
                    )
                    added += post_id is not None
                print(f"{channel}: done")
    return added


def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100, help="posts per channel")
    args = parser.parse_args()
    print(f"Added {asyncio.run(collect(args.limit))} new posts.")
    with db.connect() as conn:
        print(f"Classified {classify_pending(conn)} posts.")


if __name__ == "__main__":
    main()
