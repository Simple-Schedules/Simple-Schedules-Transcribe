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

## Give it to someone (the easy way)

Tell them to open **Terminal** and paste this **one line** (works on macOS and
Linux Mint alike):

```bash
curl -fsSL https://raw.githubusercontent.com/Simple-Schedules/Simple-Schedules-Transcribe/main/bootstrap.sh | bash
```

It downloads the app and installs everything. When it finishes, they type:

```bash
transcribe
```

…and the app opens. That's it — see **[caveman instructions](#caveman-instructions)** below for the click-by-click version.

## Quick start (macOS & Linux)

If you already have the project folder, one command sets everything up — it
installs ffmpeg, a modern Python if needed, and all dependencies into an
isolated `.venv`:

```bash
./install.sh   # first time only
```

After that, just type **`transcribe`** in **any** terminal, from **any** directory:

```bash
transcribe
```

The app launches detached — **you can close the terminal and it keeps running.**
(The installer adds a global `transcribe` command to your PATH.)

You can also still use `./run.sh` from the project folder, or on **macOS**
**double-click `Launch Simple Schedules Transcribe.command`** in Finder.

> The installer is idempotent, so it's safe to re-run. On macOS it will install
> [Homebrew](https://brew.sh) automatically if you don't have it.

### Manual setup

<details>
<summary>macOS</summary>

```bash
brew install ffmpeg
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```
</details>

<details>
<summary>Linux (Mint / Ubuntu / Debian)</summary>

```bash
sudo apt update
sudo apt install ffmpeg python3-venv python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1
# On older releases use gir1.2-webkit2-4.0 instead of 4.1
python3 -m venv --system-site-packages .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```
</details>

<details>
<summary>Windows</summary>

```powershell
# Install ffmpeg (see requirements.txt for the step-by-step), then:
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```
</details>

Then use the **Ny transkribering** button to add files and start transcribing. Saved transcripts live in `Documents/Simple Schedules Transcribe`.

## Model Management
Open the settings modal (gear icon) to see which Whisper models are downloaded. Delete unused models there to reclaim disk space — they re-download automatically when needed.

## Building a standalone app
```bash
pip install pyinstaller
pyinstaller build.spec
```
The bundle appears in `dist/` (a `.app` on macOS, a folder on Linux/Windows).

## Caveman instructions

**For a Mac:**
1. Press **Cmd + Space**, type **Terminal**, press **Enter**.
2. Copy this line, paste it in the black window, press **Enter**:
   ```
   curl -fsSL https://raw.githubusercontent.com/Simple-Schedules/Simple-Schedules-Transcribe/main/bootstrap.sh | bash
   ```
3. If a popup asks to install "Command Line Tools", click **Install**, wait, then
   paste the line again.
4. Wait until it says **"✓ Installation complete."** (first time takes a few minutes).
5. Type **`transcribe`** and press **Enter**. The app opens.
6. From now on: open Terminal, type **`transcribe`**, press **Enter**. Done.

**For a Linux Mint computer:**
1. Open **Terminal** (Menu → Terminal, or **Ctrl + Alt + T**).
2. Copy this line, paste it (**Ctrl + Shift + V**), press **Enter**:
   ```
   curl -fsSL https://raw.githubusercontent.com/Simple-Schedules/Simple-Schedules-Transcribe/main/bootstrap.sh | bash
   ```
3. Type your password if it asks (you won't see it typing — that's normal), press **Enter**.
4. Wait until it says **"✓ Installation complete."**
5. Type **`transcribe`** and press **Enter**. The app opens.
6. From now on: open Terminal, type **`transcribe`**, done.

> You can close the terminal window after the app opens — it keeps running.

## This project uses
- **ffmpeg** to convert audio/video to WAV
- **kb-whisper** (SE) and **whisper** (EN) for transcription
- **Python** + **PyWebView** for the native desktop UI
- **Resemblyzer** for speaker detection

---
Built for teams that need trustworthy, local speech-to-text when handling sensitive recordings.
Fork maintained by **Simple Schedules** · original by NTIG Helsingborg.
