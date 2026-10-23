#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
python3 -m venv .venv
printf 'Ready: no third-party packages to download.\n'
