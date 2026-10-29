from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
from recursa.server import make_handler
from recursa.experiments import ROOT, atomic_json
from recursa.engine import run_smoke


class ServerTests(unittest.TestCase):
    def test_http_replay_routes_and_boundary(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache") as tmp:
            run = run_smoke({"name": "Test", "requirements": [{"id": "R1", "text": "Test"}]})
            atomic_json(Path(tmp) / "run.json", run)
            atomic_json(Path(tmp) / "private/run.json", dict(run, id="private-should-not-be-served"))
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Path(tmp)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(base + "/api/runs") as response:
                    archive = json.loads(response.read())
                    self.assertEqual([r["id"] for r in archive], [run["id"]])
                with urlopen(base + "/") as response:
                    self.assertIn(b"Recursa", response.read())
                    self.assertIn("frame-src 'none'", response.headers["Content-Security-Policy"])
                with urlopen(base + "/api/progress") as response:
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertIn("phase", json.loads(response.read()))
                for route in ("/../README.md", "/api/execute", "/api/runs/missing"):
                    with self.assertRaises(HTTPError) as error:
                        urlopen(base + route)
                    self.assertEqual(error.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
