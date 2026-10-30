import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from recursa.build import build_application, DEFAULT_TOOLS
from recursa.experiments import ROOT


def fixture():
    return [{"path": path, "content": source, "requirements": ["R1"]} for path, source in {
        "index.html": '<!doctype html><html><head><link rel="stylesheet" href="src/style.css"></head><body><main id="app"></main><script type="module" src="src/main.ts"></script></body></html>',
        "src/main.ts": 'import { label } from "./model"; document.querySelector("#app")!.textContent = label;',
        "src/model.ts": 'export const label: string = "Built task application";',
        "src/style.css": 'body { color: rgb(10, 20, 30); }'
    }.items()]


class BuildBoundaryTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".cache")
        self.addCleanup(self.temp.cleanup)

    def test_missing_toolchain_is_not_a_build_success(self):
        result = build_application(fixture(), self.temp.name, tool_directory=Path(self.temp.name) / "missing")
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["build_success"])
        self.assertIsNone(result["functional_success"])

    def test_html_and_artifact_path_boundaries(self):
        artifacts = fixture()
        artifacts[0]["content"] = '<script type="module" src="https://invalid.example/app.js"></script>'
        result = build_application(artifacts, self.temp.name)
        self.assertFalse(result["build_success"])
        self.assertEqual(result["checks"][0]["path"], "index.html")
        artifacts = fixture()
        artifacts[1]["path"] = "../escape.ts"
        with self.assertRaises(ValueError):
            build_application(artifacts, self.temp.name)


@unittest.skipUnless((DEFAULT_TOOLS / "esbuild/package.json").exists() and shutil.which("node"), "Install tooling/frontend locked dependencies for production-build tests")
class ActualBuildTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".cache")
        self.addCleanup(self.temp.cleanup)

    def test_actual_typed_multifile_bundle_and_fresh_dist(self):
        result = build_application(fixture(), self.temp.name)
        self.assertTrue(result["build_success"], result)
        dist = Path(result["dist_path"])
        self.assertTrue((dist / "assets/entry-0.css").exists())
        self.assertTrue((dist / "assets/entry-1.js").exists())
        self.assertIn("./assets/entry-1.js", (dist / "index.html").read_text())
        self.assertIsNone(result["functional_success"])
        self.assertTrue(all(len(a["sha256"]) == 64 for a in result["outputs"]))
        self.assertIn("src/model.ts", [c["path"] for c in result["checks"]])
        second = build_application(fixture(), self.temp.name)
        self.assertNotEqual(second["dist_path"], result["dist_path"])

    def test_import_escape_missing_import_and_invalid_syntax_fail(self):
        for source in ('import "../../secret.json";', 'import "./missing";', 'const = ;', 'import "node:fs";', 'import "https://invalid.example/source.js";'):
            artifacts = fixture()
            artifacts[1]["content"] = source
            result = build_application(artifacts, self.temp.name)
            self.assertFalse(result["build_success"], result)
            self.assertIn("src/main.ts", [c["path"] for c in result["checks"]])
            self.assertIsNone(result["dist_path"])

    def test_build_never_executes_generated_source_or_configs(self):
        target = Path(self.temp.name) / "MUST_NOT_EXIST"
        artifacts = fixture()
        artifacts[1]["content"] = f'globalThis.NOT_A_REAL_BUILD_API.writeFileSync({json.dumps(str(target))}, "executed"); throw new Error("MUST_NOT_EXECUTE");'
        artifacts.extend([
            {"path": "package.json", "content": '{"scripts":{"build":"SHOULD_NEVER_RUN"}}', "requirements": ["R1"]},
            {"path": "tsconfig.json", "content": '{"extends":"../../secret.json"}', "requirements": ["R1"]}])
        result = build_application(artifacts, self.temp.name)
        self.assertTrue(result["build_success"], result)
        self.assertFalse(target.exists())

    def test_timeout_is_not_a_success(self):
        with patch("recursa.build.subprocess.run", side_effect=subprocess.TimeoutExpired("node", 1)):
            result = build_application(fixture(), self.temp.name)
        self.assertEqual(result["status"], "timeout")
        self.assertFalse(result["build_success"])
