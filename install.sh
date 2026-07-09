#!/usr/bin/env bash
#
# Simple Schedules Transcribe — one-shot installer
# Works on macOS (Apple Silicon & Intel) and Linux Mint / Ubuntu / Debian.
#
# It installs the system tools the app needs (ffmpeg, a modern Python, and on
# Linux the WebView backend), then builds an isolated .venv with all Python
# dependencies. Safe to re-run — every step is idempotent.
#
#   ./install.sh
#
set -euo pipefail

# --- pretty output -----------------------------------------------------------
BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GRN=$'\033[32m'
BLU=$'\033[34m'; YEL=$'\033[33m'; RST=$'\033[0m'
step() { printf '\n%s==>%s %s%s%s\n' "$BLU" "$RST" "$BOLD" "$1" "$RST"; }
ok()   { printf '%s  ✓%s %s\n' "$GRN" "$RST" "$1"; }
info() { printf '%s  •%s %s\n' "$DIM" "$RST" "$1"; }
warn() { printf '%s  !%s %s\n' "$YEL" "$RST" "$1"; }
die()  { printf '%s  ✗ %s%s\n' "$RED" "$1" "$RST" >&2; exit 1; }

# Always operate from the project directory (where this script lives).
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

printf '%s\n' "${BOLD}Simple Schedules Transcribe — installer${RST}"
info "Project: $(pwd)"

# --- pick a Python >= 3.10 ---------------------------------------------------
find_python() {
  local c
  for c in python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1; then
      if "$c" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,10) else 1)' 2>/dev/null; then
        echo "$c"; return 0
      fi
    fi
  done
  return 1
}

OS="$(uname -s)"

# =============================================================================
# macOS
# =============================================================================
if [ "$OS" = "Darwin" ]; then
  step "macOS detected — checking Homebrew"
  if ! command -v brew >/dev/null 2>&1; then
    warn "Homebrew is not installed. Installing it now (you may be asked for your password)…"
    NONINTERACTIVE=1 /bin/bash -c \
      "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
      || die "Homebrew install failed."
    # Make brew available on this shell for both Apple Silicon and Intel layouts.
    if [ -x /opt/homebrew/bin/brew ]; then eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x /usr/local/bin/brew ]; then eval "$(/usr/local/bin/brew shellenv)"; fi
  fi
  command -v brew >/dev/null 2>&1 || die "brew still not on PATH — open a new terminal and re-run."
  ok "Homebrew ready ($(brew --version | head -1))"

  step "Installing ffmpeg"
  if command -v ffmpeg >/dev/null 2>&1; then ok "ffmpeg already installed"
  else brew install ffmpeg && ok "ffmpeg installed"; fi

  step "Ensuring Python 3.10+"
  if PY="$(find_python)"; then ok "Using $PY ($("$PY" --version))"
  else
    info "No Python 3.10+ found — installing python@3.12 via Homebrew…"
    brew install python@3.12
    eval "$(brew shellenv)"
    PY="$(find_python)" || die "Could not locate a Python 3.10+ after install."
    ok "Using $PY ($("$PY" --version))"
  fi
  VENV_ARGS=""

# =============================================================================
# Linux (apt-based: Mint / Ubuntu / Debian)
# =============================================================================
elif [ "$OS" = "Linux" ]; then
  command -v apt-get >/dev/null 2>&1 || \
    die "This installer supports apt-based Linux (Mint/Ubuntu/Debian). Install ffmpeg, python3-venv and the GTK WebKit packages manually, then run ./run.sh."

  step "Linux detected — installing system packages (needs sudo)"
  sudo apt-get update -y
  # Try the newer WebKit GI package first, fall back to the older one.
  if ! sudo apt-get install -y ffmpeg python3 python3-venv python3-pip \
        python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1; then
    warn "webkit2-4.1 unavailable — trying the 4.0 package instead."
    sudo apt-get install -y ffmpeg python3 python3-venv python3-pip \
        python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.0
  fi
  ok "System packages installed"

  step "Ensuring Python 3.10+"
  PY="$(find_python)" || die "Python 3.10+ not found. Install a newer python3 and re-run."
  ok "Using $PY ($("$PY" --version))"
  # The GTK WebView backend lives in system site-packages (python3-gi), so the
  # venv must be able to see it.
  VENV_ARGS="--system-site-packages"

else
  die "Unsupported OS: $OS. On Windows, see README.md for manual steps."
fi

# =============================================================================
# Shared: virtual environment + Python dependencies
# =============================================================================
step "Creating virtual environment (.venv)"
if [ ! -d .venv ]; then
  # shellcheck disable=SC2086
  "$PY" -m venv $VENV_ARGS .venv || die "Failed to create .venv"
  ok ".venv created"
else
  ok ".venv already exists (reusing)"
fi

step "Installing Python dependencies (this can take a while — torch is large)"
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt

printf '\n%s%s✓ Installation complete.%s\n' "$BOLD" "$GRN" "$RST"
printf '  Launch it with:  %s./run.sh%s\n' "$BOLD" "$RST"
printf '  (on macOS you can also double-click %sLaunch Simple Schedules Transcribe.command%s in Finder)\n\n' "$BOLD" "$RST"
