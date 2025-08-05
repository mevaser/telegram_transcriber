# bot.py

import os
import logging
from dotenv import load_dotenv
from telegram import Update, Message, InputFile
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)
import textwrap
from pathlib import Path

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
        """Enable merge-mode for this user and clear previous buffer."""
        message: Message = update.message  # type: ignore[assignment]
        assert message is not None
        user_data: dict = context.user_data  # type: ignore[union-attr]

        if update.effective_user is None:
            await message.reply_text("❌ Unable to identify user.")
            return

        user_data["merge_mode"] = True
        user_data["parts"] = []
        logging.info(f"[{update.effective_user.id}] Merge mode ON")
        await message.reply_text("🔄 Merge mode ON. Send audio parts, then /end_merge")

    async def end_merge(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Merge all buffered parts and process the combined file."""
        message: Message = update.message  # type: ignore[assignment]
        assert message is not None
        user_data: dict = context.user_data  # type: ignore[union-attr]

        parts: list[str] = user_data.pop("parts", [])
        user_data["merge_mode"] = False  # 🔑 turn it off

        if not parts:
            await message.reply_text("❌ No buffered parts to merge.")
            return

        if update.effective_user is None:
            await message.reply_text("❌ Unable to identify user.")
            return

        uid = update.effective_user.id
        merged_path = os.path.join(DOWNLOAD_DIR, f"{uid}_merged.mp3")
        logging.info(f"[{uid}] Merging {len(parts)} parts → {merged_path}")

        try:
            merge_audio_files(parts, merged_path)
            await message.reply_text(f"✅ Merged {len(parts)} parts.")
            await self._process_file(update, merged_path)
        except Exception as exc:
            logging.exception(f"[{uid}] Merge failed")
            await message.reply_text(f"❌ Merge failed: {exc}")

    async def handle_audio(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Receive a voice/audio message, buffer or transcribe immediately."""
        message: Message = update.message  # type: ignore[assignment]
        assert message is not None
        user_data: dict = context.user_data  # type: ignore[union-attr]

        file_id = (
            message.voice.file_id
            if message.voice
            else message.audio.file_id if message.audio else None
        )
        if file_id is None:
            await message.reply_text("❌ Unsupported audio type.")
            return

        file_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp3")
        await (await context.bot.get_file(file_id)).download_to_drive(file_path)
        await message.reply_text("📥 Received audio part.")

        if user_data.get("merge_mode", False):
            # buffer for later merging
            user_data["parts"].append(file_path)
            await message.reply_text(f"🧩 Buffered {len(user_data['parts'])} part(s).")
        else:
            # transcribe immediately
            await self._process_file(update, file_path)

    async def _process_file(self, update: Update, file_path: str) -> None:
        """Transcribe `file_path`, send transcript (file or chunks) and summary."""
        # ── sanity checks ────────────────────────────────────────────────────
        message: Message = update.message  # type: ignore
        assert message is not None, "update.message is unexpectedly None"
        if update.effective_user is None:
            await message.reply_text("❌ Unable to identify user.")
            return
        uid = update.effective_user.id

        # ── transcription ───────────────────────────────────────────────────
        logging.info(f"[{uid}] ⏳ Transcribing {file_path}")
        await self.app.bot.send_chat_action(
            chat_id=message.chat.id, action=ChatAction.TYPING
        )

        transcript, elapsed = transcribe_audio(file_path)
        logging.info(f"[{uid}] ✅ Transcribed in {elapsed:.1f}s")

        # save transcript to disk
        txt_path = Path(file_path).with_suffix(".txt")
        txt_path.write_text(transcript, encoding="utf-8")
        logging.info(f"[{uid}] Transcript saved → {txt_path}")

        # log for stats
        log_transcription(
            file_path=file_path,
            success=bool(transcript),
            audio_duration_s=0,  # TODO: pass real duration if desired
            transcribe_time_s=elapsed,
            output_len=len(transcript),
            device=DEVICE,
        )

        # ── send transcript back ────────────────────────────────────────────
        if not transcript:
            await message.reply_text("📝 Transcript is empty.")
        elif len(transcript) > 4000:
            # Too long for a single Telegram message → send as a document
            await message.reply_document(
                document=InputFile(str(txt_path)),
                caption="📝 Full transcript (attached file)",
            )
        else:
            # Short enough → send as one or more text messages (chunk at 4000)
            await message.reply_text("📝 Full transcript:")
            for chunk in textwrap.wrap(transcript, 4000):
                await message.reply_text(chunk)

        # ── summarisation ───────────────────────────────────────────────────
        logging.info(f"[{uid}] ⚙️ Summarising transcript")
        await message.reply_text("🔍 Summarising…")
        try:
            summary = llm_utils.summarize_text(transcript)
            logging.info(f"[{uid}] Summary: {summary}")
            await message.reply_text("📄 Summary:")
            await message.reply_text(summary)
            logging.info(f"[{uid}] ✅ Summary sent")
        except Exception as e:
            logging.exception(f"[{uid}] Summarisation failed")
            await message.reply_text(f"❌ Summarisation failed: {e}")

    def run(self) -> None:
        logging.info("🚀 Bot polling for messages…")
        self.app.run_polling()


if __name__ == "__main__":
    TranscriberBot().run()
