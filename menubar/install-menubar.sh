#!/usr/bin/env bash
#
# Install the transcription status menu-bar app (macOS).
# Installs rumps into the app's venv, wires the launchd agent, and loads it.
# Re-runnable. Uninstall: --uninstall.
#
set -euo pipefail

APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$APPDIR/.venv/bin/python"
VENV_PIP="$APPDIR/.venv/bin/pip"
SCRIPT="$APPDIR/menubar/status_menubar.py"
LOG="$HOME/Library/Logs/transcribe-menubar.log"
LABEL="com.simpleschedules.transcribe-menubar"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
TEMPLATE="$APPDIR/menubar/$LABEL.plist"

if [ "${1:-}" = "--uninstall" ]; then
  launchctl unload "$PLIST_DEST" 2>/dev/null || true
  rm -f "$PLIST_DEST"
  echo "Uninstalled $LABEL (menu-bar icon will disappear)."
  exit 0
fi

if [ ! -x "$VENV_PY" ]; then
  echo "No .venv at $VENV_PY — run ./install.sh in the app first." >&2
  exit 1
fi

echo "Installing rumps into the venv…"
"$VENV_PIP" install --quiet rumps

mkdir -p "$(dirname "$LOG")" "$HOME/Library/LaunchAgents"

esc() { printf '%s' "$1" | sed 's/[&/\]/\\&/g'; }
sed \
  -e "s/__VENV_PY__/$(esc "$VENV_PY")/g" \
  -e "s/__SCRIPT__/$(esc "$SCRIPT")/g" \
  -e "s/__LOG__/$(esc "$LOG")/g" \
  -e "s/__APPDIR__/$(esc "$APPDIR")/g" \
  "$TEMPLATE" > "$PLIST_DEST"

plutil -lint "$PLIST_DEST" >/dev/null

launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "Installed $LABEL — look for 🎙️ in your menu bar."
echo "  🎙️🔴 transcribing · 🎙️🟡 queued · 🎙️ idle"
