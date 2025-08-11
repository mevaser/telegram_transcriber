# 🧠 Telegram Transcriber & Model Comparator

This project provides an automated pipeline to:

- Transcribe **Hebrew WhatsApp audio messages**
- **Compare multiple transcription models**
- Automatically **summarize** the result with an LLM
- Supports **Telegram bot** integration for full automation

---

## 📂 Project Structure

```
telegram_transcriber/
|
├── bot.py                     # Telegram bot for voice-to-text & summary
├── whisper_utils.py           # Whisper transcriber
├── ivritai_utils.py           # IvritAI transcriber (RunPod)
├── llm_utils.py               # mBART summarization pipeline
├── merge_utils.py             # Combine multiple audio parts
├── log_utils.py               # Logging (transcription stats)
|
├── compare_transcripts/       # Model evaluation tools
│   ├── transcribe_whisper.py
│   ├── transcribe_ivritai.py
│   ├── transcribe_google.py
│   ├── compare.py              # WER/similarity comparison
│   ├── evaluate.py             # Accuracy metrics vs. ground truth
│   ├── fix_opus_metadata.py
│   ├── convert_audio.py
│   └── requirements.txt
|
├── data/                      # Organized storage for bot processing
│   ├── audio_parts
│   ├── merged_audio
│   ├── parts
│   ├── summaries
│   └── transcripts
|
├── logs/                      # Transcription logs (ignored)
├── .env                       # API keys + secrets (ignored)
└── requirements.txt           # Main dependencies
```

---

## 🔁 Workflow

1. **Receive voice/audio** via Telegram or manual input.
2. Choose processing mode from the menu (Transcribe, Summarize, or Transcribe+Summarize).
3. Audio is transcribed using IvritAI (via RunPod endpoint).
4. Transcript is saved to `.txt` and sent back via Telegram.
5. Summary is generated via **mBART (facebook/mbart-large-50-mmt)**.
6. Optional: compare transcription quality across models.

---

## 🧪 Transcription Model Comparison

We evaluated three Hebrew transcription models:

| Model       | CER (%) | WER (%) |
| ----------- | ------- | ------- |
| Whisper     | 8.2     | 17.2    |
| **IvritAI** | **0.9** | **2.3** |
| TurboScribe | 11.6    | 27.8    |

👉 **IvritAI achieved the best accuracy** across both CER and WER metrics.

> CER = Character Error Rate
> WER = Word Error Rate

---

## 🤖 Telegram Bot Usage

Run locally:

```bash
python bot.py
```

Required `.env` keys:

```
BOT_TOKEN=your_telegram_bot_token
RUNPOD_API_KEY=your_runpod_api_key
RUNPOD_ENDPOINT_ID=your_ivritai_endpoint_id
```

The bot menu allows you to select processing mode directly (no `/start_merge` command).

---

## ✅ Features

- Hebrew support with high accuracy (via IvritAI)
- Summarization using multilingual LLM
- Telegram bot interface with mode selection menu
- Support for multi-part WhatsApp audios
- Logging of transcription time, device, and length
- Easy model comparison tools

---

## 📌 Project Status

The project is **almost complete** and fully functional for its main use case:
Transcribing and summarizing daily audio updates for a **traders and investors community manager**.

Remaining optional enhancements:

- WhatsApp integration (manual or API)

---

## 📄 License

This project was developed for a **private client** (a traders & investors community manager).
Not affiliated with OpenAI, Google, RunPod, or IvritAI.
