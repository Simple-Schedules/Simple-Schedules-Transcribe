<div align="center">

<img src="assets/icon.png" alt="Simple Schedules Transcribe" width="120" />

# Simple Schedules Transcribe

**Local, offline speech-to-text — Swedish &amp; English — that never sends your recordings to the cloud.**

![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20Mint-4361ee)
![Offline](https://img.shields.io/badge/100%25-offline-ffc300)
![Privacy](https://img.shields.io/badge/GDPR-clean-4361ee)
![Python](https://img.shields.io/badge/python-3.10%2B-3451d1)

</div>

Drag and drop audio or video, pick a Swedish or English model size, and get a
diarized transcript (who said what) — **entirely on your machine.** No account,
no upload, no external network requests.

> A **Simple Schedules** fork of the NTIG Helsingborg / Skolverket transcription
> project, rebranded and made to run on **macOS** and **Linux Mint**. Used with
> the original authors' permission — see [Credits](#credits).

## Contents
- [Install (one line)](#give-it-to-someone-the-easy-way)
- [Open the app](#opening-the-app)
- [Caveman instructions](#caveman-instructions)
- [Manual setup](#manual-setup)
- [Credits](#credits)

## Highlights
- **Offline-first & GDPR-clean** — models download once into `cache/`; the UI ships its own fonts and icons, so it makes **zero external network requests**.
- **One-command install** and a **clickable app icon** on both macOS and Linux.
- Queue-based processing with per-file progress tracking.
- Speaker diarization (who said what) via Resemblyzer.
- Modern UI in the Simple Schedules palette for browsing, editing and managing saved transcripts.

## Requirements
- **Python 3.10+** *(the installer sets this up for you)*
- **ffmpeg** *(the installer sets this up for you)*
- A native WebView backend (built in on macOS; one small package on Linux)

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

## Opening the app

After installing, there are three ways to open it — pick whichever you like:

| Way | How |
| --- | --- |
| 🖱️ **App icon** | **macOS:** open **Launchpad/Spotlight** → “Simple Schedules Transcribe”. **Linux:** find it in your **application menu**. |
| ⌨️ **Command** | Type **`transcribe`** in any terminal, from any folder. |
| 📂 **From the folder** | Run **`./run.sh`** inside the project folder. |

The app launches **detached** — you can **close the terminal and it keeps running**.

> **macOS note:** the clickable icon works when the app is installed to your
> home folder (the one-line installer does this). macOS Privacy rules block
> apps launched from `~/Documents`, `~/Desktop` or `~/Downloads`, so if you
> keep the project there, use the **`transcribe`** command instead.

## Quick start (from the project folder)

If you already have the folder, one command sets everything up — ffmpeg, a
modern Python if needed, all dependencies into an isolated `.venv`, the global
`transcribe` command and the app icon:

```bash
./install.sh   # first time only
```

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

## Credits

This is a fork of the transcription project by **NTIG Helsingborg** (Skolverket
assignment) — original repository:
<https://github.com/NTIG-Helsingborg/TE4_25-26_Skolverket-transkribering>.
Distributed by **Simple Schedules** with the original authors' permission.

**Simple Schedules** added: macOS & Linux support, a one-command installer,
clickable app icons, a self-hosted (offline / GDPR-clean) UI, and the Simple
Schedules visual identity.

**On licensing:** the upstream project does not carry an open-source license, so
the original authors retain their copyright. Simple Schedules distributes this
fork with their permission; we do not relicense their code. If you want to
reuse or redistribute it, please contact the original authors and Simple
Schedules first.

---
<div align="center">
Built for teams that need trustworthy, local speech-to-text when handling sensitive recordings.<br/>
Maintained by <b>Simple Schedules</b> · original by <b>NTIG Helsingborg</b>.
</div>
