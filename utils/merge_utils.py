# utils/merge_utils.py

from pathlib import Path
import subprocess
import tempfile
import time
from typing import Sequence, Union
from utils.log_utils import log_transcription


def merge_audio_files(
    input_paths: Sequence[Union[str, Path]], output_path: Union[str, Path]
) -> Path:
    """
    Merge multiple audio files into a single file using ffmpeg without re-encoding,
    and log the merge details.

    Args:
        input_paths (Sequence[str | Path]): List of audio file paths to merge.
        output_path (str | Path): Destination path for merged file.

    Returns:
        Path: Absolute path to the merged audio file.

    Raises:
        ValueError: If no input files provided or a file does not exist.
        RuntimeError: If ffmpeg merge fails.
    """
    if not input_paths:
        raise ValueError("No input files to merge.")

    abs_inputs = []
    for path in input_paths:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            raise ValueError(f"Audio part not found: {p}")
        abs_inputs.append(p.as_posix())  # ffmpeg requires POSIX format

    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    success = False
    error_msg = ""

    # Create a temporary file list for ffmpeg
    with tempfile.NamedTemporaryFile(
        mode="w+", suffix=".txt", delete=False, encoding="utf-8"
    ) as list_file:
        for abs_path in abs_inputs:
            list_file.write(f"file '{abs_path}'\n")
        list_file_path = list_file.name

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_file_path,
                "-c:a",
                "copy",  # Keep original codec (no re-encoding)
                "-y",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )
        success = True
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode(errors="ignore")
        raise RuntimeError(f"FFmpeg merge failed:\n{error_msg}") from e
    finally:
        # Remove temp file
        try:
            Path(list_file_path).unlink(missing_ok=True)
        except Exception:
            pass

        elapsed_time = time.time() - start_time
        # Log merge event
        log_transcription(
            file_path=str(output_path),
            success=success,
            audio_duration_s=0,  # Unknown without decoding, set to 0
            transcribe_time_s=elapsed_time,
            output_len=len(abs_inputs),
            error=error_msg,
        )

    if not output_path.exists():
        raise RuntimeError(f"Merged file was not created: {output_path}")

    return output_path
