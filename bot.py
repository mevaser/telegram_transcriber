# bot.py
import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from handlers.menu_handler import start_command
from handlers.audio_handler import handle_audio
from handlers.callback_handler import callback_router
from handlers import summary_handler


load_dotenv()

# Accept both env var names to avoid confusion across docs
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("transcriber-bot")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.exception("Unhandled error", exc_info=context.error)


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN (or BOT_TOKEN) in .env")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))

    # Audio / voice → transcription flow
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))

    # Inline buttons (menu)
    app.add_handler(CallbackQueryHandler(callback_router))

    # ── Summarize mode inputs ────────────────────────────────────────────────
    # .txt uploads while in Summarize mode
    app.add_handler(
        MessageHandler(
            (
                filters.Document.MimeType("text/plain")
                | filters.Document.FileExtension("txt")
            ),
            summary_handler.handle_summary_txt_file,
        )
    )
    # Plain text while in Summarize mode (non-command)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND, summary_handler.handle_summary_text
        )
    )
    # ─────────────────────────────────────────────────────────────────────────

    app.add_error_handler(on_error)

    logger.info("🚀 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
