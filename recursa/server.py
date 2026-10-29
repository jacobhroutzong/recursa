"""Read-only replay server. No live inference or generated-code execution endpoint."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def load_runs(directory):
    runs = {}
    for path in sorted(directory.rglob("*.json")):
        if "private" in path.relative_to(directory).parts:
            continue
        if path.stat().st_size > 5_000_000:
            continue
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(run, dict) and isinstance(run.get("id"), str) and isinstance(run.get("events"), list) and isinstance(run.get("artifacts"), list):
                runs[run["id"]] = run
        except (ValueError, OSError):
            continue
    return runs


def make_handler(directory):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route = urlparse(self.path).path
            if route == "/api/runs":
                self.send_data(200, list(load_runs(directory).values()))
            elif route == "/api/progress":
                path = ROOT / "public/progress.json"
                if path.exists():
                    self.send_data(200, json.loads(path.read_text(encoding="utf-8")))
                else:
                    self.send_data(200, {"phase": "Section 5 · offline synthesis foundation", "sections": [],
                                         "updated_at": None, "tests": None,
                                         "notice": "Release evidence has not been generated for this checkout."})
            elif route.startswith("/api/runs/"):
                run = load_runs(directory).get(route[len("/api/runs/"):])
                self.send_data(200 if run else 404, run or {"error": "Run not found"})
            elif route in ("/", "/index.html"):
                body = (ROOT / "apps/studio/index.html").read_bytes()
                self.send_data(200, body, "text/html; charset=utf-8")
            elif route == "/health":
                self.send_data(200, {"status": "ok", "live_inference": False})
            else:
                self.send_data(404, {"error": "Not found"})

        def send_data(self, status, data, mime="application/json"):
            body = data if isinstance(data, bytes) else json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-src 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--runs", type=Path, default=ROOT / "runs")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.runs))
    print(f"Recursa Studio: http://{args.host}:{args.port} (replay only)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
