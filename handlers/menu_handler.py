# handlers/menu_handler.py
from typing import Optional, Dict, Any, cast

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Message
from telegram.ext import ContextTypes

from .constants import (
    STATE_MODE,
    MODE_TRANSCRIBE,
    MODE_SUMMARIZE,
    MODE_BOTH,
    CB_SET_MODE_TRANSCRIBE,
    CB_SET_MODE_SUMMARIZE,
    CB_SET_MODE_BOTH,
)


def _mode_label(mode: str) -> str:
    if mode == MODE_BOTH:
        return "Transcribe + Summarize"
    if mode == MODE_SUMMARIZE:
        return "Summarize Only"
    return "Transcribe Only"


def main_menu(current_mode: Optional[str] = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📝 Transcribe + Summarize", callback_data=CB_SET_MODE_BOTH
                )
            ],
            [
                InlineKeyboardButton(
                    "🗣️ Transcribe", callback_data=CB_SET_MODE_TRANSCRIBE
                )
            ],
            [InlineKeyboardButton("📄 Summarize", callback_data=CB_SET_MODE_SUMMARIZE)],
        ]
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Cast silences Pylance's optional access warning
    ud = cast(Dict[str, Any], context.user_data)
    mode = cast(str, ud.get(STATE_MODE, MODE_TRANSCRIBE))

    text = (
        "Welcome 👋\n\n"
        "Choose a mode below, then send a voice note or audio file.\n"
        "After each upload I’ll ask if you want to add another file."
        f"\n\nCurrent mode: {_mode_label(mode)}"
    )

    # Guard access to message to keep the type checker happy
    raw_msg = update.effective_message or (
        update.callback_query.message if update.callback_query else None
    )

    if isinstance(raw_msg, Message):
        await raw_msg.reply_text(text, reply_markup=main_menu(mode))
    # else: nothing to do (no accessible message in this update type)
