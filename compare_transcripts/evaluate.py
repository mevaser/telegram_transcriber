# evaluate.py
from jiwer import wer, cer
from pathlib import Path

TRUTH_PATH = Path("truths/manual transcribe 05.08.txt")
FILENAME = "WhatsApp Audio 2025-08-05 at 16.05.18_756a7efb_1.txt"

TRANSCRIPTS = {
    "Whisper": Path("transcripts/whisper_large"),
    "IvritAI": Path("transcripts/ivritai"),
    "TurboScribe": Path("transcripts/TurboScribe"),
}


def run_evaluation():
    try:
        truth = TRUTH_PATH.read_text(encoding="utf-8").strip()
    except Exception as e:
        print(f"❌ Failed to read ground truth: {e}")
        return

    for model, path in TRANSCRIPTS.items():
        try:
            file = path / FILENAME
            if not file.exists():
                raise FileNotFoundError(f"File not found: {file}")

            prediction = file.read_text(encoding="utf-8").strip()

            model_wer = wer(truth, prediction)
            model_cer = cer(truth, prediction)

            print(f"\n📊 {model}")
            print(f"   🔹 WER: {model_wer:.3f}")
            print(f"   🔹 CER: {model_cer:.3f}")

        except Exception as e:
            print(f"\n❌ Error evaluating {model}: {e}")
