#!/usr/bin/env bash
# Double-clickable macOS launcher. Finder runs this in Terminal.
# First run installs everything; later runs just start the app.
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -d .venv ]; then
  ./install.sh || { echo "Install failed — see the messages above."; read -r -p "Press Return to close…"; exit 1; }
fi
./run.sh
