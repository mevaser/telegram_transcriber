import torch
import whisper
from pydub import AudioSegment
from typing import List, Tuple
import time

# Detect device
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Load Whisper model once on the correct device
MODEL = whisper.load_model("medium", device=DEVICE)


def transcribe_audio(path: str) -> Tuple[str, float]:
    """
    Transcribe audio via Whisper.
    Returns the transcript and elapsed time in seconds.
    """
    start_time = time.time()
    result = MODEL.transcribe(path, language="he", fp16=(DEVICE == "cuda"))
    elapsed = time.time() - start_time

    transcript = result.get("text", "")
    if not isinstance(transcript, str):
        transcript = str(transcript)
    return transcript, elapsed
