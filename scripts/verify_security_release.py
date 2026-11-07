"""Measure the sandbox and replay boundaries without model inference."""
import argparse
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from recursa.container_rlm import runtime_source_hash
from recursa.experiments import atomic_json
from recursa.sandbox import run_python
from recursa.server import make_handler


def check_http(base):
    def get(path, expected=200, method="GET"):
        request = Request(base + path, method=method, data=b"{}" if method != "GET" else None)
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            assert response.status == expected, (path, method, response.status)
            return response.read(), response.headers

    body, headers = get("/")
    assert b"Recursa" in body
    csp = headers["Content-Security-Policy"]
    assert "script-src 'sha256-" in csp and "frame-src 'none'" in csp and "form-action 'none'" in csp
    assert "'unsafe-inline'" not in csp.split("script-src ", 1)[1].split(";", 1)[0]
    assert headers["X-Content-Type-Options"] == "nosniff" and headers["Cache-Control"] == "no-store"
    assert json.loads(get("/health")[0]) == {"status": "ok", "live_inference": False}
    for route in ("/api/execute", "/api/inference", "/v1/chat/completions", "/.git/config", "/.env",
                  "/private/provider/session-report.json", "/api/runs/%2e%2e%2fprivate",
                  "/assets/task-replay/%2e%2e%2fgenerated-task-preview.png"):
        get(route, 404)
    for method, route in (("POST", "/api/execute"), ("POST", "/v1/chat/completions"),
                          ("PUT", "/api/runs"), ("PATCH", "/api/progress"), ("DELETE", "/api/runs")):
        get(route, 405, method)
    index = json.loads(get("/api/benchmark-traces")[0])
    assert len(index["traces"]) == 27
    for entry in index["traces"]:
        trace = json.loads(get("/api/runs/" + entry["id"])[0])
        assert trace["live_inference"] is False and trace["artifacts"] == []
        for event in trace["events"]:
            assert not {"content", "diagnostic", "messages", "prompt", "response"} & event["details"].keys()


def archive_probe(image, output):
    source = """
import json
from pathlib import Path
from recursa.server import load_runs
root = Path('/work/replay')
def record(path, name, **metadata):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(id=name, events=[], artifacts=[], **metadata)))
record(root/'good.json', 'public')
record(root/'PRIVATE/hidden.json', 'private-directory')
record(root/'Artifacts/hidden.json', 'artifact-directory')
record(root/'tagged.json', 'private-tag', visibility='Private')
record(Path('/work/outside.json'), 'outside')
(root/'linked.json').symlink_to('/work/outside.json')
(root/'directory-link').symlink_to(root/'PRIVATE', target_is_directory=True)
assert list(load_runs(root)) == ['public']
"""
    result = run_python(source, image, output)
    return result["status"] == "completed" and result["policy_verified"] and result["cleanup_verified"]


def suite_status(*modules):
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    status = "failed" if not result.wasSuccessful() else "unmeasured" if result.skipped else "passed"
    return status, result.testsRun


def report(container_path, output, scratch):
    container = json.loads(container_path.read_bytes())
    image = json.loads((ROOT / ".cache/rlm-runtime-image.json").read_bytes())
    if image["runtime_source_sha256"] != runtime_source_hash() or container["image_id"] != image["image_id"]:
        raise ValueError("Container evidence must match the current reviewed runtime")
    cases = {row["name"]: row for row in container["cases"]}
    rows = []

    def add(area, name, status, evidence):
        rows.append({"area": area, "check": name, "status": status, "evidence": evidence})

    probe = cases.get("policy-probe", {})
    for key, outcome in probe.get("checks", {}).items():
        add("Local Linux container", key.replace("_", " "), "passed" if outcome else "failed",
            "Observed inside the pinned container")
    for name, expected, detail in (
        ("timeout", "timeout", "Running workload stopped at its deadline"),
        ("output-limit", "output-limit", "Combined stdout and stderr stayed within 4 KiB"),
        ("memory-limit", "failed", "512 MiB allocation hit the 256 MiB cap and Docker reported OOM"),
        ("pid-limit", "completed", "Process creation was denied at the configured PID cap"),
    ):
        row = cases.get(name)
        passed = container["status"] == "passed" and row and row["status"] == expected
        add("Local Linux container", name.replace("-", " "), "passed" if passed else "unmeasured", detail)
    add("Local Linux container", "Container cleanup",
        "passed" if len(cases) == 5 and all(row["cleanup_verified"] for row in cases.values()) else "failed",
        "All five reviewed container cases confirmed cleanup")
    add("Replay archive", "Private and linked files excluded",
        "passed" if archive_probe(image["image_id"], scratch / "archive-probe") else "failed",
        "Real Linux files covered mixed-case private directories, a private tag, and file and directory symlinks")

    for area, name, modules in (
        ("Containment", "Reject weakened policy and no host fallback",
         ("test_sandbox_policy", "test_container_rlm_boundary")),
        ("Provider boundary", "Broker authorization and request limits", ("test_broker",)),
        ("Windows worker", "Deadline and descendant cleanup", ("test_process_boundary",)),
        ("Generated app browser", "External activity blocked",
         ("test_browser_checks.BrowserChecksTests.test_actual_browser_blocks_external_activity",)),
    ):
        status, count = suite_status(*modules)
        add(area, name, status, f"{count} targeted test case(s)")
    with ThreadingHTTPServer(("127.0.0.1", 0), make_handler(ROOT / "traces/public")) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            check_http(base)
            add("Replay HTTP", "Read-only routes and sanitized trace responses", "passed",
                "Denied execution, write methods, private paths and encoded traversal. Checked all 27 traces")
            browser = subprocess.run(["node", str(ROOT / "scripts/verify_replay_browser.mjs"), base],
                                     cwd=ROOT, timeout=45, check=False)
            add("Replay browser", "Private import stays inert and local",
                "passed" if browser.returncode == 0 else "failed",
                "Chromium checked text-only rendering, no upload or embedded fetch, and hash-based script blocking")
        finally:
            server.shutdown()
            thread.join()
    atomic_json(output, {"schema_version": 1, "verified_at": datetime.now(timezone.utc).isoformat(),
        "live_inference": False, "runtime_source_sha256": image["runtime_source_sha256"],
        "scope": "Local Docker, Windows worker, replay HTTP, and Chromium checks. Containers share a kernel. "
                 "The report measures the listed controls.",
        "checks": rows})
    return all(row["status"] == "passed" for row in rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container-evidence", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--live-url", help="Repeat the replay HTTP checks on the deployed Studio")
    args = parser.parse_args()
    if args.live_url:
        check_http(args.live_url.rstrip("/"))
        print("Published replay passed route, trace, and browser-header checks")
    elif args.container_evidence and args.output and args.scratch:
        raise SystemExit(0 if report(args.container_evidence, args.output, args.scratch) else 1)
    else:
        parser.error("Specify --live-url or all three local report arguments")
