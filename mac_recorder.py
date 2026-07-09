"""
Simple Mac audio recorder for the menu-bar app.

Records from an avfoundation audio device via ffmpeg, with real pause/resume:
each record span is its own segment file, and stop() concatenates them into one
.m4a — so pausing leaves no silent gap. The finished file is dropped into
SS-Incoming, where the existing watcher transcribes it (→ Meet + Slack).

Why segments instead of pausing ffmpeg: you can't cleanly pause a live
avfoundation capture; SIGSTOP would freeze the process but skew timestamps.
Starting a fresh segment on resume is glitch-free and trivially concatenable.

Device permission: the first capture triggers macOS's microphone-access prompt
for whatever process ffmpeg is launched from. If recording produces no data,
grant mic access to the menu-bar app (System Settings > Privacy > Microphone).
"""

from __future__ import annotations

import os
import re
import time
import shutil
import tempfile
import subprocess
from pathlib import Path


def _ffmpeg() -> str:
    """Resolve ffmpeg the same way the transcriber does (GUI launches lack PATH)."""
    try:
        from transcriber import AudioConverter
        return AudioConverter.get_binary_path("ffmpeg")
    except Exception:
        return shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


def incoming_dir() -> Path:
    override = os.environ.get("SS_INCOMING_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "SS-Incoming"


def list_audio_devices() -> list[tuple[int, str]]:
    """Return [(index, name)] of avfoundation audio input devices."""
    try:
        proc = subprocess.run(
            [_ffmpeg(), "-hide_banner", "-f", "avfoundation",
             "-list_devices", "true", "-i", ""],
            capture_output=True, text=True, timeout=15,
        )
        out = proc.stderr
    except Exception:
        return []
    devices: list[tuple[int, str]] = []
    in_audio = False
    for line in out.splitlines():
        if "AVFoundation audio devices" in line:
            in_audio = True
            continue
        if "AVFoundation video devices" in line:
            in_audio = False
            continue
        m = re.search(r"\[(\d+)\]\s+(.*)$", line)
        if in_audio and m:
            devices.append((int(m.group(1)), m.group(2).strip()))
    return devices


class Recorder:
    """Start / pause / resume / stop an audio recording made of segments."""

    def __init__(self, device_index: int = 0):
        self.device_index = device_index
        self._proc: subprocess.Popen | None = None
        self._segments: list[Path] = []
        self._tmpdir: Path | None = None
        self._state = "idle"          # idle | recording | paused
        self._started_at: float | None = None
        self._paused_accum = 0.0
        self._pause_started: float | None = None

    # ---- state helpers -------------------------------------------------
    @property
    def state(self) -> str:
        return self._state

    def is_active(self) -> bool:
        return self._state in ("recording", "paused")

    def elapsed(self) -> float:
        """Seconds of actual recorded audio (excludes paused time)."""
        if self._started_at is None:
            return 0.0
        now = time.time()
        paused = self._paused_accum
        if self._state == "paused" and self._pause_started is not None:
            paused += now - self._pause_started
        return max(0.0, now - self._started_at - paused)

    # ---- controls ------------------------------------------------------
    def start(self) -> None:
        if self._state != "idle":
            return
        self._tmpdir = Path(tempfile.mkdtemp(prefix="ss-rec-"))
        self._segments = []
        self._paused_accum = 0.0
        self._pause_started = None
        self._started_at = time.time()
        self._start_segment()
        self._state = "recording"

    def pause(self) -> None:
        if self._state != "recording":
            return
        self._stop_segment()
        self._pause_started = time.time()
        self._state = "paused"

    def resume(self) -> None:
        if self._state != "paused":
            return
        if self._pause_started is not None:
            self._paused_accum += time.time() - self._pause_started
            self._pause_started = None
        self._start_segment()
        self._state = "recording"

    def stop(self) -> Path | None:
        """Finish, concatenate segments, drop the file in SS-Incoming. Returns path."""
        if self._state == "idle":
            return None
        if self._state == "recording":
            self._stop_segment()
        self._state = "idle"

        segments = [s for s in self._segments if s.exists() and s.stat().st_size > 0]
        if not segments:
            self._cleanup()
            return None

        dest_dir = incoming_dir()
        dest_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d kl. %H.%M.%S")
        dest = dest_dir / f"Inspelning {stamp}.m4a"

        try:
            if len(segments) == 1:
                shutil.move(str(segments[0]), str(dest))
            else:
                self._concat(segments, dest)
        finally:
            self._cleanup()
        return dest if dest.exists() else None

    def cancel(self) -> None:
        """Abort without saving."""
        if self._state == "recording":
            self._stop_segment()
        self._state = "idle"
        self._cleanup()

    # ---- internals -----------------------------------------------------
    def _start_segment(self) -> None:
        assert self._tmpdir is not None
        seg = self._tmpdir / f"seg-{len(self._segments):03d}.m4a"
        self._segments.append(seg)
        # ":N" = no video, audio device N. 16k mono aac is exactly what Whisper
        # wants and keeps files tiny.
        self._proc = subprocess.Popen(
            [_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
             "-f", "avfoundation", "-i", f":{self.device_index}",
             "-ac", "1", "-ar", "16000", "-c:a", "aac", str(seg)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def _stop_segment(self) -> None:
        p = self._proc
        self._proc = None
        if p is None:
            return
        try:
            # 'q' tells ffmpeg to finalize the file cleanly (proper moov atom).
            if p.stdin:
                try:
                    p.stdin.write(b"q")
                    p.stdin.flush()
                except Exception:
                    pass
            p.wait(timeout=8)
        except Exception:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

    def _concat(self, segments: list[Path], dest: Path) -> None:
        assert self._tmpdir is not None
        listfile = self._tmpdir / "concat.txt"
        listfile.write_text(
            "".join(f"file '{s}'\n" for s in segments), encoding="utf-8"
        )
        subprocess.run(
            [_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
             "-f", "concat", "-safe", "0", "-i", str(listfile),
             "-c", "copy", str(dest)],
            check=True, timeout=120,
        )

    def _cleanup(self) -> None:
        if self._tmpdir and self._tmpdir.exists():
            shutil.rmtree(self._tmpdir, ignore_errors=True)
        self._tmpdir = None
        self._segments = []
        self._started_at = None
