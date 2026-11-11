#!/usr/bin/env sh
set -eu
# Intentionally bind to loopback. Do not change this to 0.0.0.0 for host execution.
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
