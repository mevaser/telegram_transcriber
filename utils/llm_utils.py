# utils/llm_utils.py
from __future__ import annotations

import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Optional, cast

from openai import OpenAI
from openai import APIConnectionError, RateLimitError, BadRequestError


# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
OPENAI_MODEL: str = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4.1-mini")

# Your exact Hebrew financial summarization prompt (system instructions).
OPENAI_SYSTEM_PROMPT: str = os.getenv(
    "OPENAI_SYSTEM_PROMPT",
    (
        "You summarize Hebrew financial transcripts into 6–10 sections.\n\n"
        "Rules:\n"
        "• Title: סיכום הקלטה (DD.MM.YY) (use date in transcript, else today).\n"
        "• Maintain original topic order. No speaker mentions.\n"
        "• Detect ALL distinct topics AND every company/asset/ticker mentioned.\n"
        "• Sectioning:\n"
        '  – Macro topics (e.g., ריבית/אג"ח, שוק/קריפטו) get their own sections.\n'
        "  – Each stock/crypto ticker gets its own section. Do NOT put two unrelated tickers in one section.\n"
        "  – Exception: if two tickers are directly compared (e.g., LLY vs NVO), a joint section is OK.\n"
        "  – 4–6 factual sentences per section (figures, reasoning, outcomes). No filler/advice.\n"
        "• If more than 10 items:\n"
        "  – Keep the most central 6–9 sections (macro + key movers),\n"
        "  – Add a final section “מניות נוספות” with 1–2 sentences per leftover ticker (still separate bullets inside).\n"
        "• Tickers:\n"
        "  – In headings include the ticker in parentheses when known.\n"
        "  – Convert Hebrew/full company names to their official English tickers when certain.\n"
        "  – Do NOT guess; if uncertain, keep the company name in the section but omit it from the final ticker list.\n"
        "• End with:\n"
        "  רשימת סימבולים שהוזכרו בהקלטה:\n"
        "  <English tickers only, comma-separated, no duplicates>\n"
        "• Keep style consistent across runs."
    ),
)

# Optional hard cap for very large transcripts (character count).
INPUT_MAX_CHARS: Optional[int] = int(os.getenv("OPENAI_INPUT_MAX_CHARS", "0")) or None

# Retry policy
RETRIES: int = int(os.getenv("OPENAI_RETRIES", "3"))
RETRY_BASE_DELAY_SEC: float = float(os.getenv("OPENAI_RETRY_BASE", "1.2"))

# Local timezone for date fallback (used in title only if transcript has no date)
LOCAL_TZ = ZoneInfo(os.getenv("LOCAL_TZ", "Asia/Jerusalem"))


# ------------------------------------------------------------------------------
# Client setup
# ------------------------------------------------------------------------------
_api_key = os.getenv("OPENAI_API_KEY")
if not _api_key:
    _client: Optional[OpenAI] = None
    _client_init_error = "OPENAI_API_KEY is not set"
else:
    try:
        _client = OpenAI(api_key=_api_key)
        _client_init_error = None
    except Exception as e:
        _client = None
        _client_init_error = f"OpenAI client init error: {e}"


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def _prepare_text(text: str) -> str:
    """Optionally trim extreme inputs to avoid BadRequest (too large)."""
    if INPUT_MAX_CHARS and len(text) > INPUT_MAX_CHARS:
        return text[:INPUT_MAX_CHARS]
    return text


def _today_str() -> str:
    """Return today's date as DD.MM.YY in the configured timezone."""
    return datetime.now(LOCAL_TZ).strftime("%d.%m.%y")


def _call_openai_summary(text: str) -> str:
    """
    Single Responses API call using system instructions + user input.
    Avoids unsupported content types (e.g., 'prompt') and 'conversation'.
    """
    if _client is None:
        raise RuntimeError(_client_init_error or "OpenAI client not available")

    today_hint = f"Today's date (use only if transcript lacks a date): {_today_str()}"

    resp = cast(Any, _client).responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "system",
                "content": [
                    {"type": "input_text", "text": OPENAI_SYSTEM_PROMPT},
                    {"type": "input_text", "text": today_hint},
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": _prepare_text(text)}],
            },
        ],
    )
    out = getattr(resp, "output_text", "") or ""
    return out.strip()


# ------------------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------------------
def summarize_text(text: str) -> str:
    """
    Summarize a Hebrew transcript via OpenAI Responses API using system instructions.
    Always returns a string (never raises).
    """
    if not isinstance(text, str) or not text.strip():
        return "No text to summarize."

    last_err = ""
    delay = RETRY_BASE_DELAY_SEC

    for attempt in range(1, max(1, RETRIES) + 1):
        try:
            return _call_openai_summary(text)
        except (APIConnectionError, RateLimitError) as e:
            last_err = f"{e.__class__.__name__}: {e}"
            if attempt < RETRIES:
                time.sleep(delay)
                delay *= 2
                continue
            return f"Summary failed after retries: {last_err}"
        except BadRequestError as e:
            # Input too large / invalid format etc. No point retrying.
            return f"Summary failed (bad request): {str(e)[:200]}"
        except Exception as e:
            return f"Summary failed: {str(e)[:200]}"

    return "Summary failed: unknown error"
