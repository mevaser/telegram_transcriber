# bot.py

import os
import logging
from dotenv import load_dotenv
from telegram import Update, Message
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

from log_utils import log_transcription
from whisper_utils import transcribe_audio, DEVICE
from merge_utils import merge_audio_files
import llm_utils

# ─── configure logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s", level=logging.INFO
)
logging.getLogger("telegram").setLevel(logging.DEBUG)

# ─── configuration ─────────────────────────────────────────────────────────────
load_dotenv()
# Guarantee BOT_TOKEN is always a str (KeyError if missing)
BOT_TOKEN: str = os.environ["BOT_TOKEN"]

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


class TranscriberBot:
    def __init__(self) -> None:
        logging.info("🔧 Initializing bot…")
        self.app = ApplicationBuilder().token(BOT_TOKEN).build()
        self._register_handlers()
        self.app.add_error_handler(self._on_error)

    def _register_handlers(self) -> None:
        self.app.add_handler(CommandHandler("start_merge", self.start_merge))
        self.app.add_handler(CommandHandler("end_merge", self.end_merge))
        self.app.add_handler(
            MessageHandler(filters.AUDIO | filters.VOICE, self.handle_audio)
        )

    async def _on_error(
        self, update: object, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        logging.exception("Unhandled exception in update:")
        if isinstance(update, Update) and update.message:
            await update.message.reply_text("❌ An unexpected error occurred.")

    async def start_merge(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        # Narrow update.message
        message: Message = update.message  # type: ignore[assignment]
        assert message is not None

        # Narrow user_data
        user_data: dict = context.user_data  # type: ignore[union-attr]
        assert isinstance(user_data, dict)

        if not update.effective_user:
            await message.reply_text("❌ Unable to identify user.")
            return
        uid = update.effective_user.id
        user_data["parts"] = []
        logging.info(f"[{uid}] Merge mode ON")
        await message.reply_text("🔄 Merge mode ON. Send audio parts, then /end_merge")

    async def end_merge(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        # Narrow update.message
        message: Message = update.message  # type: ignore[assignment]
        assert message is not None

        # Narrow user_data
        user_data: dict = context.user_data  # type: ignore[union-attr]
        assert isinstance(user_data, dict)

        if not update.effective_user:
            await message.reply_text("❌ Unable to identify user.")
            return
        uid = update.effective_user.id
        parts = user_data.pop("parts", [])
        if not parts:
            await message.reply_text("❌ No buffered parts to merge.")
            return

        merged_path = os.path.join(DOWNLOAD_DIR, f"{uid}_merged.mp3")
        logging.info(f"[{uid}] Merging {len(parts)} parts → {merged_path}")
        try:
            merge_audio_files(parts, merged_path)
        except Exception as e:
            logging.exception(f"[{uid}] Merge failed")
            await message.reply_text(f"❌ Merge failed: {e}")
            return

        await message.reply_text(f"✅ Merged {len(parts)} parts.")
        await self._process_file(update, merged_path)

    async def handle_audio(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        # Narrow update.message
        message: Message = update.message  # type: ignore[assignment]
        assert message is not None

        # Narrow user_data
        user_data: dict = context.user_data  # type: ignore[union-attr]
        assert isinstance(user_data, dict)

        if not update.effective_user:
            await message.reply_text("❌ Unable to identify user.")
            return
        uid = update.effective_user.id
        file_id = (
            message.voice.file_id
            if message.voice
            else message.audio.file_id if message.audio else None
        )
        if not file_id:
            await message.reply_text("❌ Unsupported audio type.")
            return

        file_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp3")
        logging.info(f"[{uid}] Downloading {file_id} → {file_path}")
        tg_file = await context.bot.get_file(file_id)
        await tg_file.download_to_drive(file_path)
        await message.reply_text("📥 Received audio part.")

        if "parts" in user_data:
            user_data["parts"].append(file_path)
            count = len(user_data["parts"])
            logging.info(f"[{uid}] Buffered part #{count}")
            await message.reply_text(f"🧩 Buffered {count} part(s).")

    async def _process_file(self, update: Update, file_path: str) -> None:
        # Narrow update.message
        message: Message = update.message  # type: ignore[assignment]
        assert message is not None

        if not update.effective_user:
            await message.reply_text("❌ Unable to identify user.")
            return
        uid = update.effective_user.id
        assert message is not None

        uid = update.effective_user.id
        logging.info(f"[{uid}] ⏳ Transcribing {file_path}")

        # show “typing…” indicator
        await self.app.bot.send_chat_action(
            chat_id=message.chat.id, action=ChatAction.TYPING
        )

        # 1) transcription
        transcript, elapsed = transcribe_audio(file_path)
        logging.info(f"[{uid}] ✅ Transcribed in {elapsed:.1f}s")

        # save raw transcript
        txt_path = file_path.replace(".mp3", ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(transcript)
        logging.info(f"[{uid}] Transcript saved to {txt_path}")

        # log to file
        log_transcription(
            file_path=file_path,
            success=bool(transcript),
            audio_duration_s=0,
            transcribe_time_s=elapsed,
            output_len=len(transcript),
            device=DEVICE,
        )

        # 2) send raw transcript
        await message.reply_text("📝 Full transcript:")
        await message.reply_text(transcript or "(empty)")

        # 3) summarization
        logging.info(f"[{uid}] ⚙️ Summarizing transcript")
        await message.reply_text("🔍 Summarizing…")
        try:
            summary = llm_utils.summarize_text(transcript)
            logging.info(f"[{uid}] ✅ Summary ready")
            await message.reply_text("📄 Summary:")
            await message.reply_text(summary)
        except Exception as e:
            logging.exception(f"[{uid}] Summarization failed")
            await message.reply_text(f"❌ Summarization failed: {e}")

    def run(self) -> None:
        logging.info("🚀 Bot polling for messages…")
        self.app.run_polling()


if __name__ == "__main__":
    TranscriberBot().run()
