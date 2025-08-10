# handlers/summary_handler.py
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, MutableMapping, Optional, cast

from telegram import Update
from telegram.ext import ContextTypes

from .menu_handler import main_menu
from .constants import STATE_MODE, TRANSCRIPTS_DIR
from processors.summary_processor import SummaryProcessor


def _load_latest_transcript_from_disk() -> Optional[str]:
    """Return the newest non-empty .txt content from TRANSCRIPTS_DIR, or None."""
    try:
        d = Path(TRANSCRIPTS_DIR)
        if not d.exists():
            return None
        for p in sorted(d.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                txt = p.read_text(encoding="utf-8-sig").strip()
                if txt:
                    return txt
            except Exception:
                continue
    except Exception:
        pass
    return None


async def trigger_summary_mode(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Enter Summarize mode and summarize immediately if possible (memory → disk)."""
    query = update.callback_query
    if not query:
        return

    # Set mode in user_data
    ud = cast(MutableMapping[str, Any], context.user_data)
    ud[STATE_MODE] = "summarize"

    # Prefer in-memory last transcript; then latest file on disk
    last_text = cast(Optional[str], ud.get("last_transcript_text"))
    if not last_text or not last_text.strip():
        last_text = _load_latest_transcript_from_disk()

    # Use effective chat/message to avoid Optional access warnings
    chat = update.effective_chat
    if last_text and last_text.strip():
        await query.edit_message_text(
            "Summarizing latest transcript…", reply_markup=main_menu()
        )
        sp = SummaryProcessor()
        summary = await asyncio.to_thread(sp.summarize, last_text)
        if chat:
            await context.bot.send_message(
                chat_id=chat.id, text=summary or "Summary failed."
            )
        return

    await query.edit_message_text(
        "Mode set to: Summarize Only.\nSend transcript text or a .txt file to summarize.",
        reply_markup=main_menu(),
    )


async def handle_summary_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle plain text messages while in Summarize mode."""
    ud = cast(MutableMapping[str, Any], context.user_data)
    if ud.get(STATE_MODE) != "summarize":
        return

    msg = update.effective_message
    if not msg:
        return

    text = (msg.text or "").strip()
    if not text:
        return

    # Keep last transcript in memory for one-click summaries
    ud["last_transcript_text"] = text

    sp = SummaryProcessor()
    summary = await asyncio.to_thread(sp.summarize, text)
    await msg.reply_text(summary or "Summary failed.")


async def handle_summary_txt_file(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle uploaded .txt files while in Summarize mode."""
    ud = cast(MutableMapping[str, Any], context.user_data)
    if ud.get(STATE_MODE) != "summarize":
        return

    msg = update.effective_message
    if not msg:
        return

    doc = msg.document
    if not doc:
        return

    out_dir = Path(TRANSCRIPTS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = doc.file_name or "uploaded_transcript.txt"
    out_path = out_dir / filename

    tg_file = await doc.get_file()
    await tg_file.download_to_drive(custom_path=str(out_path))

    text = out_path.read_text(encoding="utf-8-sig").strip()
    if not text:
        await msg.reply_text("Uploaded file is empty.")
        return

    ud["last_transcript_text"] = text

    sp = SummaryProcessor()
    summary = await asyncio.to_thread(sp.summarize, text)
    await msg.reply_text(summary or "Summary failed.")
