"""Publish measured release evidence and the ordered implementation ledger."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source_digest():
    digest = hashlib.sha256()
    files = []
    for folder in ("recursa", "tests", "scripts", "apps/studio"):
        files.extend(p for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in {".py", ".html", ".ps1"} and "__pycache__" not in p.parts)
    files.extend(ROOT / name for name in ("requirements-live.lock", "pyproject.toml", "tooling/typecheck/package.json", "tooling/typecheck/package-lock.json"))
    for path in sorted(files):
        if path.exists():
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def build_progress():
    sections = []
    for line in (ROOT / "docs/implementation-progress.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0].split(".")[0].isdigit():
            sections.append({"number": int(cells[0].split(".")[0]), "name": cells[0], "status": cells[1], "evidence": cells[2]})
    if [s["number"] for s in sections] != list(range(1, 22)):
        raise ValueError("Progress ledger must contain sections 1–21 exactly once in order")
    identity = source_digest()
    evidence_path = ROOT / ".cache/test-evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8")) if evidence_path.exists() else None
    if evidence is not None and evidence.get("source_digest") != identity:
        raise ValueError("Code changed after tests; rerun scripts/verify.py before publication")
    return {"schema_version": 1, "updated_at": datetime.now(timezone.utc).isoformat(),
            "phase": "Section 5 · offline synthesis and verification", "source_digest": identity,
            "tests": evidence, "sections": sections,
            "mode": "public-development-preview", "live_inference": False,
            "notice": "Auto-refresh shows the latest published release. This is development progress, not live model inference.",
            "links": {"source": "https://github.com/jacobhroutzong/recursa",
                      "portfolio": "https://jacobroutzong.dev/projects/recursa/",
                      "space": "https://huggingface.co/spaces/jacobroutzong/recursa"}}
