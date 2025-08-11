# processors/transcription_processor.py
from __future__ import annotations

import os
import asyncio
import logging
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional

from telegram import Update, InputFile
from telegram.constants import ChatAction

from utils.ivritAI_utils import transcribe_audio, DEVICE
from utils.log_utils import log_transcription, log_artifact
import utils.llm_utils as llm_utils
from handlers.constants import SUMMARIES_DIR  # summaries go here

# Controls whether to attach .txt files back to Telegram (which causes client auto-download)
ATTACH_TXT_FILES = os.getenv("ATTACH_TXT_FILES", "1") == "1"


def _chunk_for_telegram(text: str, limit: int = 3800):
    text = textwrap.dedent(text).strip()
    if len(text) <= limit:
        yield text
        return
    start = 0
    while start < len(text):
        end = min(len(text), start + limit)
        cut = text.rfind("\n", start, end)
        if cut == -1:
            cut = text.rfind(" ", start, end)
        if cut == -1 or cut <= start + 100:
            cut = end
        yield text[start:cut].strip()
        start = cut


class TranscriptionProcessor:
    """
    Orchestrates transcription (and optional summarization).
    Runs the blocking transcribe() in a background thread and
    sends a heartbeat action so the chat shows activity.
    """

    def __init__(self, transcripts_dir: str):
        self.transcripts_dir = Path(transcripts_dir).expanduser().resolve()
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)

    async def _heartbeat(self, update: Update, stop: asyncio.Event) -> None:
        chat = update.effective_chat
        if not chat:
            return
        try:
            while not stop.is_set():
                await chat.send_action(ChatAction.TYPING)
                await asyncio.sleep(4)
        except Exception:
            logging.exception("Heartbeat failed")

    def _stamp(self) -> str:
        # Example: 2025-08-08_18-32-10
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    async def process_file(
        self,
        update: Update,
        file_path: str,
        *,
        mode: str = "transcribe",  # "transcribe" | "summarize" | "transcribe_and_summarize"
        summarizer: Optional[object] = None,  # kept for API compatibility
    ) -> None:
        message = update.effective_message
        if not message:
            return

        uid = update.effective_user.id if update.effective_user else "unknown"
        audio_path = Path(file_path).expanduser().resolve()
        stamp = self._stamp()

        await message.reply_text("⏳ Starting transcription...")

        stop_event = asyncio.Event()
        hb_task = asyncio.create_task(self._heartbeat(update, stop_event))

        # progress callback from the worker thread
        def _progress(i: int, total: int) -> None:
            try:
                asyncio.run_coroutine_threadsafe(
                    message.reply_text(f"📝 Transcribing chunk {i}/{total}…"),
                    asyncio.get_running_loop(),
                )
            except Exception:
                pass

        transcript_text = ""
        transcribe_secs = 0.0
        error_text = ""

        try:
            transcript_text, transcribe_secs = await asyncio.to_thread(
                transcribe_audio, str(audio_path), language="he", progress_cb=_progress
            )
        except Exception as e:
            error_text = str(e)
            logging.exception(f"[{uid}] Transcription failed")
            await message.reply_text(f"❌ Transcription failed: {e}")
        finally:
            stop_event.set()
            try:
                await hb_task
            except Exception:
                pass

        if not transcript_text:
            log_transcription(
                file_path=str(audio_path),
                success=False,
                audio_duration_s=0.0,
                transcribe_time_s=transcribe_secs,
                output_len=0,
                device=DEVICE,
                error=error_text,
            )
            return

        # ----- Save transcript -----
        transcript_name = f"transcribe {stamp}.txt"
        transcript_path = (self.transcripts_dir / transcript_name).resolve()
        transcript_path.write_text(transcript_text, encoding="utf-8")
        log_artifact("Transcript saved", str(transcript_path))

        # 1) Status line (separate message)
        await message.reply_text(f"✅ Transcribed ({transcribe_secs:.1f}s)")

        # 2) Transcript body (unless summarize-only)
        if mode != "summarize":
            await message.reply_text("📝 Transcript:")
            for chunk in _chunk_for_telegram(transcript_text):
                await message.reply_text(chunk)

            # attach the .txt file (optional)
            if ATTACH_TXT_FILES:
                try:
                    with transcript_path.open("rb") as f:
                        await message.reply_document(
                            InputFile(f, filename=transcript_name)
                        )
                except Exception:
                    logging.exception("Failed sending transcript file")

        log_transcription(
            file_path=str(audio_path),
            success=True,
            audio_duration_s=0.0,  # could ffprobe here if needed
            transcribe_time_s=transcribe_secs,
            output_len=len(transcript_text),
            device=DEVICE,
        )

        # ----- Summarize (if requested) -----
        if "summarize" in mode:
            await message.reply_text("🔍 Summarizing…")
            try:
                summary_text = llm_utils.summarize_text(transcript_text)

                # Save summary into SUMMARIES_DIR
                summary_name = f"summarize {stamp}.txt"
                summary_path = (SUMMARIES_DIR / summary_name).resolve()
                summary_path.write_text(summary_text, encoding="utf-8")
                log_artifact("Summary saved", str(summary_path))

                await message.reply_text("📄 Summary:")
                for chunk in _chunk_for_telegram(summary_text):
                    await message.reply_text(chunk)

                if ATTACH_TXT_FILES:
                    try:
                        with summary_path.open("rb") as f:
                            await message.reply_document(
                                InputFile(f, filename=summary_name)
                            )
                    except Exception:
                        logging.exception("Failed sending summary file")

            except Exception as e:
                logging.exception(f"[{uid}] Summarization failed")
                await message.reply_text(f"❌ Summarization failed: {e}")
