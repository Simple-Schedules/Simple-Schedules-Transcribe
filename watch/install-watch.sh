#!/usr/bin/env bash
#
# Install the iPhone -> iCloud -> transcribe -> Meet background watcher (macOS).
# Fills the plist template with real paths, loads it via launchd, and creates
# the incoming folder. Re-runnable (reloads cleanly). Uninstall: --uninstall.
#
set -euo pipefail

APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"       # the Transcribe repo
VENV_PY="$APPDIR/.venv/bin/python"
SCRIPT="$APPDIR/watch_incoming.py"
INCOMING="${SS_INCOMING_DIR:-$HOME/Library/Mobile Documents/com~apple~CloudDocs/SS-Incoming}"
LOG="$HOME/Library/Logs/transcribe-watch.log"
LABEL="com.simpleschedules.transcribe-watch"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
TEMPLATE="$APPDIR/watch/$LABEL.plist"

if [ "${1:-}" = "--uninstall" ]; then
  launchctl unload "$PLIST_DEST" 2>/dev/null || true
  rm -f "$PLIST_DEST"
  echo "Uninstalled $LABEL (the incoming folder + transcripts are left untouched)."
  exit 0
fi

if [ ! -x "$VENV_PY" ]; then
  echo "No .venv found at $VENV_PY — run ./install.sh in the app first." >&2
  exit 1
fi

mkdir -p "$INCOMING" "$(dirname "$LOG")" "$HOME/Library/LaunchAgents"

# Materialize the template with escaped paths.
esc() { printf '%s' "$1" | sed 's/[&/\]/\\&/g'; }
sed \
  -e "s/__VENV_PY__/$(esc "$VENV_PY")/g" \
  -e "s/__SCRIPT__/$(esc "$SCRIPT")/g" \
  -e "s/__INCOMING__/$(esc "$INCOMING")/g" \
  -e "s/__LOG__/$(esc "$LOG")/g" \
  -e "s/__APPDIR__/$(esc "$APPDIR")/g" \
  "$TEMPLATE" > "$PLIST_DEST"

plutil -lint "$PLIST_DEST" >/dev/null

launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "Installed $LABEL"
echo "  incoming : $INCOMING"
echo "  log      : $LOG"
echo "  model    : Swedish / large   (edit EnvironmentVariables in the plist to change)"
echo
echo "Drop an audio file into the incoming folder to test, then watch the log:"
echo "  tail -f \"$LOG\""
