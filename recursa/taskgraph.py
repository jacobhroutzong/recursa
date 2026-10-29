"""Model-selected synthesis plans with deterministic dependency/state checks."""
from copy import deepcopy
from pathlib import Path
import re

from recursa.artifacts import save_artifacts, validate_artifacts
from recursa.engine import _ordered
from recursa.experiments import atomic_json


class TaskGraph:
    KINDS = {"design", "contract", "data", "component", "view", "state", "navigation", "integration", "test", "assembly", "other"}

    def __init__(self, requirement_ids, directory, record=lambda *args: None):
        self.requirement_ids = set(requirement_ids)
        self.directory = Path(directory)
        self.record = record
        self.tasks = {}
        self.artifacts = {}

    def set_plan(self, tasks):
        if not isinstance(tasks, list) or not 1 <= len(tasks) <= 128:
            raise ValueError("A synthesis plan needs 1–128 tasks")
        planned = {}
        for task in tasks:
            if not isinstance(task, dict):
                raise ValueError("Each task must be an object")
            key = task.get("id")
            if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key) or key in planned:
                raise ValueError("Task IDs must be safe and unique")
            if task.get("kind") not in self.KINDS or not isinstance(task.get("label"), str) or not task["label"].strip():
                raise ValueError("Each task requires a label and supported kind")
            refs = task.get("requirements")
            dependencies = task.get("depends_on", [])
            if not isinstance(refs, list) or not refs or any(not isinstance(r, str) or r not in self.requirement_ids for r in refs):
                raise ValueError("Tasks must reference known requirements")
            if not isinstance(dependencies, list) or any(not isinstance(d, str) for d in dependencies):
                raise ValueError("Task dependencies must be IDs")
            planned[key] = {"id": key, "label": task["label"], "kind": task["kind"],
                            "requirements": list(refs), "depends_on": list(dependencies),
                            "status": "pending", "artifact_paths": []}
        if any(dep not in planned for task in planned.values() for dep in task["depends_on"]):
            raise ValueError("Unknown task dependency")
        _ordered({key: task["depends_on"] for key, task in planned.items()})
        # Adaptive refinement can replace pending tasks but cannot rewrite history.
        for key, previous in self.tasks.items():
            if previous["status"] != "pending":
                candidate = planned.get(key)
                if not candidate or any(candidate[field] != previous[field] for field in ("id", "label", "kind", "requirements", "depends_on")):
                    raise ValueError("Started tasks cannot be removed or redefined")
                planned[key] = deepcopy(previous)
        self.tasks = planned
        self._persist()
        self.record("plan", "Set or refine synthesis task graph", {"task_ids": list(planned)})
        return {"task_order": _ordered({key: task["depends_on"] for key, task in planned.items()})}

    def begin(self, task_id):
        task = self.tasks[task_id]
        if task["status"] != "pending" or any(self.tasks[dep]["status"] != "produced" for dep in task["depends_on"]):
            raise ValueError("Task cannot start before its dependencies produce artifacts")
        task["status"] = "running"
        self._persist()
        self.record("task", "Start synthesis task", {"task_id": task_id, "requirements": task["requirements"]})
        return deepcopy(task)

    def submit(self, task_id, output):
        task = self.tasks[task_id]
        if task["status"] != "running":
            raise ValueError("Only a running task may submit output")
        artifacts = validate_artifacts(output, set(task["requirements"]))
        existing = {p.casefold() for p in self.artifacts}
        if any(a["path"].casefold() in existing for a in artifacts):
            raise ValueError("A task cannot overwrite another produced artifact")
        save_artifacts(self.directory / "intermediate" / task_id, artifacts)
        for artifact in artifacts:
            self.artifacts[artifact["path"]] = artifact
        task["artifact_paths"] = [a["path"] for a in artifacts]
        task["status"] = "produced"
        self._persist()
        self.record("artifact", "Persist structured task output", {"task_id": task_id, "artifact_paths": task["artifact_paths"]})
        return {"task_id": task_id, "status": "produced", "artifact_paths": list(task["artifact_paths"])}

    def contracts(self, task_ids):
        if not isinstance(task_ids, list) or not 1 <= len(task_ids) <= 16:
            raise ValueError("Select 1–16 dependency tasks")
        result = []
        for key in task_ids:
            task = self.tasks[key]
            if task["status"] != "produced":
                raise ValueError("Contracts are unavailable until task output is produced")
            for path in task["artifact_paths"]:
                artifact = self.artifacts[path]
                result.append({k: artifact[k] for k in ("path", "exports", "imports", "requirements", "sha256")})
        # Contract declarations, not independently typechecked interfaces.
        import json
        if len(json.dumps(result)) > 12000:
            raise ValueError("Contract observation too large; select fewer tasks")
        self.record("context", "Read declared dependency contracts", {"task_ids": task_ids})
        return result

    def select_outputs(self, paths):
        if not isinstance(paths, list) or not paths or any(not isinstance(p, str) or p not in self.artifacts for p in paths):
            raise ValueError("Final artifact paths must reference produced task outputs")
        if len(set(paths)) != len(paths):
            raise ValueError("Final artifact paths must be unique")
        return [deepcopy(self.artifacts[path]) for path in paths]

    def _persist(self):
        atomic_json(self.directory / "task-graph.json", {"tasks": list(self.tasks.values())})
