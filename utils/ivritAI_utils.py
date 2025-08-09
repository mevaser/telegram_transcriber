# utils/ivritAI_utils.py – IvritAI wrapper for transcription via Runpod

import os
import time
from pathlib import Path
from typing import Tuple, Union
from dotenv import load_dotenv
import ivrit

# ─── Device Info ─────────────────────────────────────────────────────────────
DEVICE = "runpod"

# ─── Load Environment Variables ───────────────────────────────────────────────
load_dotenv()
API_KEY = os.getenv("RUNPOD_API_KEY")
ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID")
MODEL_NAME = "ivrit-ai/whisper-large-v3-turbo-ct2"

if not API_KEY or not ENDPOINT_ID:
    raise EnvironmentError("Missing RUNPOD_API_KEY or RUNPOD_ENDPOINT_ID in .env")

# ─── Load Model (once) ────────────────────────────────────────────────────────
try:
    model = ivrit.load_model(
        engine=DEVICE,
        model=MODEL_NAME,
        api_key=API_KEY,
        endpoint_id=ENDPOINT_ID,
    )
except Exception as e:
    raise RuntimeError(f"Failed to load IvritAI model: {e}") from e


# ─── Transcription Function ───────────────────────────────────────────────────
def transcribe_audio(path: Union[str, os.PathLike[str]]) -> Tuple[str, float]:
    """
    Transcribe Hebrew audio using IvritAI via Runpod.

    Args:
        path (str | Path): Path to the audio file.

    Returns:
        tuple[str, float]: (transcript_text, elapsed_seconds)
    """
    audio_path = Path(path).expanduser().resolve()
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    start_time = time.time()
    try:
        result = model.transcribe(path=str(audio_path), language="he") or {}
    except Exception as e:
        raise RuntimeError(f"Transcription failed for {audio_path}: {e}") from e

    if not isinstance(result, dict):
        raise ValueError(
            f"Unexpected transcription result type: {type(result).__name__}"
        )

    text = result.get("text", "")
    if not isinstance(text, str):
        text = str(text or "")

    return text.strip(), time.time() - start_time
