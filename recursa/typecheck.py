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
        react = any(a['path'].endswith('.tsx') or re.search(r'''(?:from|import)\s*['"]react(?:-dom)?(?:/[^'"]*)?['"]''', a['content']) for a in sources)
        trusted_files, paths = [], {}
        if react:
            vendor = Path(__file__).resolve().parents[1] / 'tooling/frontend/node_modules'
            packages = {'@types/react': ('19.3.0', ['index.d.ts', 'global.d.ts', 'jsx-runtime.d.ts', 'jsx-dev-runtime.d.ts']),
                        '@types/react-dom': ('19.3.0', ['index.d.ts', 'client.d.ts']),
                        'csstype': ('3.2.2', ['index.d.ts'])}
            try:
                for package, (expected, files) in packages.items():
                    folder = vendor / package
                    if not folder.resolve().is_relative_to(vendor.resolve()) or json.loads((folder / 'package.json').read_text())['version'] != expected:
                        raise ValueError('Unpinned React declarations')
                    for name in files:
                        origin = folder / name
                        if not origin.resolve().is_relative_to(folder.resolve()):
                            raise ValueError('Declaration symlink escape')
                        target = root / 'trusted-types' / package / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(origin.read_bytes())
                        trusted_files.append(target.relative_to(root).as_posix())
                paths = {name: ['./trusted-types/' + package + '/' + file] for name, package, file in (
                    ('react', '@types/react', 'index.d.ts'), ('react/jsx-runtime', '@types/react', 'jsx-runtime.d.ts'),
                    ('react/jsx-dev-runtime', '@types/react', 'jsx-dev-runtime.d.ts'),
                    ('react-dom', '@types/react-dom', 'index.d.ts'), ('react-dom/client', '@types/react-dom', 'client.d.ts'),
                    ('csstype', 'csstype', 'index.d.ts'))}
            except (OSError, ValueError, KeyError):
                return {'status': 'unavailable', 'checks': [{'path': a['path'], 'kind': 'typescript', 'status': 'unavailable'} for a in sources],
                        'typecheck_success': None, 'diagnostic': 'Pinned optional React declarations unavailable'}
        # Generated tsconfig/package files, extensions, plugins and package scripts
        # are never loaded. noResolve fixes the source-file set to these artifacts.
        config = {"compilerOptions": {"strict": True, "noEmit": True, "noResolve": True,
                   "types": [], "target": "ES2022", "module": "ESNext", "moduleResolution": "Bundler",
                   "jsx": "react-jsx" if react else "preserve", "skipLibCheck": False,
                   "allowSyntheticDefaultImports": True, "paths": paths},
                  "files": ["source/" + a["path"] for a in sources] + trusted_files}
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
