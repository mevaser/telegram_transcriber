import os
import torch
from dotenv import load_dotenv
from telegram import Update, Message
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from pydub import AudioSegment
from time import time
import whisper

from log_utils import log_transcription

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if BOT_TOKEN is None:
    raise ValueError("BOT_TOKEN is not set in .env")

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Load Whisper model once at startup
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"🖥️ Torch device selected: {device.upper()}")
model = whisper.load_model("medium", device=device)
print("🧠 Whisper model loaded successfully")


# Handler for audio/voice messages
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("🔔 Message received!")
    message: Message | None = update.message
    if not message:
        print("⚠️ No message in update")
        return

    # Check if message has audio/voice
    file_id = None
    if message.voice:
        file_id = message.voice.file_id
        print("🎙️ Voice message")
    elif message.audio:
        file_id = message.audio.file_id
        print("🎵 Audio file")
    else:
        await message.reply_text("Please send a voice message or audio file.")
        return

    # Download file
    telegram_file = await context.bot.get_file(file_id)
    input_path = os.path.join(DOWNLOAD_DIR, f"{file_id}.mp3")
    await telegram_file.download_to_drive(input_path)
    print(f"✅ File downloaded to {input_path}")

    # Calculate audio duration
    audio = AudioSegment.from_file(input_path)
    duration_sec = len(audio) / 1000

    try:
        await message.reply_text("⏳ Starting transcription... please wait.")
        print("🧠 Transcribing...")

        start_time = time()
        result = model.transcribe(input_path, language="he", fp16=(device == "cuda"))
        end_time = time()

        transcript = str(result.get("text", "")).strip()
        print("📝 Transcription complete")

        log_transcription(
            file_path=input_path,
            success=True,
            duration_s=duration_sec,
            transcribe_time=end_time - start_time,
            output_len=len(transcript),
            device=device,
        )

        await message.reply_text("✅ Done. Here's the transcription:")
        await message.reply_text(
            transcript if transcript else "❌ Transcription was empty."
        )

    except Exception as e:
        print(f"🔥 Error: {e}")
        await message.reply_text(f"❌ Error:\n{str(e)}")

        log_transcription(
            file_path=input_path,
            success=False,
            duration_s=duration_sec,
            transcribe_time=0,
            output_len=0,
            device=device,
            error=str(e),
        )


# Start the bot
if __name__ == "__main__":
    print("🚀 Starting bot...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))
    print("✅ Bot is running. Waiting for messages...")
    app.run_polling()
