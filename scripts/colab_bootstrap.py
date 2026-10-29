"""Portable notebook entry point; no GPUs, provider calls, or pip installs needed."""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/smoke.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    # The default core is standard-library-only. This same command works in Colab,
    # a local venv, and Windows. Never upgrade the notebook's global dependencies.
    subprocess.run([sys.executable, "-m", "recursa.experiments", "--config", args.config,
                    "--output", str(args.output.resolve())], cwd=root, check=True)


if __name__ == "__main__":
    main()
