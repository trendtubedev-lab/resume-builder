#!/bin/bash
# Double-click on macOS, or run ./start.command in a terminal.
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "First-time setup: creating virtual environment..."
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi

if [ ! -f ".env" ]; then
  echo ""
  echo "No .env file found. Copy .env.example to .env and add your Anthropic API key."
  echo "  cp .env.example .env"
  echo ""
fi

echo "Starting TailorCV at http://localhost:8000  (press Ctrl+C to stop)"
.venv/bin/python -m app.main
