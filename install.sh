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

  step "Checking Xcode Command Line Tools (needed to build some deps)"
  if xcode-select -p >/dev/null 2>&1; then ok "Command Line Tools present"
  else
    warn "Installing Command Line Tools — accept the popup, then re-run this script."
    xcode-select --install || true
    die "Waiting on Command Line Tools install. Re-run ./install.sh once it finishes."
  fi

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
  # Base toolchain + audio/native libs some Python deps compile against
  # (webrtcvad -> build-essential/python3-dev, soundfile/librosa -> libsndfile1).
  BASE_PKGS="ffmpeg python3 python3-venv python3-pip python3-dev build-essential libsndfile1"
  # GTK WebView backend for pywebview (python3-gi-cairo is needed by some
  # pywebview versions for the GTK canvas).
  GTK_PKGS="python3-gi python3-gi-cairo gir1.2-gtk-3.0"
  # Try the newer WebKit GI package first, fall back to the older one.
  if ! sudo apt-get install -y $BASE_PKGS $GTK_PKGS gir1.2-webkit2-4.1; then
    warn "webkit2-4.1 unavailable — trying the 4.0 package instead."
    sudo apt-get install -y $BASE_PKGS $GTK_PKGS gir1.2-webkit2-4.0
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
# Upgrade the build frontend so packages that ship only as source (sdists)
# can compile cleanly.
python -m pip install --upgrade pip setuptools wheel >/dev/null
if [ "$OS" = "Linux" ]; then
  # The default PyTorch wheel on Linux pulls ~2.5GB of CUDA libraries. This app
  # runs fine on CPU, so grab the much smaller CPU-only build instead. macOS
  # wheels are already CPU-only, so this is Linux-only.
  info "Installing CPU-only PyTorch (smaller download, no NVIDIA needed)…"
  python -m pip install --index-url https://download.pytorch.org/whl/cpu torch
fi
python -m pip install -r requirements.txt
ok "Python dependencies installed"

step "Verifying the install"
# Non-fatal: a failed check warns but never aborts the icon/command setup below.
python - <<'PY' || warn "Some modules failed to import — the app may still work; see above."
import importlib.util
mods = ["webview", "torch", "transformers", "resemblyzer",
        "scipy", "numpy", "sklearn"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
if missing:
    print("  Missing after install:", ", ".join(missing))
    raise SystemExit(1)
print("  All core modules import OK")
PY

# --- global `transcribe` command --------------------------------------------
step "Installing the global 'transcribe' command"
LAUNCHER="$(pwd)/bin/transcribe"
chmod +x "$LAUNCHER"
LINK=""
if [ "$OS" = "Darwin" ]; then
  # Homebrew's bin is already on PATH and user-writable — no sudo needed.
  BINDIR="$(brew --prefix)/bin"
  ln -sf "$LAUNCHER" "$BINDIR/transcribe" && LINK="$BINDIR/transcribe"
else
  # Linux: /usr/local/bin is on PATH by default (we already have sudo above).
  if sudo ln -sf "$LAUNCHER" /usr/local/bin/transcribe 2>/dev/null; then
    LINK="/usr/local/bin/transcribe"
  else
    mkdir -p "$HOME/.local/bin"
    ln -sf "$LAUNCHER" "$HOME/.local/bin/transcribe"
    LINK="$HOME/.local/bin/transcribe"
    # Make sure ~/.local/bin is on PATH for future shells.
    for RC in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
      [ -f "$RC" ] || continue
      grep -q '.local/bin' "$RC" 2>/dev/null && continue
      printf '\n# Added by Simple Schedules Transcribe installer\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$RC"
    done
    warn "Added ~/.local/bin to your PATH — open a new terminal for 'transcribe' to work."
  fi
fi
ok "Global command installed: $LINK"

# --- clickable app icon (no terminal needed) --------------------------------
step "Creating a clickable app icon"
PROJECT="$(pwd)"
if [ "$OS" = "Darwin" ]; then
  APP="$HOME/Applications/Simple Schedules Transcribe.app"
  mkdir -p "$HOME/Applications"
  rm -rf "$APP"
  mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
  [ -f assets/icon.icns ] && cp assets/icon.icns "$APP/Contents/Resources/icon.icns"
  cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Simple Schedules Transcribe</string>
  <key>CFBundleDisplayName</key><string>Simple Schedules Transcribe</string>
  <key>CFBundleIdentifier</key><string>com.simpleschedules.transcribe</string>
  <key>CFBundleVersion</key><string>1.0.0</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundleIconFile</key><string>icon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>10.13</string>
</dict></plist>
PLIST
  cat > "$APP/Contents/MacOS/launcher" <<LAUNCH
#!/bin/bash
exec "$PROJECT/bin/transcribe"
LAUNCH
  chmod +x "$APP/Contents/MacOS/launcher"
  touch "$APP"
  ok "Added to ~/Applications — find 'Simple Schedules Transcribe' in Launchpad/Spotlight"
  # macOS blocks Finder-launched apps from running code inside Documents/Desktop/
  # Downloads. Warn if we're in one of those so the clickable icon isn't a
  # silent no-op (the 'transcribe' command still works from a terminal).
  case "$PROJECT/" in
    "$HOME/Documents/"*|"$HOME/Desktop/"*|"$HOME/Downloads/"*)
      warn "This folder is inside a macOS-protected location."
      warn "The clickable icon may not work from here (Privacy/TCC restriction)."
      warn "Fixes: use the 'transcribe' command, or reinstall to your home folder"
      warn "(the one-line installer clones to ~/Simple-Schedules-Transcribe, which works)."
      ;;
  esac
else
  APPS="$HOME/.local/share/applications"
  mkdir -p "$APPS"
  cat > "$APPS/simple-schedules-transcribe.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Simple Schedules Transcribe
Comment=Local, offline speech-to-text transcription
Exec=$PROJECT/bin/transcribe
Icon=$PROJECT/assets/icon.svg
Terminal=false
Categories=AudioVideo;Utility;
DESKTOP
  chmod +x "$APPS/simple-schedules-transcribe.desktop"
  update-desktop-database "$APPS" >/dev/null 2>&1 || true
  ok "Added to your menu — search 'Transcribe' in the application menu"
fi

printf '\n%s%s✓ Installation complete.%s\n' "$BOLD" "$GRN" "$RST"
printf '  Three ways to open it:\n'
printf '   1. Type %stranscribe%s in any terminal.\n' "$BOLD" "$RST"
if [ "$OS" = "Darwin" ]; then
  printf '   2. Open it from %sLaunchpad / Spotlight%s (search "Transcribe").\n' "$BOLD" "$RST"
else
  printf '   2. Open it from your %sapplication menu%s (search "Transcribe").\n' "$BOLD" "$RST"
fi
printf '   3. Run %s./run.sh%s from this folder.\n' "$BOLD" "$RST"
printf '  %s(The app runs detached — you can close the terminal and it keeps going.)%s\n\n' "$DIM" "$RST"
