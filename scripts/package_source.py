"""Create a credential-free source ZIP for Colab's upload-once workflow."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def package(target):
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for folder in ("recursa", "scripts", "configs", "examples/specs", "examples/fixtures", "apps/studio", "tests", "docs", "notebooks"):
            for path in sorted((ROOT / folder).rglob("*")):
                if path.is_file() and path.suffix in {".py", ".ps1", ".json", ".html", ".md", ".ipynb", ".mjs", ".ts", ".css"} and "__pycache__" not in path.parts:
                    archive.write(path, "recursa/" + path.relative_to(ROOT).as_posix())
        for name in ("pyproject.toml", "requirements-live.lock", "README.md", "AGENTS.md", "tooling/typecheck/package.json", "tooling/typecheck/package-lock.json", "tooling/frontend/package.json", "tooling/frontend/package-lock.json", "tooling/browser/package.json", "tooling/browser/package-lock.json"):
            path = ROOT / name
            if path.exists():
                archive.write(path, "recursa/" + name)
    return target


if __name__ == "__main__":
    print(package(ROOT / "recursa-source.zip"))
