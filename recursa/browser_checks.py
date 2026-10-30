"""Declarative Playwright checks in fresh, local-only browser contexts.

Scenarios must be independently authored/reviewed acceptance tests. This module
does not infer requirements from generated source and never executes Node code
provided by an application. Chromium is still an execution boundary, not a VM.
"""
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.64.1"
ACTIONS = {"fill", "click", "select", "press", "reload", "audit_accessibility", "expect_text", "expect_count", "expect_visible", "expect_value", "expect_checked"}
ROLES = {"button", "textbox", "searchbox", "combobox", "checkbox", "heading", "list", "listitem", "alert", "status", "link", "radio", "tab", "table", "cell", "row", "navigation", "form"}
KEYS = {"Enter", "Tab", "Space", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"}


def _path(value):
    return (isinstance(value, str) and 0 < len(value) <= 240 and not PurePosixPath(value).is_absolute()
            and not any(c in value for c in "\\:\x00") and all(p not in {"", ".", ".."} for p in value.split("/")))


def validate_scenarios(scenarios):
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 32:
        raise ValueError("Provide 1–32 independently authored scenarios")
    seen = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict) or set(scenario) - {"id", "requirements", "source_path", "steps", "viewport"}:
            raise ValueError("Unsupported scenario fields")
        key = scenario.get("id")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key) or key in seen:
            raise ValueError("Scenario IDs must be safe and unique")
        seen.add(key)
        refs = scenario.get("requirements")
        if not isinstance(refs, list) or not refs or len(refs) > 32 or any(not isinstance(r, str) or not r.strip() or len(r) > 128 for r in refs):
            raise ValueError("Scenarios require bounded requirement references")
        if "source_path" in scenario and not _path(scenario["source_path"]):
            raise ValueError("Scenario source_path must be a clean relative path")
        if "viewport" in scenario:
            viewport = scenario["viewport"]
            if not isinstance(viewport, dict) or set(viewport) != {"width", "height"} or any(type(viewport[d]) is not int or not 240 <= viewport[d] <= 1920 for d in viewport):
                raise ValueError("Viewport dimensions must be integers from 240 to 1920")
        steps = scenario.get("steps")
        if not isinstance(steps, list) or not 1 <= len(steps) <= 100:
            raise ValueError("Each scenario needs 1–100 steps")
        for step in steps:
            if not isinstance(step, dict) or set(step) - {"action", "target", "value", "count", "checked"} or step.get("action") not in ACTIONS:
                raise ValueError("Unsupported declarative action")
            action = step["action"]
            if action in {"reload", "audit_accessibility"}:
                if set(step) != {"action"}:
                    raise ValueError("Reload accepts no extra fields")
                continue
            target = step.get("target")
            if not isinstance(target, dict):
                raise ValueError("Actions require an accessible role or test_id target")
            if set(target) == {"test_id"}:
                if not isinstance(target["test_id"], str) or not 1 <= len(target["test_id"]) <= 200:
                    raise ValueError("Invalid test ID")
            elif set(target) in ({"role"}, {"role", "name"}):
                if target["role"] not in ROLES or ("name" in target and (not isinstance(target["name"], str) or len(target["name"]) > 200)):
                    raise ValueError("Invalid accessible target")
            else:
                raise ValueError("Selectors, JavaScript and arbitrary target fields are not allowed")
            if action in {"fill", "select", "press", "expect_text", "expect_value"}:
                if not isinstance(step.get("value"), str) or len(step["value"]) > 4000:
                    raise ValueError("Action requires bounded text value")
            if action == "press" and step["value"] not in KEYS:
                raise ValueError("Only bounded application keyboard actions are allowed")
            if action == "expect_count" and (type(step.get("count")) is not int or not 0 <= step["count"] <= 1000):
                raise ValueError("Count assertion requires integer 0–1000")
            if action == "expect_checked" and type(step.get("checked")) is not bool:
                raise ValueError("Checked assertion requires a boolean")
    if len(json.dumps(scenarios)) > 300000:
        raise ValueError("Scenario payload is too large")
    return scenarios


def _unmeasured(status, classification):
    return {"status": status, "checks": [], "functional_success": None, "end_to_end_pass_rate": None,
            "e2e_pass_rate": None, "build_success": None, "error_classification": classification,
            "scope": "Independently authored scenarios only; not general application correctness"}


def check_application(build_dir, scenarios, *, tool_directory=None, max_seconds=45):
    """Run reviewed scenarios against a dedicated ephemeral static origin.

    Missing tools/browser are unmeasured. Actual failed assertions, prohibited
    activity, or a hard process deadline are failed checks. No provider calls.
    """
    scenarios = validate_scenarios(scenarios)
    if type(max_seconds) not in (int, float) or not math.isfinite(max_seconds) or not 1 <= max_seconds <= 300:
        raise ValueError("Functional checking requires a finite timeout from 1–300 seconds")
    directory = Path(build_dir).resolve()
    if not directory.is_dir() or not (directory / "index.html").is_file():
        raise ValueError("Functional checking requires a built directory with index.html")
    files, size = [], 0
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError("Built applications cannot contain symlinks")
        if path.is_file():
            if not path.resolve().is_relative_to(directory):
                raise ValueError("Built file escapes its root")
            size += path.stat().st_size
            files.append(path.relative_to(directory).as_posix())
    if len(files) > 256 or size > 10000000:
        raise ValueError("Built application exceeds functional-check size limits")
    tools = Path(tool_directory) if tool_directory is not None else ROOT / "tooling/browser/node_modules"
    node = shutil.which("node")
    try:
        versions = [json.loads((tools / name / "package.json").read_text())["version"] for name in ("playwright", "playwright-core")]
    except (OSError, ValueError, KeyError):
        versions = []
    if not node or versions != [VERSION, VERSION]:
        return _unmeasured("unavailable", "PinnedPlaywrightUnavailable")
    environment = {key: value for key, value in os.environ.items()
                   if not any(word in key.upper() for word in ("TOKEN", "API_KEY", "SECRET", "PASSWORD", "AUTHORIZATION"))}
    environment.pop("NODE_OPTIONS", None)
    environment.pop("NODE_PATH", None)
    payload = {"build_dir": str(directory), "files": files, "scenarios": scenarios,
               "tool_directory": str(tools.resolve()), "max_seconds": max_seconds}
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    process = subprocess.Popen([node, str(ROOT / "scripts/browser_checks.mjs")], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment, **options)
    try:
        stdout, _ = process.communicate(json.dumps(payload), timeout=max_seconds)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        return {"status": "timeout", "functional_success": False, "end_to_end_pass_rate": 0,
                "e2e_pass_rate": 0, "build_success": None,
                "checks": [{"path": s.get("source_path", "index.html"), "kind": "browser", "scenario_id": s["id"],
                            "requirements": s["requirements"], "status": "timeout", "diagnostic": "Functional-check process deadline exceeded"} for s in scenarios]}
    try:
        report = json.loads(stdout)
        if len(stdout) > 1000000 or not isinstance(report, dict) or not isinstance(report.get("checks"), list):
            raise ValueError("Invalid result")
    except (ValueError, TypeError):
        return _unmeasured("error", "BrowserHarnessFailed")
    return report
