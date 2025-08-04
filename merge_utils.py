# merge_utils.py

from pydub import AudioSegment


def merge_audio_files(input_paths: list[str], output_path: str) -> None:
    """
    Merge multiple audio files into a single file using pydub.
    """
    if not input_paths:
        raise ValueError("No input files to merge.")

    combined = AudioSegment.empty()
    for path in input_paths:
        audio = AudioSegment.from_file(path)
        combined += audio

    combined.export(output_path, format="mp3")
