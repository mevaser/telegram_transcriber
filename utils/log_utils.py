# utils/log_utils.py

import os
import logging
import torch
from typing import Optional, Union

# ─── Ensure logs folder exists ───────────────────────────────────────────────
LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

LOG_FILE_PATH = os.path.join(LOGS_DIR, "transcription.log")

logging.basicConfig(
    filename=LOG_FILE_PATH,
    level=logging.INFO,
    format="[{asctime}] {message}",
    style="{",
    encoding="utf-8",
)


# ─── Logging Function ─────────────────────────────────────────────────────────
def log_transcription(
    file_path: Union[str, os.PathLike[str]],
    success: bool,
    audio_duration_s: float,
    transcribe_time_s: float,
    output_len: int,
    device: Optional[str] = None,
    error: str = "",
) -> None:
    """
    Log the result of an audio transcription process.

    Args:
        file_path (str | PathLike): Path to the processed audio file.
        success (bool): Whether the transcription succeeded.
        audio_duration_s (float): Duration of the audio in seconds.
        transcribe_time_s (float): Time taken for transcription in seconds.
        output_len (int): Length of the output transcript in characters.
        device (str, optional): Processing device ("CPU"/"GPU"). Auto-detected if None.
        error (str, optional): Error message if failed.
    """
    if device is None:
        device = "GPU" if torch.cuda.is_available() else "CPU"

    status = "✅" if success else "❌"
    dur_str = f"{int(audio_duration_s // 60)}:{int(audio_duration_s % 60):02}"
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
