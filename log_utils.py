import os
import logging
import torch
from typing import Optional

# Create logs folder if not exists
os.makedirs("logs", exist_ok=True)

# Configure logger
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
    duration_s: float,
    transcribe_time: float,
    output_len: int,
    device: Optional[str] = None,
    error: str = "",
) -> None:
    if device is None:
        device = "GPU" if torch.cuda.is_available() else "CPU"

    status = "✅" if success else "❌"
    duration_str = f"{int(duration_s // 60)}:{int(duration_s % 60):02}"
    transcribe_time = round(transcribe_time, 2)

    if success:
        logging.info(
            f"{status} Transcribed {duration_str} in {transcribe_time}s on {device} | file: {file_path} | output: {output_len} chars"
        )
    else:
        logging.error(
            f"{status} Failed on {device} | file: {file_path} | error: {error}"
        )
