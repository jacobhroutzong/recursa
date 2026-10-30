# Offline application verification

Section 5 now has an executable local verification lane: validated source → pinned TypeScript checks → production bundling → independently authored Chromium scenarios → optional bounded repair → complete recheck. The provider adapter does not yet invoke this lane automatically. No genuine inference has been run.

Install optional tooling once (Node.js required):

```powershell
npm ci --ignore-scripts --prefix tooling/typecheck
npm ci --ignore-scripts --prefix tooling/frontend
npm ci --ignore-scripts --prefix tooling/browser
node tooling/browser/node_modules/playwright/cli.js install chromium
```

Run the human-authored task-app fixture with one command:

```powershell
python -m recursa.offline --output runs/task-fixture-001
```

Use a fresh output directory for each run. The command exits nonzero on failure or incomplete verification. `application-report.json` contains source artifacts, declared provenance, actual stage results and repair status. Per-pass reports and uniquely named build directories preserve earlier failures. Source and output SHA-256 hashes identify inputs and results. This is an engineering fixture, not an RLM-generated example, research measurement or benchmark comparison.

The four authored scenarios check blank-title rejection and creation, toggling and persistence after reload, combined text/status filtering with an empty state, and keyboard interactions/navigation at a mobile viewport. They exercise the five task-spec requirement IDs, but do not establish complete accessibility or general requirement satisfaction. Artifact references are declared provenance; satisfaction remains null.

## Boundaries

`recursa.build.build_application` uses esbuild 0.28.2 with an in-memory source resolver. Only validated artifact-local modules and stylesheets resolve. It does not install application packages, read generated tsconfig files, execute package scripts or evaluate application JavaScript in Node. The current build lane does not support React/package dependencies or arbitrary asset pipelines. Build success is not type safety or functional success.

`recursa.browser_checks.check_application` uses Playwright 1.64.1 and Chromium's enabled sandbox with a new context per scenario. It serves an allowlisted build directory on an ephemeral loopback origin. External requests, writes, service workers, WebSockets, popups and downloads are blocked. Detected prohibited activity and runtime errors fail a scenario. No model-authored evaluation scripts or arbitrary selectors are accepted. This is browser isolation, not a VM: do not use it as a general hostile-code execution service. It is local only; the public replay server has no execution route.

`recursa.pipeline.verify_application` combines the stages and `repair_artifacts`. Repairs are limited to diagnosed existing files, preserve requirement provenance, retain attempt/hash history and rerun verification. Callbacks must use the caller's shared inference budget. The offline CLI supplies no callback and makes no model calls. An automated regression deliberately changes task creation to start completed; measured browser failures trigger one scripted correction, and the complete pipeline then passes. That scripted correction proves repair wiring only.

Each source/build/browser stage has a hard deadline of 15/30/45 seconds, respectively, with at most ten repair attempts (zero by default). There is no whole-pipeline process budget yet. Missing tools/browser are unmeasured, not successful. Linting, standalone generated-app unit tests, a dedicated accessibility audit, provider-budget integration and model-backed generation/repair remain open section-5 work.
