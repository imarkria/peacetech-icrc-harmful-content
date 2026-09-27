"""Community Telegram bot: anyone in the local community forwards a suspicious channel post.

    python -m harmwatch.bot

Needs TELEGRAM_BOT_TOKEN (create the bot with @BotFather). This is the broader-community lane: reports are
anonymous (the sender is never stored), rate-limited per sender, judged by the model and grouped with copies of the
same content before they reach reviewers. Trained volunteers report through their account on the web app instead.
Only text and captions are read; photos and videos are ignored on purpose.
"""

import logging
import os
import time
from collections import defaultdict, deque

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from harmwatch import publish
from harmwatch.intake import Post, ingest

WELCOME = (
    "Forward me a post from a public Telegram channel that you think is harmful (threats, mockery or exposure of "
    "survivors of sexual violence, etc.). It is checked, then reviewed by the ICRC. Your name is not kept. "
    "Do not send photos or videos."
)
RATE_LIMIT, RATE_WINDOW = 5, 600  # reports per sender per 10 minutes, in memory only
_recent: dict[int, deque] = defaultdict(deque)


def allowed(sender_id: int) -> bool:
    now, hits = time.monotonic(), _recent[sender_id]
    while hits and now - hits[0] > RATE_WINDOW:
        hits.popleft()
    if len(hits) >= RATE_LIMIT:
        return False
    hits.append(now)
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME)


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.from_user and not allowed(msg.from_user.id):
        await msg.reply_text("Thank you. You have sent many reports in a short time; please try again later.")
        return
    text = msg.text or msg.caption
    origin = msg.forward_origin
    if not text or origin is None or origin.type != "channel" or not origin.chat.username:
        await msg.reply_text("Please forward the post itself from a public channel. "
                             "For other links, use the report form on the website.")
        return

    channel = origin.chat.username
    post = Post(platform="telegram", post_id=f"{channel}/{origin.message_id}", text=text,
                url=f"https://t.me/{channel}/{origin.message_id}", posted_at=origin.date.isoformat())
    result = ingest(post, source="telegram_bot")
    if publish.enabled():
        try:
            publish.publish_pending()
        except Exception:  # the sighting stays unsent; `python -m harmwatch.publish` retries it
            logging.exception("Could not send the report to the review queue")
    await msg.reply_text("Thank you, this post was already reported." if not result.new
                         else "Thank you. The post was received and will be checked.")


def main():
    load_dotenv()
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, report))
    app.run_polling()


if __name__ == "__main__":
    main()
