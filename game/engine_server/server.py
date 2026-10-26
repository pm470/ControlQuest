"""The MPC engine: a small HTTP server that runs inside the acados Docker image.

The game (on the host) talks to it on http://127.0.0.1:8000. This file only
translates HTTP <-> Python; the work happens in runner.py (levels) and mpc/ (acados).

Endpoints (keep in sync with game/controlquest/engine/protocol.py):
    GET  /health  -> {"status": "ok", "version": ..., "protocol": 1, "acados": bool,
                      "levels": [playable level ids]}
    POST /run     {"level_id": ..., "knobs": {...}, "waypoints": [[x, y], ...] (optional)}
                  -> RunResult JSON

Run (inside the container):  python server.py --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "0.4.0"  # bump whenever the messages change (game: protocol.ENGINE_VERSION)
PROTOCOL_VERSION = 1
MAX_BODY_BYTES = 1_000_000

ACADOS = importlib.util.find_spec("acados_template") is not None
if ACADOS:
    import runner  # needs acados
else:
    runner = None


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
            self._send_json(200, {"status": "ok", "version": VERSION, "protocol": PROTOCOL_VERSION,
                                  "acados": ACADOS,
                                  "levels": sorted(runner.RULES) if runner else []})
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
        if runner is None:
            self._send_json(503, {"error": "acados is not available: start the engine in Docker"})
            return
        level_id = request.get("level_id")
        try:
            result = runner.run_level(level_id, request.get("knobs", {}), request.get("waypoints"))
        except ValueError as exc:  # bad request (unknown level/knob, ...)
            self._send_json(400, {"error": str(exc)})
            return
        except Exception as exc:  # bug in the engine: report it, keep serving
            traceback.print_exc()
            self._send_json(500, {"error": f"engine error: {exc}"})
            return
        m = result["metrics"]
        wps = f" waypoints={result['waypoints']}" if result.get("waypoints") else ""
        print(f"[engine] run {level_id} {result['knobs']}{wps} -> {result['outcome']} "
              f"({result['stars']} stars, t={m['time']:.1f} s, E={m['energy']:.2f}) "
              f"computed in {result['compute_time_s']:.2f} s", flush=True)
        self._send_json(200, result)

    def log_message(self, fmt: str, *args) -> None:
        # Quiet: the game polls /health every few seconds. Runs are printed in do_POST.
        if args and str(args[0]).startswith("GET /health"):
            return
        print(f"[engine] {self.address_string()} {fmt % args}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="0.0.0.0", help="0.0.0.0 inside Docker")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"[engine] ControlQuest MPC engine {VERSION} (acados available: {ACADOS})", flush=True)
    if runner is not None:
        runner.warm_up()  # compile solvers before accepting runs
    server = ThreadingHTTPServer((args.host, args.port), EngineHandler)
    print(f"[engine] listening on {args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
