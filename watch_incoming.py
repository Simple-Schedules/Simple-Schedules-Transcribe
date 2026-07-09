#!/usr/bin/env python3
"""
Headless watcher: transcribe audio dropped into an incoming folder, hands-off.

Flow (see the launchd agent that drives this):
  iPhone Shortcut  ->  iCloud Drive / SS-Incoming  ->  (this script)
     transcribe (KB-Whisper + diarization)  ->  save_result  ->  meet_export
  ->  the transcript lands in Simple-Schedules-Meet (committed + pushed).

Design:
- Reuses the SAME engine the GUI uses (transcriber.py) — no duplicate logic.
- iCloud-aware: forces a not-yet-downloaded ('.icloud' placeholder / dataless)
  file to download, and waits until its size is stable before transcribing.
- Safe to run concurrently: a file lock means overlapping launchd triggers
  (WatchPaths + the interval poll) never double-process.
- Processed files move to processed/; failures move to failed/ with a note —
  nothing is silently dropped and nothing is reprocessed forever.

Config via env:
  SS_INCOMING_DIR      default ~/Library/Mobile Documents/com~apple~CloudDocs/SS-Incoming
  SS_TRANSCRIBE_LANG   'sv' (default) | 'en'
  SS_TRANSCRIBE_MODEL  'tiny'|'small'|'medium'|'large' (default 'large')
"""

from __future__ import annotations

import os
import sys
import time
import fcntl
import shutil
import subprocess
from pathlib import Path

# Audio extensions the engine supports (mirrored so detection needs no heavy import).
AUDIO_EXTS = {
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v",
    ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma", ".aiff",
}


def incoming_dir() -> Path:
    override = os.environ.get("SS_INCOMING_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "SS-Incoming"


def _is_icloud_placeholder(p: Path) -> bool:
    return p.name.startswith(".") and p.name.endswith(".icloud")


def _materialized_name(placeholder: Path) -> Path:
    # ".v3-sync.m4a.icloud" -> "v3-sync.m4a"
    return placeholder.with_name(placeholder.name[1:-len(".icloud")])


def _force_download(p: Path) -> None:
    """Ask iCloud to download a dataless file/placeholder; ignore if unavailable."""
    try:
        subprocess.run(["brctl", "download", str(p)], capture_output=True, timeout=30)
    except Exception:
        pass


def _is_materialized(p: Path) -> bool:
    """
    True only when the file's real bytes are on disk — not just an iCloud stub.
    A dataless iCloud file reports its full logical st_size but allocates ~0
    blocks; feeding that to ffmpeg fails. st_blocks (512-byte units) is the
    honest signal that the content actually downloaded.
    """
    try:
        st = p.stat()
    except OSError:
        return False
    return st.st_size > 0 and st.st_blocks * 512 >= st.st_size * 0.9


def _wait_until_ready(p: Path, timeout: float = 600.0) -> bool:
    """Wait until the file is fully DOWNLOADED (real bytes on disk) and stable."""
    deadline = time.time() + timeout
    last_size, stable = -1, 0
    while time.time() < deadline:
        if p.exists():
            _force_download(p)  # nudge iCloud to materialize the bytes each pass
            try:
                size = p.stat().st_size
            except OSError:
                size = -1
            # Ready = real bytes present (not a stub) AND size held steady.
            if size > 0 and _is_materialized(p) and size == last_size:
                stable += 1
                if stable >= 2:
                    return True
            else:
                stable = 0
            last_size = size
        else:
            _force_download(p)
        time.sleep(2)
    return False


def pending_files(base: Path) -> list[Path]:
    """Top-level audio files ready to process (materialize iCloud placeholders first)."""
    if not base.is_dir():
        return []
    ready: list[Path] = []
    for entry in sorted(base.iterdir()):
        if entry.name in ("processed", "failed") or entry.name.startswith("."):
            # An iCloud placeholder is hidden — surface the real file it stands for.
            if _is_icloud_placeholder(entry):
                _force_download(entry)
            continue
        if entry.is_file() and entry.suffix.lower() in AUDIO_EXTS:
            ready.append(entry)
    return ready


def _acquire_lock(base: Path):
    """Single-runner lock; returns the open handle or None if another run holds it."""
    lock_path = base / ".watch.lock"
    fh = open(lock_path, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError:
        fh.close()
        return None


def _process_one(audio: Path) -> None:
    """Transcribe a single file end-to-end and export it to the Meet repo."""
    # Heavy imports happen only when there's real work — keeps detection cheap.
    from transcriber import TranscriptionEngine, TranscriptionJob, Language, ModelSize
    from meet_export import export_to_meet
    from slack_export import post_to_slack
    from meeting_summary import enrich_json

    lang = Language.ENGLISH if os.environ.get("SS_TRANSCRIBE_LANG", "sv").lower() == "en" else Language.SWEDISH
    model = {
        "tiny": ModelSize.TINY, "small": ModelSize.SMALL,
        "medium": ModelSize.MEDIUM, "large": ModelSize.LARGE,
    }.get(os.environ.get("SS_TRANSCRIBE_MODEL", "large").lower(), ModelSize.LARGE)

    print(f"[watch] transcribing {audio.name} (lang={lang.value}, model={model.name})", flush=True)
    engine = TranscriptionEngine()
    result = engine.transcribe(TranscriptionJob(file_path=str(audio), language=lang, model_size=model))
    if result.error:
        raise RuntimeError(result.error)

    # Fully autonomous: nothing is typed on the phone, so give the note a distinct,
    # sortable title from the meeting's own timestamp (the title is cosmetic).
    if result.date and result.time:
        result.title = f"Möte {result.date} {result.time}"

    json_path = engine.save_result(result)      # writes ~/Documents/Simple Schedules Transcribe/<Title>/
    enrich_json(json_path)                       # fill Summary/Decisions/Actions via Claude Code (subscription)
    export_to_meet(json_path)                    # renders md + commits + pushes to Meet
    post_to_slack(json_path)                     # shares the md into Slack (#möte); no-op without a token
    print(f"[watch] done: {audio.name}", flush=True)


def run(dry_run: bool = False) -> int:
    base = incoming_dir()
    base.mkdir(parents=True, exist_ok=True)
    (base / "processed").mkdir(exist_ok=True)
    (base / "failed").mkdir(exist_ok=True)

    files = pending_files(base)
    if not files:
        print("[watch] nothing pending.", flush=True)
        return 0

    if dry_run:
        print(f"[watch] DRY-RUN — {len(files)} file(s) would be processed:", flush=True)
        for f in files:
            print(f"  - {f.name}", flush=True)
        return 0

    lock = _acquire_lock(base)
    if lock is None:
        print("[watch] another run is active — exiting.", flush=True)
        return 0

    try:
        for audio in files:
            if not _wait_until_ready(audio):
                print(f"[watch] {audio.name} never finished downloading — leaving for next run.", flush=True)
                continue
            try:
                _process_one(audio)
                shutil.move(str(audio), str(base / "processed" / audio.name))
            except Exception as e:
                print(f"[watch] FAILED {audio.name}: {e}", flush=True)
                dest = base / "failed" / audio.name
                try:
                    shutil.move(str(audio), str(dest))
                    (base / "failed" / f"{audio.name}.error.txt").write_text(str(e), encoding="utf-8")
                except Exception:
                    pass
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
    return 0


if __name__ == "__main__":
    sys.exit(run(dry_run="--dry-run" in sys.argv))
