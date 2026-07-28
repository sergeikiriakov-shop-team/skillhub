"""A generic, dependency-free *recording fake service* for the skill sandbox.

It stands in for whatever external system a skill talks to (a tracker API, an internal service,
etc.) — deliberately domain-neutral. It:

  * serves canned responses declared by a scenario (``routes.json``), and
  * records every request it receives to ``calls.jsonl`` in the run directory,

so that, after the live Claude Code session has executed a skill against it, the harness can
assert *what the skill actually did* (which endpoints it hit, with what payloads).

Run it as its own process so it stays up while the agent works:

    python -m evals.fake_service --run-dir .sandbox/run-XYZ [--port 0]

It prints one line ``FAKE_SERVICE_URL=http://127.0.0.1:<port>`` (port 0 = pick a free port), then
serves until terminated. Uses only the Python standard library."""

from __future__ import annotations

import argparse
import json
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def _load_routes(run_dir: Path) -> list[dict]:
    """routes.json: a list of {method, path_regex, status, json}. First match wins."""
    routes_file = run_dir / "routes.json"
    if not routes_file.exists():
        return []
    return json.loads(routes_file.read_text(encoding="utf-8"))


class _Handler(BaseHTTPRequestHandler):
    run_dir: Path = Path(".")
    routes: list[dict] = []
    _lock = threading.Lock()

    def log_message(self, *args) -> None:  # silence default stderr access log
        pass

    def _record(self, method: str, body: str) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "method": method,
            "path": self.path,
            "body": body,
        }
        with self._lock:
            with (self.run_dir / "calls.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _match(self, method: str) -> dict | None:
        for route in self.routes:
            if route.get("method", "GET").upper() != method:
                continue
            if re.fullmatch(route.get("path_regex", ""), self.path.split("?")[0]):
                return route
        return None

    def _respond(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8") if length else ""
        self._record(method, body)
        route = self._match(method)
        if route is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error":"no canned route"}')
            return
        payload = json.dumps(route.get("json", {})).encode("utf-8")
        self.send_response(int(route.get("status", 200)))
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self._respond("GET")

    def do_POST(self) -> None:
        self._respond("POST")

    def do_PUT(self) -> None:
        self._respond("PUT")

    def do_DELETE(self) -> None:
        self._respond("DELETE")


def serve(run_dir: Path, port: int = 0, host: str = "127.0.0.1") -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    # Truncate the call log on start so each service run is a clean, isolated trial.
    (run_dir / "calls.jsonl").write_text("", encoding="utf-8")
    _Handler.run_dir = run_dir
    _Handler.routes = _load_routes(run_dir)
    # host: 127.0.0.1 for the host-Python path; 0.0.0.0 in a container so a published -p port reaches it.
    httpd = ThreadingHTTPServer((host, port), _Handler)
    actual_port = httpd.server_address[1]
    (run_dir / "url.txt").write_text(f"http://127.0.0.1:{actual_port}", encoding="utf-8")
    print(f"FAKE_SERVICE_URL=http://127.0.0.1:{actual_port}", flush=True)
    httpd.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Recording fake service for the skill sandbox.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    serve(Path(args.run_dir), args.port, args.host)


if __name__ == "__main__":
    main()
