# Simple Schedules Transcribe

**Simple Schedules Transcribe** is a locally hosted transcription tool built with Python, PyWebView, and Hugging Face Whisper models. Drag and drop audio/video, pick a Swedish or English model size, and generate diarized transcripts — **entirely on your machine, nothing is sent to the cloud.**

> A Simple Schedules fork of the NTIG Helsingborg / Skolverket transcription project, rebranded and made to run on **macOS** and **Linux** (tested on Linux Mint). Used with the original owner's permission.

## Highlights
- **Offline-first & GDPR-clean** — models download once into `cache/`; the UI ships its own fonts and icons, so it makes **zero external network requests**.
- Queue-based processing with per-file progress tracking.
- Speaker diarization (who said what) via Resemblyzer.
- Modern UI in the Simple Schedules palette for browsing, editing and managing saved transcripts.

## Requirements
- **Python 3.10+**
- **ffmpeg** (used to convert audio/video to WAV)
- A native WebView backend (bundled on macOS; a small package on Linux — see below)

## Getting Started

### macOS
```bash
brew install ffmpeg
pip install -r requirements.txt
python main.py
```

### Linux (Mint / Ubuntu / Debian)
```bash
sudo apt update
sudo apt install ffmpeg python3-gi gir1.2-webkit2-4.1 gir1.2-gtk-3.0
# On older releases use gir1.2-webkit2-4.0 instead of 4.1
pip install -r requirements.txt
python main.py
```

### Windows
```powershell
# Install ffmpeg (see requirements.txt for the step-by-step), then:
pip install -r requirements.txt
python main.py
```

Then use the **Ny transkribering** button to add files and start transcribing. Saved transcripts live in `Documents/Simple Schedules Transcribe`.

## Model Management
Open the settings modal (gear icon) to see which Whisper models are downloaded. Delete unused models there to reclaim disk space — they re-download automatically when needed.

## Building a standalone app
```bash
pip install pyinstaller
pyinstaller build.spec
```
The bundle appears in `dist/` (a `.app` on macOS, a folder on Linux/Windows).

## This project uses
- **ffmpeg** to convert audio/video to WAV
- **kb-whisper** (SE) and **whisper** (EN) for transcription
- **Python** + **PyWebView** for the native desktop UI
- **Resemblyzer** for speaker detection

---
Built for teams that need trustworthy, local speech-to-text when handling sensitive recordings.
Fork maintained by **Simple Schedules** · original by NTIG Helsingborg.
