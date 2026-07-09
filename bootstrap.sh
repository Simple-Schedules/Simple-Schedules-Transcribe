#!/usr/bin/env bash
#
# One-line installer for Simple Schedules Transcribe.
# Downloads the app and runs the full setup. Works on macOS and Linux Mint.
#
#   curl -fsSL https://raw.githubusercontent.com/Simple-Schedules/Simple-Schedules-Transcribe/main/bootstrap.sh | bash
#
set -euo pipefail

REPO="https://github.com/Simple-Schedules/Simple-Schedules-Transcribe.git"
DEST="${1:-$HOME/Simple-Schedules-Transcribe}"
OS="$(uname -s)"

echo "Simple Schedules Transcribe — downloading to $DEST"

# --- make sure git is available ---------------------------------------------
if ! command -v git >/dev/null 2>&1; then
  if [ "$OS" = "Linux" ] && command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y && sudo apt-get install -y git
  elif [ "$OS" = "Darwin" ]; then
    echo "You need Apple's Command Line Tools first. A popup will appear —"
    echo "click Install, wait for it to finish, then run this command again."
    xcode-select --install || true
    exit 1
  else
    echo "Please install git, then re-run this command." >&2
    exit 1
  fi
fi

# --- download (or update) ----------------------------------------------------
if [ -d "$DEST/.git" ]; then
  echo "Already downloaded — updating to the latest version…"
  git -C "$DEST" pull --ff-only
else
  git clone --depth 1 "$REPO" "$DEST"
fi

# --- install -----------------------------------------------------------------
cd "$DEST"
exec ./install.sh
