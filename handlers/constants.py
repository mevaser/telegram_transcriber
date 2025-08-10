# handlers/constants.py
import os
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

# --- folders (absolute) ---
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
PARTS_DIR = str(DATA_DIR / "parts")
MERGED_DIR = str(DATA_DIR / "merged_audio")
TRANSCRIPTS_DIR = str(Path("data/transcripts"))  # adjust if your path differs

# ensure folders exist early
for p in (PARTS_DIR, MERGED_DIR, TRANSCRIPTS_DIR):
    Path(p).mkdir(parents=True, exist_ok=True)
