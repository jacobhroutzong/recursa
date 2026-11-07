"""Prepare an allowlisted CPU-only Space payload; never upload the workspace."""
import json
from pathlib import Path
import shutil
import sys
from tempfile import mkdtemp

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
    releases = ROOT / ".cache/space-releases"
    releases.mkdir(exist_ok=True, parents=True)
    destination = Path(mkdtemp(prefix=progress["source_digest"][:16] + "-", dir=releases))
    paths = [ROOT / "Dockerfile", ROOT / "apps/studio/index.html", public / "progress.json"]
    paths.extend(ROOT / "apps/studio" / name for name in ("playground.json", "generated-task.json", "task-comparison.json", "comparison-series.json", "repair-series.json", "assets/task-preview.png", "assets/generated-task-preview.png"))
    paths.append(ROOT / "apps/studio/benchmark-traces.json")
    paths.append(ROOT / "apps/studio/security-checks.json")
    replay = ROOT / "apps/studio/assets/task-replay"
    paths.append(replay / "manifest.json")
    paths.extend(replay.glob("*.png"))
    paths.extend((ROOT / "recursa").glob("*.py"))
    paths.extend((ROOT / "traces/public").glob("*.json"))
    paths.append(ROOT / "deploy/space/README.md")
    for path in paths:
        if path.is_symlink() or path.resolve(strict=True) != path or not path.is_file():
            raise ValueError(f"Release input must be a regular file inside the allowlist: {path.name}")
        target = destination / ("README.md" if path == ROOT / "deploy/space/README.md" else path.relative_to(ROOT))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    (ROOT / ".cache/release-location.json").write_text(json.dumps({"path": str(destination), "source_digest": progress["source_digest"]}), encoding="utf-8")
    print(f"Space payload: {len(paths)} files at {destination}")
    print(f"Release tests: {progress['tests']['passed']} passed; {progress['tests']['skipped']} skipped")
