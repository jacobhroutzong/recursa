"""Publish captures only from the passing, source-bound Aviation showcase."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from shutil import copyfile
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recursa.browser_checks import check_application
from recursa.experiments import atomic_json

CHAPTERS = {
    "av-board-conflict": ("Inspect the flight board", {
        6: "Four valid flights are sorted by scheduled UTC and flight ID. One malformed record is excluded, and A02 has one overlapping pair.",
    }),
    "av-scope-detail": ("Inspect a flight and filter scope", {
        3: "Open AX101. The detail shows an unknown milestone and the simulated alert SIM-101.",
        7: "Filter to T2, the later UTC window, and Delayed. Only one flight remains in scope.",
        12: "The board, stand assignments, and alerts reflect the same T2 scope.",
    }),
    "av-acknowledge-reset": ("Pause, acknowledge, reload, and reset", {
        2: "Advance the exercise to 08:05 UTC.",
        7: "Pause the clock and acknowledge SIM-101. The acknowledgement records 08:05 UTC.",
        10: "Reload. The acknowledgement and High priority are still visible.",
        13: "Reset restores 08:00 UTC and clears the acknowledgement.",
    }),
    "av-narrow-summary": ("Prepare a summary by keyboard", {
        2: "At a 390-pixel viewport, the fictional exercise label remains visible.",
        9: "Press Enter to prepare the summary. Chromium checks the label, scope, source IDs, alert count, and basic accessibility.",
    }),
}


def read(path):
    return json.loads(path.read_bytes())


def capture(run_dir):
    studio = ROOT / "apps/studio"
    report = read(run_dir / "showcase-report.json")
    app = read(Path(report["application_report"]))
    verified = app["verification"]
    if report["status"] != "passed" or app["status"] != "passed" or verified["functional_success"] is not True:
        raise ValueError("A passing Aviation build is required")
    originals = {item["path"]: item for item in read(run_dir / "model-files.json")}
    lineage = report["lineage"]
    for artifact in app["artifacts"]:
        path = artifact["path"]
        digest = sha256(artifact["content"].encode()).hexdigest()
        if digest != artifact["sha256"] or digest != lineage[path]["sha256"]:
            raise ValueError("Aviation source differs from the verified record")
        if path in originals and lineage[path]["model_source_sha256"] != sha256(originals[path]["content"].encode()).hexdigest():
            raise ValueError("Aviation source lineage differs from the recorded model output")
    dist = Path(verified["dist_path"])
    outputs = {item["path"]: item["sha256"] for item in verified["stages"]["build"]["outputs"]}
    actual = {path.relative_to(dist).as_posix(): sha256(path.read_bytes()).hexdigest()
              for path in dist.rglob("*") if path.is_file()}
    if actual != outputs:
        raise ValueError("Built assets differ from the verified record")
    spec = read(ROOT / "examples/specs/aviation-local-reviewed.json")
    scenario_bytes = (ROOT / "examples/specs/aviation-local-acceptance.json").read_bytes()
    scenarios = json.loads(scenario_bytes)
    target = studio / "assets/aviation-replay"
    target.mkdir(exist_ok=True, parents=True)
    identity = "generated-aviation-local-" + sha256("".join(sorted(outputs.values())).encode()).hexdigest()[:12]
    chapters = []
    with TemporaryDirectory(prefix="aviation-replay-", dir=ROOT / ".cache") as directory:
        frames = Path(directory)
        browser = check_application(dist, scenarios, capture_directory=frames, capture_full_page=True)
        if browser["status"] != "passed":
            raise RuntimeError("The captured Aviation build did not pass verification")
        for check in browser["checks"]:
            key = check["scenario_id"]
            title, captions = CHAPTERS[key]
            chapter = {"id": key, "title": title, "checked_steps": check["completed_steps"], "frames": []}
            for step, caption in captions.items():
                name = f"{key}-{step}.png"
                image = frames / name
                chapter["frames"].append({"file": name, "step": step, "caption": caption,
                                          "sha256": sha256(image.read_bytes()).hexdigest()})
                copyfile(image, target / name)
            chapters.append(chapter)
        cover = chapters[0]["frames"][0]
        copyfile(frames / cover["file"], studio / "assets/generated-aviation-preview.png")
    count = sum(len(c["frames"]) for c in chapters)
    atomic_json(target / "manifest.json", {
        "run_id": identity, "browser": browser["browser"], "chapters": chapters,
        "scenarios_sha256": sha256(scenario_bytes).hexdigest(), "build_outputs": outputs,
        "artifacts": {a["path"]: a["sha256"] for a in app["artifacts"]},
    })
    known = read(studio / "generated-task.json")["provenance"]
    provider = read(run_dir / "private/provider/session-report.json")
    atomic_json(studio / "generated-aviation.json", {
        "schema_version": 1, "id": identity, "label": "Aviation Operations · Verified synthetic exercise",
        "mode": "structured-local-synthesis", "status": "verified", "live_inference": True,
        "spec": spec, "artifacts": app["artifacts"],
        "events": [
            {"id": "run", "parent_id": None, "type": "execution", "label": "Local Aviation showcase", "status": "passed"},
            {"id": "source", "parent_id": "run", "type": "artifact", "label": "Model output and host assembly",
             "status": "recorded", "details": {"lineage": lineage}},
            {"id": "verify", "parent_id": "run", "type": "validation", "label": "Build and browser verification",
             "status": "passed", "details": {"build_outputs": outputs, "scenarios": [
                 {"id": c["scenario_id"], "completed_steps": c["completed_steps"], "status": c["status"]}
                 for c in browser["checks"]]}},
            {"id": "capture", "parent_id": "verify", "type": "artifact", "label": "Browser capture and replay",
             "status": "passed", "details": {"screenshot_sha256": cover["sha256"], "frames": count}},
        ],
        "metrics": {"build_success": True, "lint_success": verified["lint_success"], "functional_success": True,
                    "end_to_end_pass_rate": 1, "requirement_satisfaction": None,
                    "model_calls": sum(e["status"] == "completed" for e in provider["events"]), "cost_usd": None},
        "provenance": {**{key: known[key] for key in ("model", "revision", "model_file_sha256")},
                       "host_repaired": True, "paid_api_calls": 0,
                       "scope": "Fictional exercise. Qwen generated the shell, style and renderers. Host code "
                                "corrected those files and supplied the exercise controller and fixture module."},
    })
    print(f"Captured {count} frames from {len(chapters)} passing Aviation workflows")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    capture(parser.parse_args().run)
