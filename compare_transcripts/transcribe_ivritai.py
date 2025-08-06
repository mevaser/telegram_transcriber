# transcribe_ivritai.py
import os
from pathlib import Path
from dotenv import load_dotenv
import ivrit

# ─── Configuration ─────────────────────────────────────────────────────────────
load_dotenv()
API_KEY = os.getenv("RUNPOD_API_KEY")
ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID")
MODEL_NAME = "ivrit-ai/whisper-large-v3-turbo-ct2"
AUDIO_DIR = Path("audio")
OUTPUT_DIR = Path("transcripts/ivritai")

if not API_KEY or not ENDPOINT_ID:
    raise EnvironmentError("Missing RUNPOD_API_KEY or RUNPOD_ENDPOINT_ID in .env")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── Load model ────────────────────────────────────────────────────────────────
model = ivrit.load_model(
    engine="runpod", model=MODEL_NAME, api_key=API_KEY, endpoint_id=ENDPOINT_ID
)


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


# ─── Transcribe all audio files ────────────────────────────────────────────────
def transcribe_all():
    for audio_path in AUDIO_DIR.glob("*"):
        if not audio_path.is_file():
            continue

        existing_transcripts = list(OUTPUT_DIR.glob(f"{audio_path.stem}*.txt"))
        if existing_transcripts:
            print(f"⏩ Skipping (already transcribed): {audio_path.name}")
            continue

        print(f"🎧 Transcribing: {audio_path.name}")
        try:
            result = model.transcribe(path=str(audio_path), language="he")
            text = result.get("text", "").strip()

            out_path = get_unique_path(OUTPUT_DIR / f"{audio_path.stem}.txt")
            out_path.write_text(text, encoding="utf-8")
            print(f"✅ Saved transcript: {out_path}")
        except Exception as e:
            print(f"🚫 Failed to transcribe {audio_path.name}: {e}")


# ─── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    transcribe_all()
