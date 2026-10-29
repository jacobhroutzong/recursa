"""Optional pinned TypeScript checks with a caller-controlled, trusted config."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from recursa.artifacts import validate_artifacts


def check_types(artifacts, compiler_directory, *, max_seconds=15, scratch_directory=None):
    if type(max_seconds) not in (int, float) or not 0 < max_seconds <= 300:
        raise ValueError("Typechecking requires a finite timeout up to 300 seconds")
    ids = {key for artifact in artifacts for key in artifact.get("requirements", [])}
    validated = validate_artifacts({"artifacts": artifacts}, ids)
    sources = [a for a in validated if Path(a["path"]).suffix in {".ts", ".tsx"}]
    if not sources:
        return {"status": "not-run", "checks": [], "typecheck_success": None}
    compiler = Path(compiler_directory)
    node = shutil.which("node")
    try:
        version = json.loads((compiler / "package.json").read_text(encoding="utf-8"))["version"]
    except (ValueError, KeyError, OSError):
        version = None
    if not node or version != "5.9.3" or not (compiler / "bin/tsc").is_file():
        return {"status": "unavailable", "checks": [{"path": a["path"], "kind": "typescript", "status": "unavailable"} for a in sources], "typecheck_success": None}
    if scratch_directory is not None:
        Path(scratch_directory).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_directory) as tmp:
        root = Path(tmp)
        for artifact in sources:
            target = root / "source" / artifact["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(artifact["content"], encoding="utf-8")
        # Generated tsconfig/package files, extensions, plugins and package scripts
        # are never loaded. noResolve fixes the source-file set to these artifacts.
        config = {"compilerOptions": {"strict": True, "noEmit": True, "noResolve": True,
                   "types": [], "target": "ES2022", "module": "ESNext", "moduleResolution": "Bundler",
                   "jsx": "preserve", "skipLibCheck": False},
                  "files": ["source/" + a["path"] for a in sources]}
        (root / "tsconfig.json").write_text(json.dumps(config), encoding="utf-8")
        environment = dict(os.environ)
        environment.pop("NODE_OPTIONS", None)
        environment.pop("NODE_PATH", None)
        try:
            result = subprocess.run([node, str((compiler / "bin/tsc").resolve()), "--project", str(root / "tsconfig.json"), "--pretty", "false"],
                                    cwd=root, capture_output=True, text=True, timeout=max_seconds, env=environment)
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "checks": [{"path": a["path"], "kind": "typescript", "status": "timeout"} for a in sources], "typecheck_success": False}
        diagnostics = (result.stdout + result.stderr).replace(str(root), "<verification>")[-12000:]
        checks = []
        for artifact in sources:
            normalized = artifact["path"].replace("\\", "/")
            implicated = [line for line in diagnostics.splitlines() if "source/" + normalized + "(" in line.replace("\\", "/")]
            checks.append({"path": artifact["path"], "kind": "typescript", "status": "failed" if implicated else "passed" if result.returncode == 0 else "not-verified",
                           **({"diagnostic": "\n".join(implicated)[:4000]} if implicated else {})})
        if result.returncode and not any(c["status"] == "failed" for c in checks):
            checks.append({"path": "<project>", "kind": "typescript", "status": "failed", "diagnostic": diagnostics[:4000]})
        return {"status": "passed" if result.returncode == 0 else "failed", "checks": checks,
                "typecheck_success": result.returncode == 0, "compiler": "typescript@5.9.3",
                "functional_success": None, "build_success": None,
                "limitation": "Static checks with fixed source files only; external dependency resolution, application execution and production builds are not performed."}
