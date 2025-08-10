# handlers/audio_handler.py
"""
Audio handling for the Telegram bot.
"""
import os
from pathlib import Path
from typing import Dict, Any, List, cast, Optional

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
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ Yes, add another", callback_data=CB_MORE_YES),
                InlineKeyboardButton("✅ No, process", callback_data=CB_MORE_NO),
            ]
        ]
    )


def _ext_from_remote_path(remote_path: Optional[str]) -> str:
    if not remote_path:
        return ".ogg"
    ext = Path(remote_path).suffix
    return ext if ext else ".ogg"


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg:
        return

    # detect attachment (voice|audio)
    att = None
    if msg.voice:
        att = msg.voice
    elif msg.audio:
        att = msg.audio
    else:
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

    ud = cast(Dict[str, Any], context.user_data)
    parts: List[str] = cast(List[str], ud.setdefault(STATE_PARTS, []))
    parts.append(local_path)
    ud.setdefault(STATE_MODE, MODE_TRANSCRIBE)
    ud[STATE_COLLECTING] = True  # after each upload, ask "add another?"

    await msg.reply_text(
        f"Saved part #{len(parts)}.\nAdd another file or start processing?",
        reply_markup=_more_keyboard(),
    )
