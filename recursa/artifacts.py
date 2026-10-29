"""Validate a structured web-source manifest before writing any files."""
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath


def validate_artifacts(value, requirement_ids):
    if not isinstance(value, dict) or not isinstance(value.get("artifacts"), list) or not 1 <= len(value["artifacts"]) <= 64:
        raise ValueError("Expected a JSON object with 1–64 artifacts")
    verified, seen, size = [], set(), 0
    for artifact in value["artifacts"]:
        if not isinstance(artifact, dict):
            raise ValueError("Artifacts must be objects")
        path = artifact.get("path", "")
        if not isinstance(path, str) or not path or any(c in path for c in '\\:<>"|?*') or any(ord(c) < 32 for c in path):
            raise ValueError("Invalid artifact path")
        parts = path.split("/")
        if PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute() or any(p in ("", ".", "..") or p.startswith(".") or p.endswith((" ", ".")) for p in parts):
            raise ValueError("Artifact path must be a clean relative path")
        if any(p.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))} for p in parts):
            raise ValueError("Reserved artifact filename")
        if path.casefold() == "artifact-manifest.json" or Path(path).suffix not in {".ts", ".tsx", ".js", ".jsx", ".json", ".html", ".css", ".md"} or path.casefold() in seen:
            raise ValueError("Unsupported or duplicate artifact path")
        seen.add(path.casefold())
        content = artifact.get("content")
        refs = artifact.get("requirements")
        if not isinstance(content, str) or not isinstance(refs, list) or not refs or any(not isinstance(r, str) or r not in requirement_ids for r in refs):
            raise ValueError("Each artifact requires source and known requirement IDs")
        for field in ("imports", "exports", "assumptions"):
            if not isinstance(artifact.get(field, []), list) or any(not isinstance(v, str) for v in artifact.get(field, [])):
                raise ValueError("Artifact metadata must be string lists")
        size += len(content.encode())
        if size > 1_000_000:
            raise ValueError("Artifact content exceeds one megabyte")
        verified.append({"path": path, "content": content, "requirements": refs,
                         "imports": artifact.get("imports", []), "exports": artifact.get("exports", []),
                         "assumptions": artifact.get("assumptions", []), "sha256": hashlib.sha256(content.encode()).hexdigest()})
    return verified


def save_artifacts(directory, artifacts):
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for artifact in artifacts:
        target = (root / artifact["path"]).resolve()
        if not target.is_relative_to(root):
            raise ValueError("Artifact escapes workspace")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(artifact["content"], encoding="utf-8")
    manifest = [{key: value for key, value in artifact.items() if key != "content"} for artifact in artifacts]
    (root / "artifact-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
