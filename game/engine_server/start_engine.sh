#!/usr/bin/env bash
# Start the ControlQuest MPC engine in Docker (macOS / Linux / Git Bash).
#   ./game/engine_server/start_engine.sh
# The course image is found automatically: VS Code names it vsc-mpcrl26-exercises-<hash>,
# and the hash differs on every computer, so it must NOT be hard-coded here.
# Override with:  CONTROLQUEST_IMAGE=my-image ./start_engine.sh
# Stop it with Ctrl+C.
set -euo pipefail

IMAGE="${CONTROLQUEST_IMAGE:-}"
if [ -z "$IMAGE" ]; then  # newest local image whose name starts with vsc-mpcrl26-exercises-
  IMAGE="$(docker images --format '{{.Repository}}' | grep '^vsc-mpcrl26-exercises-' | head -n 1 || true)"
fi
if [ -z "$IMAGE" ]; then
  echo "No course Docker image found (vsc-mpcrl26-exercises-...)." >&2
  echo "Build it by opening the course repository mpcrl26-exercises in its VS Code Dev Container," >&2
  echo "or set the image name yourself:  CONTROLQUEST_IMAGE=<image> ./start_engine.sh  (see: docker images)" >&2
  exit 1
fi
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
