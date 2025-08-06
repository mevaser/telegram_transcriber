# convert_audio.py
import os
from pathlib import Path
from pydub import AudioSegment

# Paths
INPUT_DIR = Path("compare_transcripts/audio")
OUTPUT_DIR = Path("compare_transcripts/audio_wav")
OUTPUT_DIR.mkdir(exist_ok=True)

# Convert all files to WAV (48000Hz, mono)
for audio_path in INPUT_DIR.glob("*"):
    try:
        print(f"🎧 Converting: {audio_path.name}")
        audio = AudioSegment.from_file(audio_path)
        audio = audio.set_frame_rate(48000).set_channels(1)
        out_path = OUTPUT_DIR / f"{audio_path.stem}.wav"
        audio.export(out_path, format="wav")
        print(f"✅ Saved: {out_path}")
    except Exception as e:
        print(f"❌ Failed to convert {audio_path.name}: {e}")
