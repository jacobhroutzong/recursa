"""Re-record the published Task Management build with its acceptance scenarios."""
from hashlib import sha256
import json
from pathlib import Path
from shutil import copyfile
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recursa.browser_checks import check_application

CHAPTERS = {
    "required-title": ("Create a task", {
        3: "Submit a blank title. The error appears and the list stays empty.",
        4: "Enter “Write notes” in the task title field.",
        6: "Submit the form. The new task appears in the list.",
    }),
    "toggle-and-persist": ("Complete and reload", {
        2: "Create “Persistent task.”",
        4: "Check the task. Chromium verifies its completed state.",
        6: "Reload the page. The same task is still checked.",
        8: "Toggle it again. Chromium verifies that it is active.",
    }),
    "combined-filters": ("Combine status and search", {
        5: "Create two tasks and mark Alpha complete.",
        8: "Select Completed. Alpha remains visible and active Beta is excluded.",
        10: "Search for “lPh.” The case-insensitive substring still matches Alpha.",
        13: "Search for “Beta” with Completed selected. The empty state appears.",
    }),
    "keyboard-mobile-task-controls": ("Use the keyboard on mobile", {
        1: "Enter a title at the 390-pixel mobile viewport.",
        2: "Press Tab to focus Add task.",
        4: "Press Enter to add the task.",
        7: "Press Space on the focused checkbox. The task is checked and the main region is visible.",
    }),
}


def capture():
    studio = ROOT / "apps/studio"
    run = json.loads((studio / "generated-task.json").read_bytes())
    scenario_bytes = (ROOT / "examples/specs/tasks-local-acceptance.json").read_bytes()
    scenarios = json.loads(scenario_bytes)
    if [scenario["id"] for scenario in scenarios] != list(CHAPTERS):
        raise ValueError("The replay chapters must match the reviewed scenarios")
    destination = studio / "assets/task-replay"
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="task-replay-", dir=cache) as directory:
        work = Path(directory)
        build = work / "app"
        build.mkdir()
        artifacts = {artifact["path"]: artifact for artifact in run["artifacts"]}
        if set(artifacts) != {"index.html", "app.js", "styles.css"}:
            raise ValueError("Expected the three published Task Management files")
        for name, artifact in artifacts.items():
            content = artifact["content"].encode("utf-8")
            if sha256(content).hexdigest() != artifact["sha256"]:
                raise ValueError(f"Published artifact hash differs for {name}")
            (build / name).write_bytes(content)
        frames = work / "frames"
        report = check_application(build, scenarios, capture_directory=frames)
        if report["status"] != "passed":
            raise RuntimeError(f"Replay capture did not pass verification: {report}")
        chapters = []
        for check in report["checks"]:
            key = check["scenario_id"]
            title, captions = CHAPTERS[key]
            chapter = {"id": key, "title": title, "checked_steps": check["completed_steps"], "frames": []}
            for step, caption in captions.items():
                name = f"{key}-{step}.png"
                image = frames / name
                chapter["frames"].append({
                    "file": name, "step": step, "caption": caption,
                    "sha256": sha256(image.read_bytes()).hexdigest(),
                })
            chapters.append(chapter)
        destination.mkdir(exist_ok=True, parents=True)
        for chapter in chapters:
            for frame in chapter["frames"]:
                copyfile(frames / frame["file"], destination / frame["file"])
        (destination / "manifest.json").write_text(json.dumps({
            "run_id": run["id"], "browser": report["browser"],
            "scenarios_sha256": sha256(scenario_bytes).hexdigest(),
            "artifacts": {name: artifact["sha256"] for name, artifact in artifacts.items()},
            "chapters": chapters,
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"Captured {sum(len(c['frames']) for c in chapters)} verified frames in {len(chapters)} chapters")


if __name__ == "__main__":
    capture()
