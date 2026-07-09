#!/usr/bin/env python3
"""
Menu-bar status light for the transcription pipeline.

Glanceable state in the macOS menu bar:
  🎙️🔴  a transcription is actively running
  🎙️🟡  files are queued in SS-Incoming, nothing running yet
  🎙️     idle — nothing going

Decoupled from the watcher on purpose: it only *reads* state (a running
watch_incoming.py process + the incoming/processed folders), so it can never
interfere with a transcription. Runs via rumps; install with install-menubar.sh.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import rumps

try:  # hide the Dock icon — this is a menu-bar-only app
    from AppKit import NSApplication
    NSApplication.sharedApplication().setActivationPolicy_(1)  # .accessory
except Exception:
    pass

INCOMING = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "SS-Incoming"
MEET = Path.home() / "Documents" / "SS" / "Simple-Schedules-Meet"
LOG = Path.home() / "Library" / "Logs" / "transcribe-watch.log"
AUDIO_EXTS = {
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v",
    ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma", ".aiff",
}


def _watcher_running() -> bool:
    """A watch_incoming.py process alive == something is actively transcribing."""
    try:
        r = subprocess.run(["pgrep", "-f", "watch_incoming.py"],
                           capture_output=True, text=True, timeout=5)
        return bool(r.stdout.strip())
    except Exception:
        return False


def _pending_count() -> int:
    if not INCOMING.is_dir():
        return 0
    return sum(1 for p in INCOMING.iterdir()
               if p.is_file() and p.suffix.lower() in AUDIO_EXTS)


def _processed_count() -> int:
    d = INCOMING / "processed"
    return len(list(d.glob("*"))) if d.is_dir() else 0


class StatusApp(rumps.App):
    def __init__(self):
        super().__init__("🎙️", quit_button=None)
        self._icon_ok = False
        self.status_item = rumps.MenuItem("Idle")
        self.queued_item = rumps.MenuItem("Queued: 0")
        self.done_item = rumps.MenuItem("Completed: 0")
        self.menu = [
            self.status_item, self.queued_item, self.done_item, None,
            rumps.MenuItem("Open Meet folder", callback=self._open_meet),
            rumps.MenuItem("Open incoming folder", callback=self._open_incoming),
            rumps.MenuItem("View log", callback=self._open_log), None,
            rumps.MenuItem("Quit", callback=lambda _: rumps.quit_application()),
        ]
        self._timer = rumps.Timer(self._refresh, 3)
        self._timer.start()
        self._refresh(None)

    def _button(self):
        item = getattr(self._nsapp, "nsstatusitem", None)
        return item.button() if item is not None else None

    def _apply_icon_once(self) -> bool:
        """Set the menu-bar image to the SF Symbols 'waveform' glyph (Voice-Memos look)."""
        if self._icon_ok:
            return True
        try:
            from AppKit import NSImage
            btn = self._button()
            if btn is None:
                return False
            img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                "waveform", "Transcription status")
            if img is None:
                return False
            img.setTemplate_(True)        # adapts to light/dark menu bar
            btn.setImage_(img)
            self.title = ""               # icon carries it — no emoji
            self._icon_ok = True
            return True
        except Exception:
            return False

    def _tint(self, which):
        """Tint the waveform: red = transcribing, orange = queued, none = idle."""
        try:
            from AppKit import NSColor
            btn = self._button()
            if btn is None:
                return
            color = {"red": NSColor.systemRedColor(),
                     "orange": NSColor.systemOrangeColor()}.get(which)
            btn.setContentTintColor_(color)  # None resets to default menu-bar colour
        except Exception:
            pass

    def _refresh(self, _):
        pending = _pending_count()
        if _watcher_running():
            state, tint = "Transcribing…", "red"
        elif pending:
            state, tint = f"{pending} queued", "orange"
        else:
            state, tint = "Idle", None

        if self._apply_icon_once():
            self._tint(tint)
        else:  # fallback if SF Symbols unavailable — a waveform-ish glyph
            self.title = {"red": "∿ rec", "orange": "∿ ·"}.get(tint or "", "∿")

        self.status_item.title = f"Status: {state}"
        self.queued_item.title = f"Queued: {pending}"
        self.done_item.title = f"Completed: {_processed_count()}"

    def _open_meet(self, _):
        subprocess.run(["open", str(MEET)])

    def _open_incoming(self, _):
        INCOMING.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(INCOMING)])

    def _open_log(self, _):
        if LOG.exists():
            subprocess.run(["open", str(LOG)])


if __name__ == "__main__":
    StatusApp().run()
