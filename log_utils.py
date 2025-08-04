# log_utils.py

import os
import logging
import torch
from typing import Optional

# Ensure logs folder exists
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/transcription.log",
    level=logging.INFO,
    format="[{asctime}] {message}",
    style="{",
    encoding="utf-8",
)


def log_transcription(
    file_path: str,
    success: bool,
    audio_duration_s: float,
    transcribe_time_s: float,
    output_len: int,
    device: Optional[str] = None,
    error: str = "",
) -> None:
    if device is None:
        device = "GPU" if torch.cuda.is_available() else "CPU"
    status = "✅" if success else "❌"
    dur_str = f"{int(audio_duration_s//60)}:{int(audio_duration_s%60):02}"
    transcribe_time_s = round(transcribe_time_s, 2)
    if success:
        logging.info(
            f"{status} Transcribed {dur_str} in {transcribe_time_s}s on {device} "
            f"| file: {file_path} | output: {output_len} chars"
        )
    else:
        logging.error(
            f"{status} Failed on {device} | file: {file_path} | error: {error}"
        )
