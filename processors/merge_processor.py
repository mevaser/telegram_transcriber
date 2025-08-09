# processors/merge_processor.py
import subprocess
import tempfile
from pathlib import Path
from typing import List


class MergeProcessor:
    """
    Robust merge that outputs a single .opus file.
    Steps:
      1) Normalize each input to Opus 48k mono (consistent codec/params).
      2) Concat with ffmpeg concat demuxer using stream copy (-c copy).
      3) ffprobe the result and fail early if duration < 1s.
    Requires: ffmpeg, ffprobe in PATH.
    """

    def __init__(self, merged_dir: str):
        self.merged_dir = Path(merged_dir)
        self.merged_dir.mkdir(parents=True, exist_ok=True)

    def _run(self, cmd: list[str]) -> None:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{proc.stderr}")

    def _probe_duration(self, path: Path) -> float:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {proc.stderr}")
        try:
            return float(proc.stdout.strip())
        except Exception:
            return 0.0

    def merge(self, parts: List[str], out_name: str) -> str:
        if not parts:
            raise ValueError("No parts to merge")

        # Force .opus extension for output
        out_name = Path(out_name).with_suffix(".opus").name
        out_path = self.merged_dir / out_name

        with tempfile.TemporaryDirectory(prefix="merge_norm_") as td:
            tmpdir = Path(td)

            # 1) Normalize all inputs to opus (same params)
            normalized_paths: list[Path] = []
            for idx, p in enumerate(parts, start=1):
                src = Path(p)
                if not src.exists():
                    raise FileNotFoundError(f"Missing input: {src}")

                norm = tmpdir / f"part_{idx:03d}.opus"
                # Re-encode to Opus 48k mono @ 64 kbps (tweak if you like)
                self._run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(src),
                        "-vn",
                        "-acodec",
                        "libopus",
                        "-b:a",
                        "64k",
                        "-ar",
                        "48000",
                        "-ac",
                        "1",
                        str(norm),
                    ]
                )
                normalized_paths.append(norm)

            # 2) Write concat list
            concat_file = tmpdir / "concat.txt"
            concat_file.write_text(
                "\n".join([f"file '{p.as_posix()}'" for p in normalized_paths]),
                encoding="utf-8",
            )

            # 3) Concat using stream copy (no re-encode)
            self._run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_file),
                    "-c",
                    "copy",
                    str(out_path),
                ]
            )

        # 4) Sanity-check duration
        dur = self._probe_duration(out_path)
        if dur < 1.0:
            # if concat produced a broken/empty file, delete and fail
            try:
                out_path.unlink(missing_ok=True)
            finally:
                raise RuntimeError(f"Merged output duration too short ({dur:.2f}s)")

        return str(out_path)
