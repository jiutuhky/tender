#!/usr/bin/env bash
# Hagent sandbox entrypoint. Keeps the container alive so `docker exec`
# can dispatch each LLM tool call.
set -euo pipefail
mkdir -p /workspace
exec tail -f /dev/null
