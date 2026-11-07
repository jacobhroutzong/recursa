"""Export versioned, sanitized Explorer traces from benchmark evidence."""
import argparse
import json
from pathlib import Path

from run_task_comparison import ROOT
from recursa.experiments import atomic_json


METHODS = {"direct": "Direct LLM", "structured": "Structured", "rlm": "Contained RLM"}
ARCHIVES = {
    "pilot": ("task-comparison.json", "Original pilot", "task-comparison-002"),
    "repeated": ("comparison-series.json", "Repeated first pass", "series-seed"),
    "paired": ("repair-series.json", "Paired repair", "repair-seed"),
}


def read(path):
    return json.loads(path.read_bytes())


def trial_blocks(public, archive):
    filename, label, _ = ARCHIVES[archive]
    data = read(public / filename)
    if archive == "pilot":
        yield "tasks", "Task Management", label, data
    else:
        for case in data["cases"]:
            for block in case["blocks"]:
                yield case["id"], case["label"], label, block


def project(archive, case, label, group, block, trial, directory):
    seed, method = block["settings"]["seed"], trial["method"]
    events = []

    def add(key, parent, kind, name, status, *, duration=None, details=None):
        events.append({"id": key, "parent_id": parent, "type": kind, "label": name,
                       "status": status, "duration_ms": duration, "details": details or {}})

    def verification(parent, prefix, application, outcome):
        result = read(application) if application.is_file() else {}
        measured = result.get("verification", {})
        stages = measured.get("stages", {})
        artifacts = result.get("artifacts", [])
        paths = {artifact["path"] for artifact in artifacts}
        if artifacts:
            add(prefix + "-manifest", parent, "artifact", "Source manifest", "recorded",
                details={"files": [{key: artifact[key] for key in ("path", "sha256", "requirements")}
                                   for artifact in artifacts]})
        for kind, title in (("source", "Source checks"), ("lint", "Lint"), ("build", "Production build"),
                            ("browser", "Browser acceptance"), ("unit", "Unit checks")):
            stage = stages.get(kind, {})
            checks = stage.get("checks", [])
            if kind == "browser" and not checks:
                checks = outcome.get("scenarios", [])
            if not stage and not checks:
                continue
            stage_id = prefix + "-" + kind
            add(stage_id, parent, "validation", title, stage.get("status", "recorded"),
                duration=stage.get("duration_ms"), details={"checks": len(checks)})
            for index, check in enumerate(checks, 1):
                # Keep classifications and requirement references. Diagnostics can contain source.
                fields = ("scenario_id", "kind", "requirements", "completed_steps", "blocked_activity",
                          "error_classification")
                details = {key: check[key] for key in fields if key in check}
                if check.get("path") in paths:
                    details["artifact_path"] = check["path"]
                add(f"{stage_id}-{index}", stage_id, "check", check.get("scenario_id") or check["kind"],
                    check["status"], details=details)

    root = {"archive": group, "specification": label, "seed": seed, "method": METHODS[method],
            **{key: block.get(key) for key in ("model", "revision", "weights_sha256",
                "runtime_binary_sha256", "rlm_runtime_source_sha256", "spec_sha256", "scenarios_sha256",
                "settings", "budget", "repair_budget", "output_tokens_per_call", "paid_api_calls")}}
    add("trial", None, "execution", "Recorded benchmark trial", "recorded", details=root)
    measurement = {key: trial[key] for key in ("build_success", "lint_success", "accessibility_success",
                   "end_to_end_pass_rate", "requirement_satisfaction", "billing_cost_usd", "error_classification")}
    add("first-pass", "trial", "validation", "First-pass generation and verification", trial["status"],
        duration=trial["wall_ms"], details={**measurement, **trial["usage"]})
    provider = read(directory / "private/provider/session-report.json")
    requests = [event for event in provider["events"] if "prompt_sha256" in event]
    if (provider["reserved_calls"] != trial["usage"]["reserved_calls"]
            or sum(event["status"] == "completed" for event in requests) != trial["usage"]["completed_calls"]
            or len(requests) != provider["reserved_calls"]):
        raise ValueError("Private call counts differ from the published trial")
    timings = {call["number"]: call for call in trial.get("initial_calls", [])}
    if set(timings) - set(range(1, len(requests) + 1)):
        raise ValueError("Published timing does not reference a recorded request")
    for index, request in enumerate(requests, 1):
        timing = timings.get(index, {})
        details = {"timing_source": timing.get("timing_source"),
                   "tokens": timing.get("tokens", request.get("provider_reported_usage")),
                   "error_classification": request.get("error_classification")}
        details.update({key: timing[key] for key in ("prompt_eval_ms", "generation_ms") if key in timing})
        add(f"first-call-{index}", "first-pass", "model_call", f"Initial model call {index}",
            timing.get("status", request["status"]), duration=timing.get("duration_ms"), details=details)
    if trial["rlm_observations"] is not None:
        add("rlm", "first-pass", "runtime", "Contained runtime observations", "recorded",
            details=trial["rlm_observations"])
    verification("first-pass", "initial", directory / "private/application/application-report.json", trial)
    repair = trial.get("repair")
    if repair:
        repair_dir = directory / "private/paired-repair"
        state_path = repair_dir / "repair-state.json"
        attempts = read(state_path)["attempts"] if state_path.is_file() else []
        change_hashes = attempts[0].get("source_hashes", {}) if attempts else {}
        if len(change_hashes) != repair["changed_files"]:
            raise ValueError("Private change hashes differ from the recorded repair")
        add("repair", "trial", "repair", "Bounded repair and recheck", repair["status"],
            duration=repair["wall_ms"], details={"attempts": repair["attempts"],
                "changed_files": repair["changed_files"], "source_hashes": change_hashes})
        if repair["inference_wall_ms"] is not None:
            repair_provider = read(repair_dir / "provider/session-report.json")
            add("repair-call", "repair", "model_call", "Repair model call",
                "completed" if repair["usage"]["completed_calls"] else "no completed response",
                duration=repair["inference_wall_ms"], details={**repair["usage"],
                    "error_classification": repair_provider["stop_reason"]})
        if repair["recheck_wall_ms"] is not None:
            after = repair["after"] or {}
            add("recheck", "repair", "validation", "Reverification", after.get("status", repair["status"]),
                duration=repair["recheck_wall_ms"], details={key: after.get(key) for key in measurement})
            if after:
                verification("recheck", "after",
                             repair_dir / "recheck/application-report.json", after)
    seen = {None}
    for event in events:
        if event["id"] in seen or event["parent_id"] not in seen:
            raise ValueError("Trace event IDs must be unique and follow their parents")
        seen.add(event["id"])
    return {"schema_version": 1, "trace_schema_version": 1, "trace_group": group,
            "id": f"benchmark-{archive}-{case}-{seed}-{method}",
            "label": f"{label} · {METHODS[method]} · seed {seed}", "mode": "benchmark-trace",
            "status": trial["status"], "live_inference": False, "events": events, "artifacts": [],
            "metrics": {"first_pass_wall_ms": trial["wall_ms"], "model_calls": trial["usage"]["completed_calls"],
                        "functional_success": (None if trial["end_to_end_pass_rate"] is None else
                                               trial["end_to_end_pass_rate"] == 1), **measurement}}


def build(public, runs):
    traces = []
    for archive, (_, _, folder) in ARCHIVES.items():
        for case, label, group, block in trial_blocks(public, archive):
            seed = block["settings"]["seed"]
            run = runs / folder if archive == "pilot" else runs / f"{folder}-{seed}" / case
            private_block = read(run / "comparison-record.json")
            for field in ("spec_sha256", "scenarios_sha256", "settings", "weights_sha256", "budget"):
                if block[field] != private_block[field]:
                    raise ValueError("Private block identity does not match the published benchmark")
            for trial, observed in zip(block["trials"], private_block["trials"], strict=True):
                if {key: value for key, value in trial.items() if key != "initial_calls"} != observed:
                    raise ValueError("Private trial does not match the published benchmark")
                traces.append(project(archive, case, label, group, block, trial, run / trial["method"]))
    if len({trace["id"] for trace in traces}) != len(traces):
        raise ValueError("Duplicate benchmark trace IDs")
    return {"schema_version": 1, "traces": traces}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", required=True, type=Path, help="Private local benchmark directory")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    atomic_json(args.output, build(ROOT / "apps/studio", args.runs))
