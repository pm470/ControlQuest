#!/usr/bin/env bash
# Start the ControlQuest MPC engine in Docker (macOS / Linux / Git Bash).
#   ./game/engine_server/start_engine.sh
# Override the image with:  CONTROLQUEST_IMAGE=my-image ./start_engine.sh
# Stop it with Ctrl+C.
set -euo pipefail

IMAGE="${CONTROLQUEST_IMAGE:-vsc-mpcrl26-exercises-94d9982245bae36f409cb410a37b514aafe63fa52604de9d9dc9f0c9c94c729a}"
PORT="${CONTROLQUEST_PORT:-8000}"

# repository root = two folders above this script; mounted at /workspace
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if command -v cygpath >/dev/null 2>&1; then  # Git Bash on Windows needs a Windows path
  REPO="$(cygpath -w "$REPO")"
  export MSYS_NO_PATHCONV=1
fi

echo "Starting MPC engine from image $IMAGE on http://127.0.0.1:$PORT"
docker run --rm -it -p "127.0.0.1:${PORT}:8000" -v "${REPO}:/workspace" \
  -w /workspace/game/engine_server "$IMAGE" python server.py --host 0.0.0.0 --port 8000
