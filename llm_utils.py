from transformers.pipelines import pipeline
import torch
from typing import List, Dict, Any

# Load multilingual summarization pipeline
device = 0 if torch.cuda.is_available() else -1
_summarizer = pipeline(
    task="summarization",
    model="facebook/mbart-large-50-many-to-many-mmt",
    tokenizer="facebook/mbart-large-50-many-to-many-mmt",  # use slow tokenizer
    device=device,
    use_fast=False,  # ✅ disable fast tokenizer (causes crash on Windows)
)


def summarize_text(text: str) -> str:
    """
    Summarize Hebrew text using mBART model.
    """
    # Run the summarizer
    result: Any = _summarizer(
        text,
        max_length=2000,
        min_length=50,
        do_sample=False,
        source_lang="he_HE",
        tgt_lang="he_HE",
    )

    # Check for result structure safety
    if (
        result
        and isinstance(result, list)
        and len(result) > 0
        and "summary_text" in result[0]
    ):
        return str(result[0]["summary_text"])
    else:
        return "⚠️ Summary generation failed."
