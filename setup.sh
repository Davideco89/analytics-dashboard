#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname -- "$0")"

if ! command -v python3.13 >/dev/null 2>&1; then
    echo "[ERROR] Python 3.13 is required. Install it and retry." >&2
    exit 1
fi

if [ ! -x .venv/bin/python ]; then
    echo "Creating Python 3.13 virtual environment..."
    python3.13 -m venv .venv
fi

if ! .venv/bin/python -c 'import sys; sys.exit(sys.version_info[:2] != (3, 13))'; then
    echo "[ERROR] The existing .venv is not Python 3.13." >&2
    exit 1
fi

if [ ! -f .env ]; then
    cp .env.example .env
fi

echo "Installing Python dependencies..."
.venv/bin/python -m pip install -r requirements.txt

echo "Checking the project environment..."
.venv/bin/python test_setup.py

echo "Running offline Python tests..."
.venv/bin/python -m unittest discover -s tests/python -v

echo "Checking Docker Compose configuration..."
docker compose config --quiet

echo "[OK] Setup checks passed. Build Metabase and run the data refresh as described in README.md."
