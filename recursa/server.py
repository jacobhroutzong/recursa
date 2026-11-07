"""Read-only replay server. No live inference or generated-code execution endpoint."""
import argparse
from base64 import b64encode
from hashlib import sha256
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from stat import S_ISREG
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def load_runs(directory):
    directory = directory.resolve()
    runs = {}
    for path in sorted(directory.rglob("*.json")):
        if {"private", "artifacts"}.intersection(part.casefold() for part in path.relative_to(directory).parts):
            continue
        try:
            if path.is_symlink() or path.resolve(strict=True) != path:
                continue
            info = path.stat()
            if not S_ISREG(info.st_mode) or info.st_size > 5_000_000:
                continue
            with path.open("rb") as stream:
                data = stream.read(5_000_001)
            if len(data) > 5_000_000:
                continue
            run = json.loads(data)
            if (isinstance(run, dict) and str(run.get("visibility")).casefold() != "private"
                    and isinstance(run.get("id"), str) and isinstance(run.get("events"), list)
                    and isinstance(run.get("artifacts"), list)):
                runs[run["id"]] = run
        except (ValueError, OSError):
            continue
    return runs


def load_benchmark_traces():
    path = ROOT / "apps/studio/benchmark-traces.json"
    if not path.is_file():
        return {}
    archive = json.loads(path.read_bytes())
    if archive["schema_version"] != 1:
        return {}
    return {trace["id"]: trace for trace in archive["traces"]}


def make_handler(directory):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route = urlparse(self.path).path
            if route == "/api/runs":
                self.send_data(200, list(load_runs(directory).values()))
            elif route == "/api/benchmark-traces":
                fields = ("id", "label", "mode", "status", "trace_group", "trace_schema_version")
                self.send_data(200, {"schema_version": 1, "traces": [
                    {key: trace[key] for key in fields} for trace in load_benchmark_traces().values()
                ]})
            elif route == "/api/playground":
                studio = ROOT / "apps/studio"
                catalog = json.loads((studio / "playground.json").read_bytes())
                for key, filename in (("generated", "generated-task.json"), ("operations", "generated-operations.json")):
                    generated = studio / filename
                    if generated.is_file():
                        catalog[key] = json.loads(generated.read_bytes())
                self.send_data(200, catalog)
            elif route in ("/api/task-comparison", "/api/comparison-series", "/api/repair-series"):
                comparison = ROOT / "apps/studio" / (route.rsplit("/", 1)[1] + ".json")
                if comparison.is_file():
                    self.send_data(200, comparison.read_bytes())
                else:
                    self.send_data(404, {"error": "Comparison not published"})
            elif route in ("/assets/task-preview.png", "/assets/generated-task-preview.png",
                           "/assets/generated-operations-preview.png"):
                asset = ROOT / "apps/studio" / route.lstrip("/")
                if asset.is_file():
                    self.send_data(200, asset.read_bytes(), "image/png")
                else:
                    self.send_data(404, {"error": "Preview not found"})
            elif re.fullmatch(r"/assets/(?:task|operations)-replay/(manifest\.json|[a-z-]+-\d{1,2}\.png)", route):
                asset = ROOT / "apps/studio" / route.lstrip("/")
                if asset.is_file():
                    mime = "image/png" if asset.suffix == ".png" else "application/json"
                    self.send_data(200, asset.read_bytes(), mime)
                else:
                    self.send_data(404, {"error": "Replay frame not found"})
            elif route == "/api/progress":
                path = ROOT / "public/progress.json"
                if path.exists():
                    self.send_data(200, json.loads(path.read_text(encoding="utf-8")))
                else:
                    self.send_data(200, {"phase": "Section 5 · offline synthesis foundation", "sections": [],
                                         "updated_at": None, "tests": None,
                                         "notice": "Release evidence has not been generated for this checkout."})
            elif route == "/api/security-checks":
                path = ROOT / "apps/studio/security-checks.json"
                if path.is_file():
                    self.send_data(200, path.read_bytes())
                else:
                    self.send_data(404, {"error": "Security checks not published"})
            elif route.startswith("/api/runs/"):
                identifier = route[len("/api/runs/"):]
                run = (load_benchmark_traces() if identifier.startswith("benchmark-") else
                       load_runs(directory)).get(identifier)
                self.send_data(200 if run else 404, run or {"error": "Run not found"})
            elif route in ("/", "/index.html"):
                body = (ROOT / "apps/studio/index.html").read_bytes()
                normalized = body.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                scripts = re.findall(rb"<script>(.*?)</script>", normalized, re.DOTALL)
                hashes = " ".join("'sha256-" + b64encode(sha256(script).digest()).decode() + "'"
                                  for script in scripts)
                self.send_data(200, body, "text/html; charset=utf-8", scripts=hashes or "'none'")
            elif route == "/health":
                self.send_data(200, {"status": "ok", "live_inference": False})
            else:
                self.send_data(404, {"error": "Not found"})

        def reject_write(self):
            self.send_data(405, {"error": "Replay service is read-only"})

        do_POST = do_PUT = do_PATCH = do_DELETE = reject_write

        def send_data(self, status, data, mime="application/json", *, scripts="'none'"):
            body = data if isinstance(data, bytes) else json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", f"default-src 'self'; script-src {scripts}; "
                             "style-src 'self' 'unsafe-inline'; object-src 'none'; frame-src 'none'; "
                             "base-uri 'none'; form-action 'none'")
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
