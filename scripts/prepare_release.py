"""Prepare an allowlisted CPU-only Space payload; never upload the workspace."""
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recursa.progress import build_progress


if __name__ == "__main__":
    progress = build_progress()
    if not progress["tests"] or progress["tests"]["failed"]:
        raise SystemExit("Passing, current test evidence is required before release packaging")
    public = ROOT / "public"
    public.mkdir(exist_ok=True)
    (public / "progress.json").write_text(json.dumps(progress, indent=2), encoding="utf-8")
    destination = ROOT / ".cache/space-releases" / progress["source_digest"][:16]
    paths = [ROOT / "Dockerfile", ROOT / "apps/studio/index.html", public / "progress.json"]
    paths.extend((ROOT / "recursa").glob("*.py"))
    paths.extend((ROOT / "traces/public").glob("*.json"))
    for path in paths:
        target = destination / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    shutil.copyfile(ROOT / "deploy/space/README.md", destination / "README.md")
    (ROOT / ".cache/release-location.json").write_text(json.dumps({"path": str(destination), "source_digest": progress["source_digest"]}), encoding="utf-8")
    print(f"Space payload: {len(paths)} files at {destination}")
    print(f"Release tests: {progress['tests']['passed']} passed; {progress['tests']['skipped']} skipped")
