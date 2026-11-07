"""Capture and publish evidence from a passing Operations Analytics build."""
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
    "ops-valid-aggregates": ("Validate totals", {
        4: "Chromium confirmed two excluded records, five valid orders, 60% completion, and a 30-minute median.",
    }),
    "ops-team-period": ("Filter team and period", {
        1: "Select North across the full reporting period.",
        2: "Narrow the reporting period to Jan 2.",
        10: "Verify both North orders, the filtered KPIs, five staffing hours, and one completed order.",
    }),
    "ops-drilldown": ("Drill into a chart day", {
        1: "Select North and leave the full period active.",
        6: "Choose Jan 2 on the chart. The Orders table keeps North and shows only N2 and N3.",
    }),
    "ops-saved-view": ("Restore a saved view", {
        1: "Select South to see its two orders and the incomplete staffing notice.",
        2: "Save the current dashboard view.",
        6: "Reload. Chromium verifies that South, the order volume, and the staffing notice are restored.",
    }),
}


def capture(run_dir, host_repaired=False):
    studio = ROOT / "apps/studio"
    filename = "host-showcase-report.json" if host_repaired else "showcase-report.json"
    showcase = json.loads((run_dir / filename).read_bytes())
    if bool(showcase.get("host_repaired")) != host_repaired:
        raise ValueError("Showcase repair provenance does not match the requested record")
    verified = json.loads(Path(showcase["application_report"]).read_bytes())
    verification = verified["verification"]
    if showcase["status"] != "passed" or verified["status"] != "passed" or verification["functional_success"] is not True:
        raise ValueError("Only a passing Operations build can be published")
    if showcase["model"] != "qwen3-4b-local":
        raise ValueError("Review model provenance before publishing a different model")
    artifacts = verified["artifacts"]
    selected = {item["path"]: item for item in showcase["provenance"]}
    original_report = json.loads((run_dir / "showcase-report.json").read_bytes())
    model_outputs = {(item["path"], item["call"], item["sha256"]) for item in original_report["provenance"]}
    for artifact in artifacts:
        digest = sha256(artifact["content"].encode()).hexdigest()
        item = selected[artifact["path"]]
        if digest != artifact["sha256"] or digest != item["sha256"]:
            raise ValueError("Published source must match the selected source record")
        if host_repaired and (item.get("origin") != "host-repair" or (
                artifact["path"], item["model_call"], item["model_source_sha256"]) not in model_outputs):
            raise ValueError("Host repairs must reference a recorded model source")
    dist = Path(verification["dist_path"])
    outputs = {item["path"]: item["sha256"] for item in verification["stages"]["build"]["outputs"]}
    actual = {path.relative_to(dist).as_posix(): sha256(path.read_bytes()).hexdigest()
              for path in dist.rglob("*") if path.is_file()}
    if actual != outputs:
        raise ValueError("Built assets no longer match the verified digests")
    spec = json.loads((ROOT / "examples/specs/operations-local-reviewed.json").read_bytes())
    scenario_bytes = (ROOT / "examples/specs/operations-local-acceptance.json").read_bytes()
    scenarios = json.loads(scenario_bytes)
    destination = studio / "assets/operations-replay"
    identity = "generated-operations-local-" + sha256("".join(sorted(outputs.values())).encode()).hexdigest()[:12]
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="ops-replay-", dir=cache) as directory:
        frames = Path(directory)
        capture_report = check_application(dist, scenarios, capture_directory=frames, capture_full_page=True)
        if capture_report["status"] != "passed":
            raise RuntimeError("Captured build did not pass all four reviewed scenarios")
        chapters = []
        for check in capture_report["checks"]:
            key = check["scenario_id"]
            title, captions = CHAPTERS[key]
            chapter = {"id": key, "title": title, "checked_steps": check["completed_steps"], "frames": []}
            for step, caption in captions.items():
                name = f"{key}-{step}.png"
                chapter["frames"].append({"file": name, "step": step, "caption": caption,
                    "sha256": sha256((frames / name).read_bytes()).hexdigest()})
            chapters.append(chapter)
        destination.mkdir(exist_ok=True, parents=True)
        for chapter in chapters:
            for frame in chapter["frames"]:
                copyfile(frames / frame["file"], destination / frame["file"])
        cover = chapters[0]["frames"][0]
        copyfile(frames / cover["file"], studio / "assets/generated-operations-preview.png")
    manifest = {"run_id": identity, "browser": capture_report["browser"], "chapters": chapters,
                "scenarios_sha256": sha256(scenario_bytes).hexdigest(),
                "artifacts": {a["path"]: a["sha256"] for a in artifacts}, "build_outputs": outputs}
    atomic_json(destination / "manifest.json", manifest)

    known = json.loads((studio / "generated-task.json").read_bytes())["provenance"]
    provider = json.loads((run_dir / "private/provider/session-report.json").read_bytes())
    events = [
        {"id": "run", "parent_id": None, "type": "execution", "label": "Local Operations showcase", "status": "passed"},
        {"id": "source", "parent_id": "run", "type": "artifact",
         "label": "Generated source and host repairs" if host_repaired else "Retained model output",
         "status": "recorded", "details": {"files": list(selected.values()),
             "model_repair_rounds": original_report["attempt"], "host_repaired": host_repaired}},
        {"id": "verify", "parent_id": "run", "type": "validation", "label": "Build and browser verification", "status": "passed",
         "details": {"build_outputs": outputs, "scenarios": [
             {"id": check["scenario_id"], "status": check["status"], "completed_steps": check["completed_steps"]}
             for check in capture_report["checks"]]}},
        {"id": "capture", "parent_id": "verify", "type": "artifact", "label": "Browser capture and replay", "status": "passed",
         "details": {"screenshot_sha256": cover["sha256"], "frames": sum(len(c["frames"]) for c in chapters)}},
    ]
    atomic_json(studio / "generated-operations.json", {
        "schema_version": 1, "id": identity, "label": "Operations Analytics · Verified generated showcase",
        "mode": "structured-local-synthesis", "status": "verified", "live_inference": True,
        "spec": spec, "events": events, "artifacts": artifacts,
        "metrics": {"build_success": True, "functional_success": True, "end_to_end_pass_rate": 1,
                    "lint_success": verification["lint_success"], "requirement_satisfaction": None,
                    "model_calls": sum(e["status"] == "completed" for e in provider["events"]), "cost_usd": None},
        "provenance": {**{key: known[key] for key in ("model", "revision", "model_file_sha256")},
                       "paid_api_calls": 0, "host_repaired": host_repaired,
                       "scope": ("Showcase with model-generated files and host corrections. " if host_repaired else
                                 "Showcase with a host-defined file contract and model-generated files. ")
                       + "Four reviewed browser scenarios on synthetic records. CSV downloads and sort order across "
                         "pages were outside these checks."},
    })
    print(f"Captured {sum(len(c['frames']) for c in chapters)} frames from four passing Operations workflows")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--host-repaired", action="store_true")
    args = parser.parse_args()
    capture(args.run, args.host_repaired)
