# processors/transcription_processor.py
import asyncio
import logging
import textwrap
from pathlib import Path
from typing import Optional

from telegram import Update, InputFile
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from utils.ivritAI_utils import transcribe_audio, DEVICE
from utils.log_utils import log_transcription
import utils.llm_utils as llm_utils


class TranscriptionProcessor:
    """
    Orchestrates transcription (and optional summarization).
    Runs the blocking IvritAI transcribe() in a background thread and
    sends a heartbeat action so the chat shows activity.
    """

    def __init__(self, transcripts_dir: str):
        self.transcripts_dir = Path(transcripts_dir)
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)

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
            # Don't let heartbeat exceptions kill the flow
            logging.exception("Heartbeat failed")

    async def process_file(
        self,
        update: Update,
        file_path: str,
        *,
        mode: str = "transcribe_and_summarize",  # "transcribe" | "summarize" | "transcribe_and_summarize"
        summarizer: Optional[object] = None,  # kept for API compatibility
    ) -> None:
        """
        - Transcribes audio with IvritAI (Runpod).
        - If mode contains 'summarize', generates a Hebrew summary.
        - Sends transcript as text + file (except in summarize-only).
        """
        message = update.effective_message
        if not message:
            return

        uid = update.effective_user.id if update.effective_user else "unknown"
        audio_path = Path(file_path).resolve()

        # Status line to user
        await message.reply_text("⏳ Starting transcription...")

        # Heartbeat on while transcribing
        stop_event = asyncio.Event()
        hb_task = asyncio.create_task(self._heartbeat(update, stop_event))

        transcript_text = ""
        transcribe_secs = 0.0
        error_text = ""

        try:
            # IMPORTANT: transcribe_audio() is blocking -> run in a thread
            transcript_text, transcribe_secs = await asyncio.to_thread(
                transcribe_audio, str(audio_path)
            )
        except Exception as e:
            error_text = str(e)
            logging.exception(f"[{uid}] Transcription failed")
            await message.reply_text(f"❌ Transcription failed: {e}")
        finally:
            # stop the heartbeat regardless of outcome
            stop_event.set()
            try:
                await hb_task
            except Exception:
                pass

        if not transcript_text:
            # Log failure (duration unknown -> 0)
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

        # Save transcript to file
        out_name = audio_path.with_suffix(".txt").name
        out_path = self.transcripts_dir / out_name
        out_path.write_text(transcript_text, encoding="utf-8")

        # Send transcript (in summarize-only we skip sending the transcript file)
        if mode != "summarize":
            # Chunk long text into Telegram-friendly pieces
            await message.reply_text("📝 Transcript:")
            for chunk in _chunk_for_telegram(transcript_text):
                await message.reply_text(chunk)

            # Also attach the .txt file
            try:
                with out_path.open("rb") as f:
                    await message.reply_document(InputFile(f, filename=out_name))
            except Exception:
                logging.exception("Failed sending transcript file")

        # Log success
        log_transcription(
            file_path=str(audio_path),
            success=True,
            audio_duration_s=0.0,  # if you want real duration, we can add ffprobe later
            transcribe_time_s=transcribe_secs,
            output_len=len(transcript_text),
            device=DEVICE,
        )

        # Summarize if requested
        if "summarize" in mode:
            await message.reply_text("🔍 Summarising…")
            try:
                summary = llm_utils.summarize_text(transcript_text)
                await message.reply_text("📄 Summary:")
                for chunk in _chunk_for_telegram(summary):
                    await message.reply_text(chunk)
            except Exception as e:
                logging.exception(f"[{uid}] Summarisation failed")
                await message.reply_text(f"❌ Summarisation failed: {e}")


def _chunk_for_telegram(text: str, limit: int = 3800):
    """Yield text chunks under Telegram message limit with clean breaks."""
    text = textwrap.dedent(text).strip()
    if len(text) <= limit:
        yield text
        return
    start = 0
    while start < len(text):
        end = min(len(text), start + limit)
        # try to break on a whitespace
        cut = text.rfind("\n", start, end)
        if cut == -1:
            cut = text.rfind(" ", start, end)
        if cut == -1 or cut <= start + 100:
            cut = end
        yield text[start:cut].strip()
        start = cut
