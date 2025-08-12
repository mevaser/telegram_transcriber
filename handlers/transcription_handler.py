# handlers/transcription_handler.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, MutableMapping, cast
from telegram import Update
from telegram.ext import ContextTypes

from handlers.constants import (
    STATE_MODE,
    MODE_TRANSCRIBE,
    MODE_SUMMARIZE,
    MODE_BOTH,
    TRANSCRIPTS_DIR,
)
from processors.transcription_processor import TranscriptionProcessor
from processors.summary_processor import SummaryProcessor

# Reusable singletons (can also be created on app startup and stored in bot_data)
TP = TranscriptionProcessor(TRANSCRIPTS_DIR)
SP = SummaryProcessor()


def _normalize_mode(mode: str | None) -> str:
    """
    Map UI mode (as stored in user_data) to the processor mode.
    Processor accepts: "transcribe", "summarize", "both".
    """
    if mode == MODE_TRANSCRIBE:
        return "transcribe"
    if mode == MODE_SUMMARIZE:
        return "summarize"
    return "both"  # default and MODE_BOTH


async def handle_audio_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    file_path: str | Path,
) -> None:
    """
    Thin handler:
    - Read the current user mode from context.user_data (with safe fallback)
    - Delegate heavy lifting to TranscriptionProcessor
    - Always pass SummaryProcessor so the summary path is consistent
    """
    try:
        # Pylance-safe: user_data may be None per typing; coerce to a dict
        ud: MutableMapping[str, Any] = cast(
            MutableMapping[str, Any], getattr(context, "user_data", {}) or {}
        )
        mode_ui = ud.get(STATE_MODE, MODE_BOTH)
        processor_mode = _normalize_mode(mode_ui)

        await TP.process_file(
            update=update,
            file_path=str(file_path),
            mode=processor_mode,
            summarizer=SP,
        )
    except Exception:
        logging.exception("Audio handling failed")
        msg = update.effective_message
        if msg:
            await msg.reply_text("❌ Failed to process audio.")
