# handlers/audio_handler.py
"""
Audio handling for the Telegram bot.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, MutableMapping, cast

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from .constants import (
    STATE_MODE,
    MODE_TRANSCRIBE,
    MODE_SUMMARIZE,
    MODE_BOTH,
    STATE_PARTS,
    STATE_COLLECTING,
    PARTS_DIR,
    CB_MORE_YES,
    CB_MORE_NO,
)


def _more_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard that asks whether to add another part or start processing."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ Yes, add another", callback_data=CB_MORE_YES),
                InlineKeyboardButton("✅ No, process", callback_data=CB_MORE_NO),
            ]
        ]
    )


def _ext_from_remote_path(remote_path: Optional[str]) -> str:
    """Derive a file extension from Telegram's remote path (fallback .ogg)."""
    if not remote_path:
        return ".ogg"
    ext = Path(remote_path).suffix
    return ext if ext else ".ogg"


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Save incoming voice/audio to PARTS_DIR and ask whether to add more parts.
    This handler does not process; processing is triggered via the merge flow.
    """
    msg = update.effective_message
    if not msg:
        return

    # Detect attachment (voice | audio)
    att = getattr(msg, "voice", None) or getattr(msg, "audio", None)
    if att is None:
        await msg.reply_text("Unsupported message type. Send voice or audio.")
        return

    await msg.chat.send_action(ChatAction.UPLOAD_VOICE)

    tg_file = await att.get_file()
    ext = _ext_from_remote_path(getattr(tg_file, "file_path", None))
    user_id = msg.from_user.id if msg.from_user else 0
    ts = int(msg.date.timestamp())
    filename = f"{user_id}_{ts}{ext}"
    local_path = str(Path(PARTS_DIR) / filename)

    await tg_file.download_to_drive(custom_path=local_path)

    # Pylance-safe: user_data is a mutable mapping in PTB
    ud: MutableMapping[str, Any] = cast(MutableMapping[str, Any], context.user_data)

    parts: List[str] = cast(List[str], ud.setdefault(STATE_PARTS, []))
    parts.append(local_path)

    # Default UI mode if not set (no "BOTH" mode used here)
    if STATE_MODE not in ud:
        ud[STATE_MODE] = MODE_BOTH

    # After each upload, ask whether to add another file
    ud[STATE_COLLECTING] = True

    await msg.reply_text(
        f"Saved part #{len(parts)}.\nAdd another file or start processing?",
        reply_markup=_more_keyboard(),
    )
