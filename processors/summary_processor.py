# processors/summary_processor.py
from typing import Optional
from utils.llm_utils import summarize_text  # should return str or None


class SummaryProcessor:
    def summarize(self, text: Optional[str]) -> str:
        """
        Produce a concise Hebrew summary for the given transcript text.

        Args:
            text (str | None): The text to summarize.

        Returns:
            str: The generated summary, or an empty string if text is invalid.
        """
        if not text or not text.strip():
            return ""

        try:
            summary = summarize_text(text)
        except Exception as e:
            # Optional: log the exception if you have a logger
            # logger.exception("summarize_text failed: %s", e)
            return ""

        if not isinstance(summary, str):
            return ""

        return summary.strip()
