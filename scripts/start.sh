#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then sh scripts/setup.sh; fi
exec .venv/bin/python run.py "$@"
