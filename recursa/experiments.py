"""Portable, restartable experiment batches. No accelerator or model call by default."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique siblings avoid concurrent writers sharing a staging file. Windows
    # sync/indexing readers can briefly prevent replacement even after close.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix=path.name + '.', suffix='.tmp', delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(json.dumps(value, indent=2, ensure_ascii=False))
    try:
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.02 * 2 ** attempt)
    finally:
        temporary.unlink(missing_ok=True)


def load_config(path: Path) -> tuple[dict, dict]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("mode") not in {"smoke", "live"}:
        raise ValueError("mode must be smoke or live")
    if type(config.get("trials")) is not int or not 1 <= config["trials"] <= 100:
        raise ValueError("trials must be an integer from 1 to 100")
    budget = config.get("budget", {})
    for key in ("max_wall_seconds", "max_calls", "max_cost_usd", "max_output_tokens"):
        value = budget.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError(f"budget.{key} must be a finite nonnegative number")
    if budget["max_wall_seconds"] <= 0:
        raise ValueError("max_wall_seconds must be positive")
    if config["mode"] == "live" and (budget["max_calls"] < 1 or budget["max_output_tokens"] < 1):
        raise ValueError("live mode requires a positive call and output-token budget")
    spec_path = (ROOT / config["spec"]).resolve()
    if not spec_path.is_relative_to(ROOT):
        raise ValueError("spec must be inside the repository")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    return config, spec


def fingerprint(config: dict, spec: dict) -> str:
    """Source digest invalidates checkpoints even for uncommitted code changes."""
    digest = hashlib.sha256(json.dumps([config, spec], sort_keys=True).encode())
    digest.update(sys.version.encode())
    for name in ("pyproject.toml", "requirements-live.lock", "tooling/typecheck/package.json", "tooling/typecheck/package-lock.json",
                 "tooling/frontend/package.json", "tooling/frontend/package-lock.json", "tooling/browser/package.json", "tooling/browser/package-lock.json"):
        path = ROOT / name
        if path.exists():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    for directory in (ROOT / "recursa", ROOT / "prompts", ROOT / "scripts", ROOT / "examples/fixtures"):
        if directory.exists():
            for path in sorted(directory.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    digest.update(path.relative_to(ROOT).as_posix().encode())
                    digest.update(path.read_bytes())
    return digest.hexdigest()


def export_batch(directory: Path) -> Path:
    rows = []
    for checkpoint in sorted(directory.glob("trial-*/checkpoint.json")):
        state = json.loads(checkpoint.read_text(encoding="utf-8"))
        row = {key: state.get(key) for key in ("trial", "status", "duration_seconds", "mode")}
        run_path = checkpoint.parent / "run.json"
        if run_path.exists():
            metrics = json.loads(run_path.read_text(encoding="utf-8")).get("metrics", {})
            row.update({key: metrics.get(key) for key in ("model_calls", "cost_usd", "requirements", "functional_success")})
        rows.append(row)
    with (directory / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["trial", "status", "duration_seconds", "mode", "model_calls", "cost_usd", "requirements", "functional_success"])
        writer.writeheader()
        writer.writerows(rows)
    target = directory / "recursa-artifacts.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            # Never include temporary files or raw runtime logs in public export.
            if path.is_file() and path != target and path.suffix in {".json", ".csv"} and "private" not in path.parts:
                archive.write(path, path.relative_to(directory))
    return target


def run_batch(config_path: Path, output: Path, authorize_live: bool = False) -> Path:
    config, spec = load_config(config_path)
    if config["mode"] == "live" and not authorize_live:
        raise ValueError("live execution requires --authorize-live and a reviewed finite budget")
    if config["mode"] == "live":
        raise ValueError("Live batch execution remains disabled pending genuine-backend and execution-boundary verification; use offline tests first")
    identity = fingerprint(config, spec)
    directory = output.resolve() / identity[:16]
    directory.mkdir(parents=True, exist_ok=True)
    # Configs contain environment variable names only, never credential values.
    atomic_json(directory / "manifest.json", {"schema_version": "1.0", "fingerprint": identity,
                "config": config, "python": sys.version.split()[0], "spec": spec})
    started = time.monotonic()
    for index in range(config["trials"]):
        trial = directory / f"trial-{index + 1:03}"
        trial.mkdir(exist_ok=True)
        checkpoint = trial / "checkpoint.json"
        if checkpoint.exists():
            previous = json.loads(checkpoint.read_text(encoding="utf-8"))
            # Failed / interrupted model trials are not silently rerun and recharged.
            if previous.get("status") in {"complete", "failed", "timeout"}:
                continue
            if previous.get("status") == "running" and config["mode"] == "live":
                continue
        remaining = config["budget"]["max_wall_seconds"] - (time.monotonic() - started)
        if remaining <= 0:
            break
        atomic_json(trial / "input.json", {"config": config, "spec": spec})
        state = {"trial": index + 1, "mode": config["mode"], "status": "running"}
        atomic_json(checkpoint, state)
        trial_start = time.monotonic()
        try:
            # Child process bounds blocked providers and untrusted runtime execution.
            # stdout/stderr can contain model content, so do not place them in exports.
            result = subprocess.run([sys.executable, "-m", "recursa.experiments", "--worker", str(trial)],
                                    cwd=ROOT, timeout=remaining, capture_output=True)
            state["status"] = "complete" if result.returncode == 0 and (trial / "run.json").exists() else "failed"
            if result.returncode != 0:
                state["error"] = "worker_failed; inspect local environment and configuration"
        except subprocess.TimeoutExpired:
            state["status"] = "timeout"
        finally:
            state["duration_seconds"] = round(time.monotonic() - trial_start, 6)
            atomic_json(checkpoint, state)
            export_batch(directory)
        if state["status"] != "complete":
            break
    export_batch(directory)
    return directory


def worker(directory: Path) -> None:
    value = json.loads((directory / "input.json").read_text(encoding="utf-8"))
    if value["config"]["mode"] == "smoke":
        from recursa.engine import run_smoke
        run = run_smoke(value["spec"])
    else:
        from recursa.live import run_live
        run = run_live(value["spec"], directory, value["config"])
    run["id"] = directory.parent.name + "-" + directory.name
    run["provenance"] = {"batch_fingerprint": directory.parent.name, "trial": directory.name}
    atomic_json(directory / "run.json", run)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/smoke.json")
    parser.add_argument("--output", type=Path, default=ROOT / "runs")
    parser.add_argument("--authorize-live", action="store_true")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
    else:
        try:
            directory = run_batch(args.config, args.output, args.authorize_live)
            print(directory)
            states = [json.loads(p.read_text(encoding="utf-8")) for p in directory.glob("trial-*/checkpoint.json")]
            config, _ = load_config(args.config)
            if len(states) != config["trials"] or any(s.get("status") != "complete" for s in states):
                parser.exit(1, "Batch incomplete; checkpoints and partial exports preserved.\n")
        except (ValueError, KeyError, OSError) as error:
            parser.exit(2, f"Experiment configuration rejected: {type(error).__name__}\n")


if __name__ == "__main__":
    main()
