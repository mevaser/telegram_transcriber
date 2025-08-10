# handlers/constants.py
from pathlib import Path

# --- user_data keys ---
STATE_MODE = "mode"
STATE_PARTS = "parts"
STATE_COLLECTING = "collecting"

# --- mode values ---
MODE_TRANSCRIBE = "transcribe"
MODE_SUMMARIZE = "summarize"
MODE_BOTH = "both"

# --- callback data ---
CB_SET_MODE_TRANSCRIBE = "set_mode_transcribe"
CB_SET_MODE_SUMMARIZE = "set_mode_summarize"
CB_SET_MODE_BOTH = "set_mode_both"
CB_MORE_YES = "more_yes"
CB_MORE_NO = "more_no"

# --- folders (absolute inside project) ---
BASE_DIR: Path = Path(__file__).resolve().parents[1]
DATA_DIR: Path = BASE_DIR / "data"
PARTS_DIR: Path = DATA_DIR / "parts"
MERGED_DIR: Path = DATA_DIR / "merged_audio"
TRANSCRIPTS_DIR: Path = DATA_DIR / "transcripts"  # raw ASR text files
SUMMARIES_DIR: Path = DATA_DIR / "summaries"  # LLM summaries

# ensure folders exist early
for p in (PARTS_DIR, MERGED_DIR, TRANSCRIPTS_DIR, SUMMARIES_DIR):
    p.mkdir(parents=True, exist_ok=True)
