# Offline application verification

Section 5 now has an executable local verification lane: validated source → pinned TypeScript and fixed AST lint checks → production bundling → independently authored Chromium interaction/unit cases and basic accessibility audits → optional bounded repair → complete recheck. The provider adapter does not yet invoke this lane automatically. No genuine inference has been run.

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

Six independently authored JSON unit cases exercise blank/trimmed titles and case-insensitive, status and combined filtering against `src/model.ts` exports. A trusted harness bundles the referenced modules and calls them inside the isolated browser, never in a host Node process. Cases specify a module, named export, JSON arguments and expected JSON result; no executable test body is accepted. Cases must be pure and independent of order; each fresh context runs the fixture. Missing tools yield a null pass rate. A deliberately wrong expected result is verified to fail.

Linting uses the pinned TypeScript 5.9.3 parser with fixed rules for parse errors, `var`, `debugger`, loose equality and direct `eval`. Comments and string literals are not mistaken for code. No generated lint configuration/plugins run. This small ruleset is not a full ESLint suite or a comprehensive security audit.

Each interaction scenario ends with a fixed basic DOM accessibility audit: document language/title, main landmark, level-one heading, duplicate IDs, visible control names, image alt attributes, positive tabindex and focusability of custom button/checkbox roles. Findings are stored with the scenario. Negative fixtures verify detection. Color contrast, complete accessible-name computation, screen-reader behavior and full WCAG conformance remain outside this audit.

## Boundaries

`recursa.build.build_application` uses esbuild 0.28.2 with an in-memory source resolver. Only validated artifact-local modules and stylesheets resolve. It does not install application packages, read generated tsconfig files, execute package scripts or evaluate application JavaScript in Node. The current build lane does not support React/package dependencies or arbitrary asset pipelines. Build success is not type safety or functional success.

`recursa.browser_checks.check_application` uses Playwright 1.64.1 and Chromium's enabled sandbox with a new context per scenario. It serves an allowlisted build directory on an ephemeral loopback origin. External requests, writes, service workers, WebSockets, popups and downloads are blocked. Detected prohibited activity and runtime errors fail a scenario. No model-authored evaluation scripts or arbitrary selectors are accepted. This is browser isolation, not a VM: do not use it as a general hostile-code execution service. It is local only; the public replay server has no execution route.

`recursa.pipeline.verify_application` combines the stages and `repair_artifacts`. Repairs are limited to diagnosed existing files, preserve requirement provenance, retain attempt/hash history and rerun verification. Callbacks must use the caller's shared inference budget. The offline CLI supplies no callback and makes no model calls. An automated regression deliberately changes task creation to start completed; measured browser failures trigger one scripted correction, and the complete pipeline then passes. That scripted correction proves repair wiring only.

Each source/lint/build/browser stage has a hard deadline of 15/15/30/45 seconds, respectively; unit checks add a separately bounded build and browser pass. At most ten repair attempts are allowed (zero by default). There is no whole-pipeline process budget yet. Missing tools/browser are unmeasured, not successful. Provider-budget integration, broader framework/package support, genuine model-backed generation/repair and full accessibility assurance remain open work. The public replay container installs none of these optional execution tools.
