# utils/ivritAI_utils.py – IvritAI wrapper for transcription via Runpod
import os
import time
import shutil
import subprocess
from pathlib import Path
from typing import Tuple, Union, Optional, Callable, Iterable, Any

from dotenv import load_dotenv
import ivrit

# Try import chunking constants; fall back to sane defaults if not present
try:
    from handlers.constants import CHUNK_SEC, OVERLAP_SEC, FFMPEG_BIN, FFPROBE_BIN
except Exception:
    CHUNK_SEC = 240  # 4 minutes per chunk
    OVERLAP_SEC = 1.2  # seconds overlap between chunks
    FFMPEG_BIN = "ffmpeg"
    FFPROBE_BIN = "ffprobe"

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


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _probe_duration_seconds(path: Path) -> float:
    """Return audio duration in seconds using ffprobe."""
    out = subprocess.check_output(
        [
            FFPROBE_BIN,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    ).strip()
    return float(out) if out else 0.0


def _split_with_overlap(
    src: Path, chunk_sec: int, overlap_sec: float, dst_dir: Path
) -> list[Path]:
    """
    Split audio into fixed-length chunks with a small overlap to avoid cutting
    words in the middle. Uses stream copy (fast).
    """
    dst_dir.mkdir(parents=True, exist_ok=True)
    dur = _probe_duration_seconds(src)

    step = max(1.0, chunk_sec - overlap_sec)  # start gap between chunks
    starts = []
    t = 0.0
    while t < dur:
        starts.append(t)
        t += step

    paths: list[Path] = []
    for i, start in enumerate(starts):
        out = dst_dir / f"chunk_{i:03d}.opus"
        # Keep OPUS codec (fast). If you ever see cutting artifacts, re-encode:
        # replace ["-c","copy"] with ["-c:a","libopus","-b:a","64k"]
        subprocess.check_call(
            [
                FFMPEG_BIN,
                "-y",
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{chunk_sec:.3f}",
                "-i",
                str(src),
                "-c",
                "copy",
                str(out),
            ]
        )
        paths.append(out)

    return paths


def _extract_text_safe(result: Any) -> str:
    """
    Safely extract text from various possible return types of model.transcribe().
    Supports dicts, strings, and generators/iterables of dicts/strings.
    """
    # dict-like
    if isinstance(result, dict):
        txt = result.get("text", "")
        return (txt or "").strip()

    # plain string
    if isinstance(result, str):
        return result.strip()

    # bytes (rare)
    if isinstance(result, (bytes, bytearray)):
        try:
            return bytes(result).decode("utf-8", errors="ignore").strip()
        except Exception:
            return str(result).strip()

    # generator / iterable of segments or strings
    if isinstance(result, Iterable):
        parts: list[str] = []
        for item in result:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")).strip())
            elif isinstance(item, str):
                parts.append(item.strip())
            elif isinstance(item, (bytes, bytearray)):
                try:
                    parts.append(bytes(item).decode("utf-8", errors="ignore").strip())
                except Exception:
                    parts.append(str(item).strip())
            else:
                parts.append(str(item).strip())
        return " ".join(p for p in parts if p).strip()

    # fallback
    return str(result or "").strip()


def _stitch_with_overlap_text(
    chunks_texts: list[str], min_k: int = 10, max_k: int = 80
) -> str:
    """
    Merge transcripts by removing duplicated overlap between the end of the
    previous chunk and the start of the current one.
    """
    out: list[str] = []
    for i, txt in enumerate(chunks_texts):
        cur = (txt or "").strip()
        if not cur:
            continue
        if i == 0:
            out.append(cur)
            continue

        prev = out[-1]
        k_found = 0
        max_try = min(max_k, len(prev), len(cur))
        for k in range(max_try, min_k - 1, -1):
            if prev[-k:] == cur[:k]:
                k_found = k
                break

        out[-1] = prev + ("" if k_found else " ") + cur[k_found:]

    return "\n".join(out).strip()


# ─── Public API ───────────────────────────────────────────────────────────────
def transcribe_audio(
    path: Union[str, os.PathLike[str]],
    *,
    language: str = "he",
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Tuple[str, float]:
    """
    Transcribe Hebrew audio using IvritAI via Runpod.
    For long audio, automatically chunk with overlap to stay under API payload limits.

    Args:
        path: Path to the audio file.
        language: ASR language code ('he' default).
        progress_cb: Optional callback reporting (chunk_index, total_chunks).

    Returns:
        (transcript_text, elapsed_seconds)
    """
    audio_path = Path(path).expanduser().resolve()
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    t0 = time.perf_counter()
    duration_sec = _probe_duration_seconds(audio_path)

    # Short files: one-shot
    if duration_sec <= CHUNK_SEC:
        try:
            raw = model.transcribe(path=str(audio_path), language=language) or {}
        except Exception as e:
            raise RuntimeError(f"Transcription failed for {audio_path}: {e}") from e

        text = _extract_text_safe(raw)
        return text, time.perf_counter() - t0

    # Long files: chunk with overlap
    tmp_dir = audio_path.parent / f"{audio_path.stem}_chunks"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)

    chunks = _split_with_overlap(audio_path, CHUNK_SEC, OVERLAP_SEC, tmp_dir)
    texts: list[str] = []
    total = len(chunks)

    for i, ch in enumerate(chunks, 1):
        if progress_cb:
            try:
                progress_cb(i, total)
            except Exception:
                pass
        try:
            raw = model.transcribe(path=str(ch), language=language) or {}
        except Exception as e:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise RuntimeError(
                f"Transcription failed for chunk {i}/{total} ({ch.name}): {e}"
            ) from e

        texts.append(_extract_text_safe(raw))

    full_text = _stitch_with_overlap_text(texts)

    # Cleanup
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

    return full_text, time.perf_counter() - t0
