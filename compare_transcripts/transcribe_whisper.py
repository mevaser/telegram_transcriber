# transcribe_whisper.py
import whisper
from pathlib import Path

MODEL_SIZE = "large"
LANGUAGE = "he"
AUDIO_DIR = Path("audio")
OUTPUT_DIR = Path("transcripts/whisper_large")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ─── Utility: Ensure output file is unique ─────────────────────────────────────
def get_unique_path(base_path: Path) -> Path:
    if not base_path.exists():
        return base_path
    counter = 1
    while True:
        new_path = base_path.with_name(f"{base_path.stem}_{counter}{base_path.suffix}")
        if not new_path.exists():
            return new_path
        counter += 1


# ─── Main Transcription ────────────────────────────────────────────────────────
def transcribe_whisper(audio_dir=AUDIO_DIR):
    model = whisper.load_model(MODEL_SIZE)

    for path in audio_dir.glob("*"):
        if not path.is_file():
            continue

        print(f"🔊 Transcribing with Whisper: {path.name}")
        result = model.transcribe(str(path), language=LANGUAGE)
        text = result["text"].strip()

        out_path = get_unique_path(OUTPUT_DIR / f"{path.stem}.txt")
        out_path.write_text(text, encoding="utf-8")
        print(f"📄 Saved: {out_path}")


if __name__ == "__main__":
    transcribe_whisper()
