#!/usr/bin/env python3
"""
Menu-bar status light for the transcription pipeline.

Glanceable state in the macOS menu bar — a white SF Symbols waveform (like the
native system icons):
  white waveform          idle — nothing going
  red waveform            a transcription is actively running
  orange waveform         files are queued in SS-Incoming, nothing running yet

Decoupled from the watcher on purpose: it only *reads* state (a running
watch_incoming.py process + the incoming/processed folders), so it can never
interfere with a transcription. Runs via rumps; install with install-menubar.sh.
"""

from __future__ import annotations

import sys
import configparser
import subprocess
from pathlib import Path

# The recorder + settings live in the repo root (this file is in menubar/).
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import rumps

try:
    from mac_recorder import Recorder, list_audio_devices
except Exception:  # recording is optional — the status light still works without it
    Recorder = None
    def list_audio_devices():
        return []

SETTINGS_FILE = REPO_ROOT / "settings.ini"

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
        super().__init__("", quit_button=None)
        self._icon_ok = False
        self.status_item = rumps.MenuItem("Idle")
        self.queued_item = rumps.MenuItem("Queued: 0")
        self.done_item = rumps.MenuItem("Completed: 0")

        # Recording controls. Wrapped defensively: if anything here fails, the app
        # degrades to a plain status light rather than crashing (which would make
        # the whole menu-bar icon disappear).
        self._recorder = None
        try:
            if Recorder is not None:
                self._recorder = Recorder(self._load_device_index())
                self.record_item = rumps.MenuItem("● Start recording", callback=self._on_record)
                self.pause_item = rumps.MenuItem("Pause", callback=self._on_pause)
                self.stop_item = rumps.MenuItem("■ Stop & transcribe", callback=self._on_stop)
                self.source_menu = rumps.MenuItem("Recording source")
                self._build_source_menu()
        except Exception:
            self._recorder = None

        menu = []
        if self._recorder is not None:
            menu += [self.record_item, self.pause_item, self.stop_item,
                     self.source_menu, None]
        menu += [
            self.status_item, self.queued_item, self.done_item, None,
            rumps.MenuItem("Open Meet folder", callback=self._open_meet),
            rumps.MenuItem("Open incoming folder", callback=self._open_incoming),
            rumps.MenuItem("View log", callback=self._open_log), None,
            rumps.MenuItem("Quit", callback=lambda _: rumps.quit_application()),
        ]
        self.menu = menu
        self._timer = rumps.Timer(self._refresh, 1)
        self._timer.start()
        self._refresh(None)

    # ---- recording settings + source menu ------------------------------
    def _load_device_index(self) -> int:
        # Explicit saved choice wins.
        try:
            cfg = configparser.ConfigParser()
            if cfg.read(SETTINGS_FILE) and cfg.has_option("recording", "device_index"):
                return cfg.getint("recording", "device_index")
        except Exception:
            pass
        # Otherwise prefer the built-in Mac mic over Continuity (iPhone) mics.
        devices = list_audio_devices()
        for idx, name in devices:
            low = name.lower()
            if "iphone" in low or "ipad" in low or "continuity" in low:
                continue
            if "macbook" in low or "built-in" in low or "microphone" in low:
                return idx
        return devices[0][0] if devices else 0

    def _save_device_index(self, idx: int) -> None:
        try:
            cfg = configparser.ConfigParser()
            cfg.read(SETTINGS_FILE)
            if "recording" not in cfg:
                cfg.add_section("recording")
            cfg.set("recording", "device_index", str(idx))
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                cfg.write(f)
        except Exception:
            pass

    def _build_source_menu(self) -> None:
        # A freshly-created rumps submenu has no underlying NSMenu yet, so clear()
        # would throw — only clear once it's been populated/initialised.
        try:
            self.source_menu.clear()
        except Exception:
            pass
        devices = list_audio_devices()
        current = self._recorder.device_index if self._recorder else 0
        if not devices:
            self.source_menu.add(rumps.MenuItem("(no audio devices found)"))
            return
        for idx, name in devices:
            item = rumps.MenuItem(f"{name}", callback=self._select_device)
            item.state = 1 if idx == current else 0
            item._ss_device_index = idx
            self.source_menu.add(item)

    def _select_device(self, sender) -> None:
        idx = getattr(sender, "_ss_device_index", 0)
        if self._recorder and self._recorder.is_active():
            rumps.alert("Stop the current recording before switching source.")
            return
        if self._recorder:
            self._recorder.device_index = idx
        self._save_device_index(idx)
        self._build_source_menu()

    # ---- recording controls -------------------------------------------
    def _on_record(self, _) -> None:
        r = self._recorder
        if r is None:
            return
        if r.state == "idle":
            r.start()
        elif r.state == "recording":
            r.pause()
        elif r.state == "paused":
            r.resume()
        self._refresh(None)

    def _on_pause(self, _) -> None:
        r = self._recorder
        if r is None:
            return
        if r.state == "recording":
            r.pause()
        elif r.state == "paused":
            r.resume()
        self._refresh(None)

    def _on_stop(self, _) -> None:
        r = self._recorder
        if r is None or not r.is_active():
            return
        dest = r.stop()
        self._refresh(None)
        if dest is not None:
            rumps.notification("Simple Schedules", "Recording saved",
                               f"{dest.name} — transcribing shortly.")
        else:
            rumps.notification("Simple Schedules", "Recording discarded",
                               "No audio was captured (check mic permission).")

    def _button(self):
        item = getattr(self._nsapp, "nsstatusitem", None)
        return item.button() if item is not None else None

    def _apply_icon(self, tint):
        """Native pure-white waveform (like the system menu-bar icons).

        The status-item button reports NSAppearanceNameVibrantLight even in Dark
        mode (macOS treats the bar as light-backed), which renders a template icon
        BLACK — and an explicit white becomes invisible. We force the button to
        DarkAqua so the template renders white, exactly like wifi/battery/etc.
        Idle = white; red = transcribing/recording; orange = queued/paused."""
        try:
            from AppKit import NSImage, NSAppearance, NSColor
            btn = self._button()
            if btn is None:
                return
            if not self._icon_ok:
                img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                    "waveform", "Transcription status")
                if img is None:
                    return
                img.setTemplate_(True)
                btn.setImage_(img)
                self.title = ""              # image carries it — no emoji, ever
                self._icon_ok = True
            # Re-assert the dark appearance on EVERY refresh so the icon can never
            # revert to black — macOS can flip the button back to VibrantLight on
            # sleep/wake, display changes, or menu-bar vibrancy re-evaluation. This
            # runs on the ~1s timer, so any revert self-corrects almost instantly.
            ap = NSAppearance.appearanceNamed_("NSAppearanceNameDarkAqua")
            if ap is not None:
                btn.setAppearance_(ap)       # force white template rendering
            color = {"red": NSColor.systemRedColor(),
                     "orange": NSColor.systemOrangeColor()}.get(tint)
            btn.setContentTintColor_(color)  # None (idle) -> white template
        except Exception:
            pass

    def _refresh(self, _):
        pending = _pending_count()
        rec = self._recorder
        rec_state = rec.state if rec else "idle"

        # Recording takes visual priority over the transcription queue.
        if rec_state == "recording":
            state, tint = f"● Recording {self._fmt(rec.elapsed())}", "red"
        elif rec_state == "paused":
            state, tint = f"❚❚ Paused {self._fmt(rec.elapsed())}", "orange"
        elif _watcher_running():
            state, tint = "Transcribing…", "red"
        elif pending:
            state, tint = f"{pending} queued", "orange"
        else:
            state, tint = "Idle", "idle"  # neutral white on the dark menu bar

        # Keep the record controls' labels in sync with the recorder state.
        if rec is not None:
            self.record_item.title = {
                "idle": "● Start recording",
                "recording": "❚❚ Pause recording",
                "paused": "● Resume recording",
            }[rec_state]
            self.pause_item.set_callback(self._on_pause if rec_state != "idle" else None)
            self.pause_item.title = "Resume" if rec_state == "paused" else "Pause"
            self.stop_item.set_callback(self._on_stop if rec_state != "idle" else None)

        self._apply_icon(tint)

        self.status_item.title = f"Status: {state}"
        self.queued_item.title = f"Queued: {pending}"
        self.done_item.title = f"Completed: {_processed_count()}"

    @staticmethod
    def _fmt(seconds: float) -> str:
        s = int(seconds)
        return f"{s // 60:02d}:{s % 60:02d}"

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
