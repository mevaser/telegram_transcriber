# handlers/summary_handler.py
from typing import cast, Any, MutableMapping
from telegram import Update
from telegram.ext import ContextTypes
from .menu_handler import main_menu
from .constants import STATE_MODE


async def trigger_summary_mode(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query:
        return

    # Pylance-safe user_data access
    ud = cast(MutableMapping[str, Any], context.user_data)
    ud[STATE_MODE] = "summarize"

    await query.edit_message_text(
        "Mode set to: Summarize Only.\nSend text to summarize.",
        reply_markup=main_menu(),
    )
