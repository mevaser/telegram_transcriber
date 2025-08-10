# utils/log_utils.py
import os
import logging
import torch
from pathlib import Path
from typing import Optional, Union

# ─── Ensure logs folder exists ───────────────────────────────────────────────
LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
os.makedirs(LOGS_DIR, exist_ok=True)

LOG_FILE_PATH = os.path.join(LOGS_DIR, "transcription.log")

logging.basicConfig(
    filename=LOG_FILE_PATH,
    level=logging.INFO,
    format="[{asctime}] {message}",
    style="{",
    encoding="utf-8",
)


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _fmt_hms(seconds: float) -> str:
    """Format seconds as M:SS or H:MM."""
    try:
        total = int(seconds)
    except Exception:
        return "0:00"
    m, s = divmod(total, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}" if h else f"{m}:{s:02d}"


# ─── Transcription Logging ───────────────────────────────────────────────────
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
        file_path: Path to the processed audio file.
        success: Whether transcription succeeded.
        audio_duration_s: Duration of the audio in seconds.
        transcribe_time_s: Time taken for transcription in seconds.
        output_len: Length of the output transcript in characters.
        device: Processing device ("CPU"/"GPU"). Auto-detected if None.
        error: Error message if failed.
    """
    if device is None:
        device = "GPU" if torch.cuda.is_available() else "CPU"

    status = "✅" if success else "❌"
    dur_str = _fmt_hms(audio_duration_s)
    transcribe_time_s = round(transcribe_time_s, 2)

    if success:
        logging.info(
            f"{status} Transcribed {dur_str} in {transcribe_time_s}s on {device} "
            f"| file: {Path(file_path).expanduser().resolve().as_posix()} "
            f"| output: {output_len} chars"
        )
    else:
        logging.error(
            f"{status} Failed on {device} "
            f"| file: {Path(file_path).expanduser().resolve().as_posix()} "
            f"| error: {error}"
        )


# ─── Merge Logging ───────────────────────────────────────────────────────────
def log_merge(
    file_path: Union[str, os.PathLike[str]],
    success: bool,
    parts_count: int,
    merge_time_s: float,
    audio_duration_s: float,
    error: str = "",
) -> None:
    """
    Log the result of an audio merge operation (not transcription).
    """
    status = "✅" if success else "❌"
    dur_hms = _fmt_hms(audio_duration_s)
    merge_time_s = round(merge_time_s, 2)
    file_abs = Path(file_path).expanduser().resolve().as_posix()

    if success:
        logging.info(
            f"{status} Merged {parts_count} parts in {merge_time_s}s "
            f"| file: {file_abs} | duration: {dur_hms}"
        )
    else:
        msg = (
            f"{status} Merge failed in {merge_time_s}s "
            f"| file: {file_abs} | duration: {dur_hms}"
        )
        if error:
            msg += f" | error: {error.strip()}"
        logging.error(msg)


# ─── Artifacts Logging ───────────────────────────────────────────────────────
def log_artifact(tag: str, path: Union[str, os.PathLike[str]]) -> None:
    """
    Log a saved artifact location (e.g., 'Transcript saved', 'Summary saved').
    """
    abs_path = Path(path).expanduser().resolve().as_posix()
    logging.info(f"📦 {tag}: {abs_path}")
