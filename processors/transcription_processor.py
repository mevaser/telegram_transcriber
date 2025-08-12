# processors/transcription_processor.py
from __future__ import annotations

import os
import asyncio
import logging
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from telegram import Update, InputFile
from telegram.constants import ChatAction

from utils.ivritAI_utils import transcribe_audio, DEVICE
from utils.log_utils import log_transcription, log_artifact
from handlers.constants import SUMMARIES_DIR  # where summaries are saved

# Controls whether to attach .txt files back to Telegram (client will auto-download)
ATTACH_TXT_FILES = os.getenv("ATTACH_TXT_FILES", "1") == "1"


@runtime_checkable
class Summarizer(Protocol):
    """Protocol for summary providers."""

    def summarize(self, text: str) -> str: ...


def _chunk_for_telegram(text: str, limit: int = 3800):
    """Yield text chunks under Telegram message limit with clean breaks."""
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
    Runs the blocking IvritAI transcribe() in a background thread and
    keeps a 'typing' heartbeat so the user sees activity.
    """

    def __init__(self, transcripts_dir: str | Path):
        self.transcripts_dir = Path(transcripts_dir).expanduser().resolve()
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)

    def _stamp(self) -> str:
        """Return a filesystem-safe timestamp, e.g. 2025-08-12_11-05-30."""
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    async def _heartbeat(self, update: Update, stop: asyncio.Event) -> None:
        """Send TYPING action every few seconds until 'stop' is set."""
        chat = update.effective_chat
        if not chat:
            return
        try:
            while not stop.is_set():
                await chat.send_action(ChatAction.TYPING)
                await asyncio.sleep(4)
        except Exception:
            logging.exception("Heartbeat failed")

    async def process_file(
        self,
        update: Update,
        file_path: str | Path,
        *,
        mode: str = "both",  # accepts: "transcribe" | "summarize" | "both"
        summarizer: Optional[Summarizer] = None,  # type-safe protocol
    ) -> None:
        """Transcribe audio; optionally summarize; send results + save artifacts."""
        message = update.effective_message
        if not message:
            return

        uid = update.effective_user.id if update.effective_user else "unknown"
        audio_path = Path(file_path).expanduser().resolve()
        stamp = self._stamp()

        await message.reply_text("⏳ Starting transcription...")

        # Heartbeat while transcribing
        stop_event = asyncio.Event()
        hb_task = asyncio.create_task(self._heartbeat(update, stop_event))

        # Capture the main loop for thread-safe UI updates from worker thread
        loop = asyncio.get_running_loop()

        def _progress(i: int, total: int) -> None:
            """Called from worker thread; schedule UI update on main loop."""
            try:
                asyncio.run_coroutine_threadsafe(
                    message.reply_text(f"📝 Transcribing chunk {i}/{total}…"),
                    loop,
                )
            except Exception:
                pass  # never break pipeline on progress errors

        transcript_text = ""
        transcribe_secs = 0.0
        error_text = ""

        try:
            # Run blocking ASR in a worker thread
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

        # Save transcript with timestamped name
        transcript_name = f"transcribe {stamp}.txt"
        transcript_path = (self.transcripts_dir / transcript_name).resolve()
        transcript_path.write_text(transcript_text, encoding="utf-8")
        log_artifact("Transcript saved", str(transcript_path))

        await message.reply_text(f"✅ Transcribed ({transcribe_secs:.1f}s)")

        # Send transcript (skip if summarize-only)
        if mode != "summarize":
            await message.reply_text("📝 Transcript:")
            for chunk in _chunk_for_telegram(transcript_text):
                await message.reply_text(chunk)

            if ATTACH_TXT_FILES:
                try:
                    with transcript_path.open("rb") as f:
                        await message.reply_document(
                            InputFile(f, filename=transcript_name)
                        )
                except Exception:
                    logging.exception("Failed sending transcript file")

        # Log success
        log_transcription(
            file_path=str(audio_path),
            success=True,
            audio_duration_s=0.0,  # could add ffprobe duration later
            transcribe_time_s=transcribe_secs,
            output_len=len(transcript_text),
            device=DEVICE,
        )

        # Summarize if requested ("both" or "summarize")
        if mode in ("summarize", "both"):
            await message.reply_text("🔍 Summarizing…")
            try:
                if summarizer is not None:
                    # Pylance-safe: summarizer follows the Summarizer Protocol
                    summary_text = summarizer.summarize(transcript_text)
                else:
                    # Backward-compatible fallback
                    import utils.llm_utils as llm_utils

                    summary_text = llm_utils.summarize_text(transcript_text)

                summary_name = f"summarize {stamp}.txt"
                summary_path = (Path(SUMMARIES_DIR) / summary_name).resolve()
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
