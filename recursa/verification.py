"""Non-executing source checks and declared coverage for synthesis artifacts.

This module never runs generated applications, installs dependencies or invokes
package scripts. Syntax checks cannot establish functionality or satisfaction.
"""
import json
import os
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import time


class ScriptCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.scripts = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            attributes = dict(attrs)
            self.current = {"source": "", "src": attributes.get("src"), "type": attributes.get("type", "").lower()}

    def handle_data(self, data):
        if self.current is not None:
            self.current["source"] += data

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.current is not None:
            self.scripts.append(self.current)
            self.current = None


def declared_coverage(spec, artifacts):
    references = {r["id"]: [] for r in spec["requirements"]}
    for artifact in artifacts:
        for key in artifact["requirements"]:
            references[key].append(artifact["path"])
    return {"kind": "declared-provenance-only", "references": references,
            "referenced_requirements": sum(bool(v) for v in references.values()),
            "total_requirements": len(references),
            "unreferenced": [key for key, paths in references.items() if not paths],
            "satisfaction_rate": None,
            "limitation": "Artifact references are declarations, not independently verified acceptance criteria."}


def _reject_constant(value):
    raise ValueError("Nonstandard JSON constant")


def check_sources(artifacts, max_seconds=15, node_executable=None, typescript_directory=None, scratch_directory=None):
    if type(max_seconds) not in (int, float) or not 0 < max_seconds <= 300:
        raise ValueError("Static verification needs a finite timeout up to 300 seconds")
    started = time.monotonic()
    node = node_executable or shutil.which("node")
    checks = []

    def json_check(path, source):
        try:
            json.loads(source, parse_constant=_reject_constant)
            checks.append({"path": path, "kind": "json-parse", "status": "passed"})
        except (ValueError, TypeError):
            checks.append({"path": path, "kind": "json-parse", "status": "failed", "diagnostic": "Invalid strict JSON"})

    def js_check(path, source, module=True):
        if not node:
            checks.append({"path": path, "kind": "javascript-syntax", "status": "unavailable"})
            return
        remaining = max_seconds - (time.monotonic() - started)
        if remaining <= 0:
            checks.append({"path": path, "kind": "javascript-syntax", "status": "timeout"})
            return
        environment = dict(os.environ)
        # Do not permit inherited Node preload options to execute code during parsing.
        environment.pop("NODE_OPTIONS", None)
        environment.pop("NODE_PATH", None)
        try:
            result = subprocess.run([str(node), "--check", "--input-type=" + ("module" if module else "commonjs")],
                                    input=source, text=True, capture_output=True, timeout=remaining, env=environment)
            check = {"path": path, "kind": "javascript-syntax", "status": "passed" if result.returncode == 0 else "failed"}
            if result.returncode:
                check["diagnostic"] = result.stderr[-4000:]
            checks.append(check)
        except subprocess.TimeoutExpired:
            checks.append({"path": path, "kind": "javascript-syntax", "status": "timeout"})
        except OSError:
            checks.append({"path": path, "kind": "javascript-syntax", "status": "unavailable"})

    for artifact in artifacts:
        path, source = artifact["path"], artifact["content"]
        suffix = Path(path).suffix
        if suffix == ".json":
            json_check(path, source)
        elif suffix == ".js":
            js_check(path, source)
        elif suffix == ".html":
            collector = ScriptCollector()
            collector.feed(source)
            collector.close()
            for index, script in enumerate(collector.scripts):
                label = f"{path}#script-{index + 1}"
                if script["src"] is not None:
                    checks.append({"path": label, "kind": "external-script", "status": "not-run"})
                elif script["type"] in {"application/json", "application/ld+json"}:
                    json_check(label, script["source"])
                elif script["type"] in {"", "module", "text/javascript", "application/javascript"}:
                    js_check(label, script["source"], module=script["type"] == "module")
            if not collector.scripts:
                checks.append({"path": path, "kind": "html-functional-validation", "status": "not-run"})
        elif suffix in {".ts", ".tsx"} and typescript_directory is not None:
            pass
        else:
            checks.append({"path": path, "kind": "source-validation", "status": "not-run",
                           "diagnostic": "No pinned typechecker/linter configured for this source type"})
    type_result = None
    if typescript_directory is not None and any(Path(a["path"]).suffix in {".ts", ".tsx"} for a in artifacts):
        from recursa.typecheck import check_types
        remaining = max_seconds - (time.monotonic() - started)
        if remaining > 0:
            type_result = check_types(artifacts, typescript_directory, max_seconds=remaining, scratch_directory=scratch_directory)
            checks.extend(type_result["checks"])
        else:
            type_result = {"typecheck_success": False}
            checks.extend({"path": a["path"], "kind": "typescript", "status": "timeout"} for a in artifacts if Path(a["path"]).suffix in {".ts", ".tsx"})
    failures = any(c["status"] in {"failed", "timeout"} for c in checks)
    category = "static" if type_result is not None else "syntax"
    return {"status": category + "-failed" if failures else category + "-passed" if any(c["status"] == "passed" for c in checks) else "not-checked",
            "checks": checks, "duration_ms": round((time.monotonic() - started) * 1000, 3),
            "tool": {"javascript": Path(node).name if node else None},
            "build_success": None, "typecheck_success": type_result["typecheck_success"] if type_result else None, "functional_success": None,
            "unit_test_pass_rate": None, "end_to_end_pass_rate": None,
            "limitations": ["Static source checks only; no dependencies installed, production build or generated application executed.",
                            "HTML parsing is permissive; classic scripts use Node CommonJS syntax rules, which differ from browser script rules."]}
