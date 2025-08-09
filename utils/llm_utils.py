# utils/llm_utils.py – Hebrew summarization via mBART
from __future__ import annotations

from typing import Any, Optional
import torch
from transformers import pipeline

# ─── Load multilingual summarization pipeline ────────────────────────────────
device = 0 if torch.cuda.is_available() else -1
try:
    _summarizer = pipeline(
        task="summarization",
        model="facebook/mbart-large-50-many-to-many-mmt",
        tokenizer="facebook/mbart-large-50-many-to-many-mmt",
        device=device,
        use_fast=False,  # prevent Windows crashes with fast tokenizers
    )
except Exception as e:
    raise RuntimeError(f"Failed to load summarization model: {e}") from e


def _hebrew_bos_token_id() -> Optional[int]:
    """
    Safely resolve BOS token id for Hebrew ("he_HE") if tokenizer supports it.
    Returns None if unavailable, which means no forced BOS will be used.
    """
    tok = getattr(_summarizer, "tokenizer", None)
    # Some tokenizers expose 'lang_code_to_id' (e.g., mBART); others don't.
    lang_map = getattr(tok, "lang_code_to_id", None)
    if isinstance(lang_map, dict):
        val = lang_map.get("he_HE")
        if isinstance(val, int):
            return val
    return None


# ─── Summarization Function ───────────────────────────────────────────────────
def summarize_text(text: str) -> str:
    """
    Summarize Hebrew text using mBART model.

    Args:
        text (str): The Hebrew text to summarize.

    Returns:
        str: The generated summary (Hebrew) or an informative message on failure.
    """
    if not isinstance(text, str) or not text.strip():
        return "⚠️ No valid text provided for summarization."

    forced_bos = _hebrew_bos_token_id()

    try:
        # NOTE: Adjust max_length/min_length as needed for your content lengths.
        result: Any = _summarizer(
            text,
            max_length=2000,
            min_length=50,
            do_sample=False,
            forced_bos_token_id=forced_bos,  # None is fine if unsupported
        )
    except Exception as e:
        return f"⚠️ Summary generation error: {e}"

    # Validate and extract pipeline output
    if (
        isinstance(result, list)
        and len(result) > 0
        and isinstance(result[0], dict)
        and "summary_text" in result[0]
    ):
        summary = result[0]["summary_text"]
        return (
            summary.strip() if isinstance(summary, str) else str(summary or "").strip()
        )

    return "⚠️ Summary generation failed."
