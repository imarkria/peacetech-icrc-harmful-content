"""Telegram bot: volunteers forward a suspicious post, it enters the review queue.

    python -m harmwatch.bot

Needs TELEGRAM_BOT_TOKEN (create the bot with @BotFather). Only text and captions
are stored; photos and videos are ignored on purpose.
"""

import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from harmwatch import db, publish
from harmwatch.pipeline import classify_post

WELCOME = (
    "Forward me a Telegram post you think is harmful (threats, mockery or exposure of survivors "
    "of sexual violence, etc.). An ICRC analyst will review it. Do not send photos or videos."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME)


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = msg.text or msg.caption
    if not text:
        await msg.reply_text("I can only take text. Please forward a post with text, or paste it.")
        return

    channel, url = None, None
    origin = msg.forward_origin
    if origin is not None and origin.type == "channel":
        channel = origin.chat.username or origin.chat.title
        if origin.chat.username:
            url = f"https://t.me/{origin.chat.username}/{origin.message_id}"

    with db.connect() as conn:
        post_id = db.add_post(
            conn, source="volunteer", text=text, channel=channel, url=url,
            posted_at=origin.date.isoformat() if origin else None,
            reporter=f"tg:{msg.from_user.id}" if msg.from_user else None,
        )
        if post_id is None:
            await msg.reply_text("Thanks, this post was already reported.")
            return
        post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        classify_post(conn, post)
        if publish.enabled():
            try:
                publish.publish_pending(conn)
            except Exception:  # the post stays unpublished; `python -m harmwatch.publish` retries it
                logging.exception("Could not send the post to the review queue")
    await msg.reply_text("Thank you. The post was added to the review queue.")


def main():
    load_dotenv()
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, report))
    app.run_polling()


if __name__ == "__main__":
    main()
