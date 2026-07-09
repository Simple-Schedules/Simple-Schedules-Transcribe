#!/usr/bin/env bash
#
# Simple Schedules Transcribe — launcher
# Activates the .venv created by install.sh and starts the app.
#
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d .venv ]; then
  printf '\033[31mNo .venv found.\033[0m Run the installer first:\n\n    ./install.sh\n\n' >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate
exec python main.py
