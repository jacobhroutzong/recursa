"""Run actual tests and save source-bound evidence for a release."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recursa.progress import source_digest


if __name__ == "__main__":
    before = source_digest()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    after = source_digest()
    if before != after:
        raise SystemExit("Source changed during tests; no release evidence written")
    evidence = {"total": result.testsRun, "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
                "failed": len(result.failures) + len(result.errors), "skipped": len(result.skipped),
                "verified_at": datetime.now(timezone.utc).isoformat(), "source_digest": after,
                "scope": "Offline fixtures and deterministic checks; no genuine model inference"}
    path = ROOT / ".cache/test-evidence.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
