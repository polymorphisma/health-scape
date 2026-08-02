#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Remove raw dump files older than 30 days to keep VPS storage clean.
# Processed CSVs in output/ are never touched — they are your long-term historical record.
# Safe on fresh deployments — skips silently if raw_dumps/ doesn't exist yet.
if [ -d "$SCRIPT_DIR/raw_dumps" ]; then
    find "$SCRIPT_DIR/raw_dumps" -maxdepth 1 -name "*.json" -mtime +30 -delete
fi

source venv/bin/activate
python -m src.main
