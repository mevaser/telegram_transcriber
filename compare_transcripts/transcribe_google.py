# transcribe_google.py
import os
from pathlib import Path
from google.cloud import speech_v1p1beta1 as speech
from dotenv import load_dotenv
import pprint

# Load credentials
load_dotenv()
credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if not credentials_path or not Path(credentials_path).exists():
    raise EnvironmentError("Missing or invalid GOOGLE_APPLICATION_CREDENTIALS")

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

# GCS audio URIs to transcribe
GCS_URIS = [
    (
        "WhatsApp Audio 2025-08-05 at 16.05.18_756a7efb",
        "gs://telegram-transcriber-mevaser/WhatsApp Audio 2025-08-05 at 16.05.18_756a7efb.opus",
    ),
]

LANGUAGE_CODE = "he-IL"
OUTPUT_DIR = Path("transcripts/google")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_unique_path(base_path: Path) -> Path:
    """Ensure the output filename is unique (adds _1, _2 if needed)."""
    if not base_path.exists():
        return base_path
    counter = 1
    while True:
        candidate = base_path.with_name(f"{base_path.stem}_{counter}{base_path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def transcribe_gcs_file(stem: str, gcs_uri: str):
    client = speech.SpeechClient()

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
        sample_rate_hertz=48000,
        language_code=LANGUAGE_CODE,
        enable_automatic_punctuation=True,
    )
    audio = speech.RecognitionAudio(uri=gcs_uri)

    print(f"🎧 Transcribing: {gcs_uri}")
    operation = client.long_running_recognize(config=config, audio=audio)
    response = operation.result(timeout=600)
    pprint.pprint(response)

    if not response.results:
        print("⚠️ Google API returned no transcription results.")
        return

    text = " ".join(
        result.alternatives[0].transcript for result in response.results
    ).strip()

    out_path = get_unique_path(OUTPUT_DIR / f"{stem}.txt")
    out_path.write_text(text, encoding="utf-8")
    print(f"✅ Saved to: {out_path}")


def transcribe_google_from_gcs():
    for stem, uri in GCS_URIS:
        try:
            transcribe_gcs_file(stem, uri)
        except Exception as e:
            print(f"🚫 Failed to transcribe {uri}: {e}")


if __name__ == "__main__":
    transcribe_google_from_gcs()
