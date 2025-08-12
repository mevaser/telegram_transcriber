# handlers/callback_handler.py
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Any, List, Optional, MutableMapping, cast, Any as _Any

from telegram import Update, Message
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from .menu_handler import main_menu
from .constants import (
    STATE_MODE,
    MODE_TRANSCRIBE,
    MODE_SUMMARIZE,
    MODE_BOTH,
    STATE_PARTS,
    STATE_COLLECTING,
    PARTS_DIR,
    MERGED_DIR,
    TRANSCRIPTS_DIR,
    CB_SET_MODE_TRANSCRIBE,
    CB_SET_MODE_SUMMARIZE,
    CB_SET_MODE_BOTH,
    CB_MORE_YES,
    CB_MORE_NO,
    # ensure summaries dir exists as well
    SUMMARIES_DIR,
)

from processors.merge_processor import MergeProcessor
from processors.transcription_processor import TranscriptionProcessor
from processors.summary_processor import SummaryProcessor

# Import the summarize flow (memory → disk → ask user)
from handlers import summary_handler

# Ensure expected directories exist (they are Path objects already)
for d in (PARTS_DIR, MERGED_DIR, TRANSCRIPTS_DIR, SUMMARIES_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Singletons (pass str to satisfy type checkers)
merger = MergeProcessor(merged_dir=str(MERGED_DIR))
transcriber = TranscriptionProcessor(transcripts_dir=str(TRANSCRIPTS_DIR))
summarizer = SummaryProcessor()


# --- Safe edit helper to avoid "Message is not modified" exceptions ---
def _markup_equal(a: _Any, b: _Any) -> bool:
    if a is b:
        return True
    if (a is None) != (b is None):
        return False
    try:
        return a.to_dict() == b.to_dict()
    except Exception:
        return str(a) == str(b)


async def safe_edit(query, text: str, reply_markup=None, parse_mode=None):
    msg = query.message
    try:
        if msg is None:
            await query.answer()
            return
        current_text = msg.text or msg.caption or ""
        if current_text != text or not _markup_equal(msg.reply_markup, reply_markup):
            await query.edit_message_text(
                text=text, reply_markup=reply_markup, parse_mode=parse_mode
            )
        else:
            await query.answer()
    except BadRequest as e:
        if "Message is not modified" in str(e):
            return
        raise


def _mode_label(mode: str) -> str:
    if mode == MODE_BOTH:
        return "Transcribe + Summarize"
    if mode == MODE_SUMMARIZE:
        return "Summarize Only"
    return "Transcribe Only"


def _user_data(context: ContextTypes.DEFAULT_TYPE) -> MutableMapping[str, Any]:
    """Return user_data as a mutable mapping (PTB provides a dict here)."""
    return cast(MutableMapping[str, Any], context.user_data)


async def _process_current_mode(
    update: Update, context: ContextTypes.DEFAULT_TYPE, audio_path: str
) -> None:
    ud = _user_data(context)
    mode = cast(str, ud.get(STATE_MODE, MODE_BOTH))

    # Make Pylance happy: annotate as Optional[Message]
    msg: Optional[Message] = update.effective_message or (
        update.callback_query.message if update.callback_query else None  # type: ignore[attr-defined]
    )
    if msg is not None:
        await msg.reply_text(f"🚀 Processing: {_mode_label(mode)} ...")

    processor_mode = {
        MODE_BOTH: "both",
        MODE_TRANSCRIBE: "transcribe",
        MODE_SUMMARIZE: "summarize",
    }[mode]

    await transcriber.process_file(
        update, audio_path, mode=processor_mode, summarizer=summarizer
    )


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    await query.answer()

    ud = _user_data(context)
    ud.setdefault(STATE_PARTS, [])
    ud.setdefault(STATE_MODE, MODE_BOTH)

    # --- Mode switching ---
    if data == CB_SET_MODE_TRANSCRIBE:
        ud[STATE_MODE] = MODE_TRANSCRIBE
        ud[STATE_COLLECTING] = False
        ud[STATE_PARTS] = []
        await safe_edit(
            query,
            "Mode set to: Transcribe Only.\nSend audio to transcribe.",
            reply_markup=main_menu(),
        )
        return

    if data == CB_SET_MODE_SUMMARIZE:
        # Enter Summarize mode and trigger the summarize flow immediately:
        # 1) in-memory last transcript → 2) latest .txt on disk → 3) ask for input.
        ud[STATE_MODE] = MODE_SUMMARIZE
        ud[STATE_COLLECTING] = False
        ud[STATE_PARTS] = []
        await summary_handler.trigger_summary_mode(update, context)
        return

    if data == CB_SET_MODE_BOTH:
        ud[STATE_MODE] = MODE_BOTH
        ud[STATE_COLLECTING] = False
        ud[STATE_PARTS] = []
        await safe_edit(
            query,
            "Mode set to: Transcribe + Summarize.\nSend audio to process.",
            reply_markup=main_menu(),
        )
        return

    # --- Add-more flow (merge multiple audio parts) ---
    if data == CB_MORE_YES:
        ud[STATE_COLLECTING] = True
        await safe_edit(
            query, "OK. Send the next audio file…", reply_markup=main_menu()
        )
        return

    if data == CB_MORE_NO:
        parts: List[str] = cast(List[str], ud.get(STATE_PARTS, []))
        ud[STATE_COLLECTING] = False

        if not parts:
            await safe_edit(query, "No files to process.", reply_markup=main_menu())
            return

        if len(parts) == 1:
            final_path = parts[0]
        else:
            user = update.effective_user
            uid = user.id if user else int(time.time())
            # use .opus to match MergeProcessor enforced extension
            out_name = f"{uid}_{int(time.time())}_merged.opus"
            final_path = merger.merge(parts, out_name)

        ud[STATE_PARTS] = []

        await safe_edit(query, "Starting processing…", reply_markup=None)
        await _process_current_mode(update, context, final_path)
        return

    # Default fallback
    await safe_edit(query, "Unsupported action.", reply_markup=main_menu())
