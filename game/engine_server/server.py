"""The MPC engine: a small HTTP server that runs inside the acados Docker image.

The game (on the host) talks to it on http://127.0.0.1:8000. Only the Python
standard library is used, so it runs in the course image without extra installs.

Endpoints (keep in sync with game/controlquest/engine/protocol.py):
    GET  /health  -> {"status": "ok", "version": ..., "protocol": 1, "acados": bool}
    POST /run     -> RunResult JSON. Not implemented yet: answers 501.

Run (inside the container):  python server.py --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "0.1.0"
PROTOCOL_VERSION = 1
MAX_BODY_BYTES = 1_000_000


def acados_available() -> bool:
    return importlib.util.find_spec("acados_template") is not None


class EngineHandler(BaseHTTPRequestHandler):
    server_version = f"ControlQuestEngine/{VERSION}"

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "version": VERSION,
                                  "protocol": PROTOCOL_VERSION, "acados": acados_available()})
        else:
            self._send_json(404, {"error": f"unknown endpoint {self.path}"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/run":
            self._send_json(404, {"error": f"unknown endpoint {self.path}"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            self._send_json(413, {"error": "request too large"})
            return
        try:
            request = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._send_json(400, {"error": "request body is not valid JSON"})
            return
        # TODO: simulate the level with the MPC and return a RunResult (PRD 9.4).
        self._send_json(501, {"error": "Running levels is not implemented in the engine yet.",
                              "level_id": request.get("level_id")})

    def log_message(self, fmt: str, *args) -> None:
        print(f"[engine] {self.address_string()} {fmt % args}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="0.0.0.0", help="0.0.0.0 inside Docker")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), EngineHandler)
    print(f"[engine] ControlQuest MPC engine {VERSION} on {args.host}:{args.port} "
          f"(acados available: {acados_available()})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
