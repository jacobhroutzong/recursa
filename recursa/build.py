"""Controlled production assembly using a pinned optional esbuild toolchain."""
import base64
import hashlib
from html import escape
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import time

from recursa.artifacts import validate_artifacts
from recursa.experiments import atomic_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOOLS = ROOT / "tooling/frontend/node_modules"


class _Entries(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.entries = {}
        self.replacements = []
        self.lines = [0]
        self.inline_script = False
        for index, char in enumerate(source):
            if char == "\n":
                self.lines.append(index + 1)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        field = None
        if tag == "script":
            if attrs.get("type") != "module" or not attrs.get("src"):
                raise ValueError("Production entry scripts must use type=module and a local src")
            field = "src"
        elif tag == "link" and attrs.get("rel", "").lower() == "stylesheet":
            field = "href"
        if field is None:
            return
        source = attrs.get(field, "")
        if not source or source.startswith(("/", "\\")) or ":" in source or "?" in source or "#" in source or "\\" in source:
            raise ValueError("HTML entries must reference local artifact paths")
        source = source.removeprefix("./")
        if any(part in {"", ".", ".."} for part in source.split("/")):
            raise ValueError("HTML entry escapes the artifact set")
        name = f"entry-{len(self.entries)}"
        self.entries[name] = source
        attrs[field] = f"./assets/{name}.{'css' if field == 'href' else 'js'}"
        rewritten = "<" + tag + "".join(" " + key + ("" if value is None else '=\"' + escape(value, quote=True) + '\"') for key, value in attrs.items()) + ">"
        line, column = self.getpos()
        start = self.lines[line - 1] + column
        self.replacements.append((start, start + len(self.get_starttag_text()), rewritten))

    def rewritten(self):
        output = self.source
        for start, end, value in reversed(self.replacements):
            output = output[:start] + value + output[end:]
        return output


def build_application(artifacts, output_dir, *, tool_directory=DEFAULT_TOOLS, max_seconds=30):
    """Return measured build evidence; never run generated modules or package scripts.

    Dist directories are unique per invocation. Unsupported dependencies fail
    explicitly; this initial build lane supports artifact-local browser modules.
    """
    if type(max_seconds) not in (int, float) or not math.isfinite(max_seconds) or not 0 < max_seconds <= 300:
        raise ValueError("Build timeout must be finite and between 0 and 300 seconds")
    if not isinstance(artifacts, list) or any(not isinstance(a, dict) for a in artifacts):
        raise ValueError("Artifacts must be a list of objects")
    refs = {r for a in artifacts for r in a.get("requirements", []) if isinstance(r, str)}
    verified = validate_artifacts({"artifacts": artifacts}, refs)
    inputs = {a["path"]: a for a in verified}
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="build-", dir=output_root))
    dist = directory / "dist"
    started = time.perf_counter()
    report = {"status": "failed", "build_success": False, "functional_success": None,
              "typecheck_success": None, "checks": [], "outputs": [], "dist_directory": None, "dist_path": None,
              "tool": {"name": "esbuild", "required_version": "0.28.2"},
              "limitations": ["Bundling is not typechecking, application execution or functional success.",
                              "Only artifact-local modules and CSS are supported; package dependencies are not installed or resolved."]}

    def finish():
        report["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
        atomic_json(directory / "build-report.json", report)
        return report

    if "index.html" not in inputs:
        report["checks"].append({"path": "index.html", "kind": "production-build", "status": "failed", "diagnostic": "Missing index.html entry point"})
        return finish()
    try:
        parser = _Entries(inputs["index.html"]["content"])
        parser.feed(inputs["index.html"]["content"])
        parser.close()
        if not parser.entries:
            raise ValueError("At least one local module or stylesheet entry is required")
        if any(path not in inputs for path in parser.entries.values()):
            raise ValueError("HTML entry references an unknown artifact")
    except ValueError as error:
        report["checks"].append({"path": "index.html", "kind": "production-build", "status": "failed", "diagnostic": str(error)})
        return finish()
    tools = Path(tool_directory)
    node = shutil.which("node")
    try:
        version = json.loads((tools / "esbuild/package.json").read_text(encoding="utf-8"))["version"]
    except (ValueError, KeyError, OSError):
        version = None
    if node is None or version != "0.28.2":
        report.update(status="unavailable", build_success=None)
        report["checks"].append({"path": "index.html", "kind": "production-build", "status": "unavailable", "diagnostic": "Install the pinned optional frontend toolchain"})
        return finish()
    environment = dict(os.environ)
    for key in ("NODE_OPTIONS", "NODE_PATH", "ESBUILD_BINARY_PATH"):
        environment.pop(key, None)
    payload = {"artifacts": verified, "entries": {"assets/" + key: value for key, value in parser.entries.items()}}
    try:
        result = subprocess.run([node, str(ROOT / "scripts/build_frontend.mjs"), str(tools.resolve())],
                                input=json.dumps(payload), text=True, capture_output=True, timeout=max_seconds,
                                env=environment, cwd=directory)
        response = json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        report["status"] = "timeout"
        report["checks"].append({"path": "index.html", "kind": "production-build", "status": "timeout"})
        return finish()
    except (ValueError, OSError):
        report.update(status="unavailable", build_success=None)
        report["checks"].append({"path": "index.html", "kind": "production-build", "status": "unavailable", "diagnostic": "Bundler helper did not return valid evidence"})
        return finish()
    report["tool"]["version"] = response.get("version")
    if result.returncode != 0 or response.get("status") != "passed":
        for error in response.get("errors", [{"path": "<project>", "text": "Bundler failed"}]):
            report["checks"].append({"path": error.get("path", "<project>"), "kind": "production-build", "status": "failed", "diagnostic": str(error.get("text", "Bundler failed"))[:2000], "line": error.get("line")})
        return finish()
    dist.mkdir()
    outputs = list(response.get("outputs", []))
    outputs.append({"path": "index.html", "content_base64": base64.b64encode(parser.rewritten().encode()).decode()})
    # CSS imported from a script is emitted by esbuild separately; connect it to HTML.
    html_path = next(item for item in outputs if item["path"] == "index.html")
    html = base64.b64decode(html_path["content_base64"]).decode()
    linked = {f"assets/{name}.css" for name, value in parser.entries.items() if value.endswith(".css")}
    for item in outputs:
        if item["path"].endswith(".css") and item["path"] not in linked:
            html = html.replace("</head>", f'<link rel="stylesheet" href="./{escape(item["path"], quote=True)}"></head>', 1)
    html_path["content_base64"] = base64.b64encode(html.encode()).decode()
    for item in outputs:
        relative = PurePosixPath(item["path"])
        if relative.is_absolute() or ".." in relative.parts or "\\" in item["path"]:
            raise ValueError("Bundler produced an invalid output path")
        data = base64.b64decode(item["content_base64"], validate=True)
        target = dist / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        report["outputs"].append({"path": relative.as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    report.update(status="passed", build_success=True, dist_directory=str(dist), dist_path=str(dist))
    checked = {"index.html"}
    checked.update(name.removeprefix("recursa:") for name in response.get("metadata", {}).get("inputs", {}))
    report["checks"].extend({"path": name, "kind": "production-build", "status": "passed"} for name in sorted(checked) if name in inputs)
    report["warnings"] = response.get("warnings", [])
    return finish()
