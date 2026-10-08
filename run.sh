#!/bin/zsh
# Start the Malaysia Healthcare Monitor at http://localhost:8050
cd "${0:A:h}"
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
open "http://localhost:8050" 2>/dev/null &
exec .venv/bin/python server.py
