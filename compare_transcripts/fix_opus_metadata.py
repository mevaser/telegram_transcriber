# fix_opus_metadata.py
import subprocess
from pathlib import Path

# Paths
INPUT_DIR = Path("compare_transcripts/audio")
OUTPUT_DIR = Path("compare_transcripts/audio_fixed")
OUTPUT_DIR.mkdir(exist_ok=True)

# Loop over all OPUS files and fix metadata
for opus_file in INPUT_DIR.glob("*.opus"):
    output_path = OUTPUT_DIR / opus_file.name
    print(f"🎧 Fixing metadata: {opus_file.name}")

    cmd = [
        "ffmpeg",
        "-i",
        str(opus_file),
        "-c:a",
        "libopus",
        "-ar",
        "48000",  # Set sample rate
        "-ac",
        "1",  # Mono
        str(output_path),
    ]

    try:
        subprocess.run(
            cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print(f"✅ Saved: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to fix {opus_file.name}: {e}")
