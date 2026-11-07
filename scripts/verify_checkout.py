"""Verify CPU experiment resume and the HTTP replay from a standard-library checkout."""
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    suite = unittest.TestSuite(
        unittest.TestLoader().discover(str(ROOT / "tests"), pattern=pattern)
        for pattern in ("test_experiments.py", "test_server.py")
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() and not result.skipped else 1


if __name__ == "__main__":
    raise SystemExit(main())
