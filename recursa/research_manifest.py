"""Offline-only provenance and comparability checks for future Recursa research.

This module deliberately does not invoke inference or change the P0 runtime.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

ARMS = frozenset({"direct", "external_context_only", "recursive_subcalls"})
SHA = re.compile(r"^[a-f0-9]{64}$")
REV = re.compile(r"^[a-f0-9]{40,64}$")
SHARED = ("task_suite_sha256", "model_id", "model_revision",
          "tokenizer_revision", "decoding_config", "evaluation_version",
          "resource_limits", "seed")


def validate_research_run(run: dict) -> None:
    if not isinstance(run, dict):
        raise ValueError("run must be an object")
    if run.get("arm") not in ARMS:
        raise ValueError("invalid experiment arm")
    if run.get("evidence") not in {"planned", "offline_simulated", "measured"}:
        raise ValueError("evidence must distinguish planned/simulated/measured")
    if not isinstance(run.get("task_suite_sha256"), str) or not SHA.fullmatch(run["task_suite_sha256"]):
        raise ValueError("task_suite_sha256 must be SHA-256")
    for key in ("model_revision", "tokenizer_revision"):
        if not isinstance(run.get(key), str) or not REV.fullmatch(run[key]):
            raise ValueError(f"{key} must be pinned to a commit")
    for key in ("model_id", "evaluation_version"):
        if not isinstance(run.get(key), str) or not run[key].strip():
            raise ValueError(f"{key} is required")
    if type(run.get("seed")) is not int or run["seed"] < 0:
        raise ValueError("seed must be nonnegative integer")
    dec = run.get("decoding_config")
    if not isinstance(dec, dict) or any(k not in dec for k in ("temperature", "max_output_tokens")):
        raise ValueError("decoding settings missing")
    if (type(dec["temperature"]) not in (float, int) or not math.isfinite(dec["temperature"])
            or dec["temperature"] < 0 or type(dec["max_output_tokens"]) is not int
            or dec["max_output_tokens"] <= 0):
        raise ValueError("invalid decoding settings")
    limits = run.get("resource_limits")
    if not isinstance(limits, dict) or any(k not in limits for k in ("max_calls", "max_cost_usd", "max_wall_seconds")):
        raise ValueError("resource limits missing")
    if any(type(v) not in (float, int) or not math.isfinite(v) or v < 0 for v in limits.values()):
        raise ValueError("invalid resource limits")
    if run["evidence"] == "measured":
        metrics = run.get("metrics")
        if not isinstance(metrics, dict) or not all(
            k in metrics for k in ("model_calls", "functional_success", "latency_ms")
        ):
            raise ValueError("measured evidence requires metrics")
        if type(metrics["model_calls"]) is not int or metrics["model_calls"] < 1:
            raise ValueError("measured run needs actual model calls")
        if type(metrics["functional_success"]) is not bool:
            raise ValueError("success must be a recorded boolean")
        if (type(metrics["latency_ms"]) not in (int, float)
                or not math.isfinite(metrics["latency_ms"]) or metrics["latency_ms"] < 0):
            raise ValueError("latency invalid")
        if not isinstance(run.get("trace_sha256"), str) or not SHA.fullmatch(run["trace_sha256"]):
            raise ValueError("measured run needs trace digest")


def compare_arms(runs: list[dict]) -> dict:
    """Audit matched configurations only; never claim a benchmark gain."""
    if not isinstance(runs, list) or len(runs) != 3:
        raise ValueError("exactly three arms required")
    for run in runs:
        validate_research_run(run)
    if {r["arm"] for r in runs} != ARMS:
        raise ValueError("missing or duplicate comparison arm")
    for key in SHARED:
        value = json.dumps(runs[0][key], sort_keys=True)
        if any(json.dumps(r[key], sort_keys=True) != value for r in runs[1:]):
            raise ValueError(f"mismatched shared comparison field: {key}")
    if len({r["evidence"] for r in runs}) != 1:
        raise ValueError("cannot mix simulated and measured evidence")
    raw = json.dumps(runs, sort_keys=True, separators=(",", ":")).encode()
    return {"comparable": True, "evidence": runs[0]["evidence"],
            "measured": runs[0]["evidence"] == "measured",
            "arms": sorted(ARMS),
            "comparison_sha256": hashlib.sha256(raw).hexdigest(),
            "limitation": "Protocol comparability only; no research advantage claimed."}
