# Offline application verification

Section 5 now has an executable local verification lane: validated source → pinned TypeScript and fixed AST lint checks → production bundling → independently authored Chromium interaction/unit cases and basic accessibility audits → optional bounded repair → complete recheck. The RLM adapter can invoke this lane when configured with reviewed acceptance scenarios. No genuine inference has been run.

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

Use a fresh output directory for each run. The command exits nonzero on failure, worker timeout or incomplete verification. The parent saves `worker-report.json`; `application/application-report.json` contains source artifacts, declared provenance, actual stage results and repair status once the worker reaches verification. A timeout before startup may leave only the worker report. Per-pass reports and uniquely named build directories preserve earlier failures. Source and output SHA-256 hashes identify inputs and results. This is an engineering fixture, not an RLM-generated example, research measurement or benchmark comparison.

The four authored scenarios check blank-title rejection and creation, toggling and persistence after reload, combined text/status filtering with an empty state, and keyboard interactions/navigation at a mobile viewport. They exercise the five task-spec requirement IDs, but do not establish complete accessibility or general requirement satisfaction. Artifact references are declared provenance; satisfaction remains null.

Six independently authored JSON unit cases exercise blank/trimmed titles and case-insensitive, status and combined filtering against `src/model.ts` exports. A trusted harness bundles the referenced modules and calls them inside the isolated browser, never in a host Node process. Cases specify a module, named export, JSON arguments and expected JSON result; no executable test body is accepted. Cases must be pure and independent of order; each fresh context runs the fixture. Missing tools yield a null pass rate. A deliberately wrong expected result is verified to fail.

Linting uses the pinned TypeScript 5.9.3 parser with fixed rules for parse errors, `var`, `debugger`, loose equality and direct `eval`. Comments and string literals are not mistaken for code. No generated lint configuration/plugins run. This small ruleset is not a full ESLint suite or a comprehensive security audit.

Each interaction scenario ends with a fixed basic DOM accessibility audit: document language/title, main landmark, level-one heading, duplicate IDs, visible control names, image alt attributes, positive tabindex and focusability of custom button/checkbox roles. Findings are stored with the scenario. Negative fixtures verify detection. Color contrast, complete accessible-name computation, screen-reader behavior and full WCAG conformance remain outside this audit.

## Boundaries

`recursa.build.build_application` uses esbuild 0.28.2 with an in-memory application source resolver. Validated artifact-local modules/stylesheets and a fixed pinned React closure resolve. It does not install application packages, read generated tsconfig files, execute package scripts or evaluate application JavaScript in Node. See [controlled React builds](react-builds.md). Arbitrary packages and asset pipelines remain unsupported. Build success is not type safety or functional success.

`recursa.browser_checks.check_application` uses Playwright 1.64.1 and Chromium's enabled sandbox with a new context per scenario. It serves an allowlisted build directory on an ephemeral loopback origin. External requests, writes, service workers, WebSockets, popups and downloads are blocked. Detected prohibited activity and runtime errors fail a scenario. No model-authored evaluation scripts or arbitrary selectors are accepted. This is browser isolation, not a VM: do not use it as a general hostile-code execution service. It is local only; the public replay server has no execution route.

`recursa.pipeline.verify_application` combines the stages and `repair_artifacts`. Repairs are limited to diagnosed existing files, preserve requirement provenance, retain attempt/hash history and rerun verification. Callbacks must use the caller's shared inference budget. The offline CLI supplies no callback and makes no model calls. An automated regression deliberately changes task creation to start completed; measured browser failures trigger one scripted correction, and the complete pipeline then passes. That scripted correction proves repair wiring only.

Each source/lint/build/browser stage has a timeout cap of 15/15/30/45 seconds, respectively; unit checks add a build and browser pass. All stages and repairs share one monotonic deadline, and subprocess timeout values shrink to the remaining time. The offline command defaults to 180 seconds; use `--max-wall-seconds` to set a smaller finite budget. A late stage is not dispatched after exhaustion; measured stage JSON and source artifacts remain on disk. Reviewed scenario/unit inputs and artifact hashes are saved in `verification-inputs.json`.

Atomic JSON writes use unique sibling staging files. Brief Windows replacement locks receive up to five bounded backoffs (0.62 seconds total); a permanent error is raised and the prior checkpoint remains intact. Regression tests cover both outcomes. This handles observed workspace file locks without treating a failed checkpoint write as success.

At most ten repair attempts are allowed (zero by default). The adapter uses the same `CallBudget` for root, recursive subcall and repair requests, including pre-dispatch reservations for tokens, request bytes and estimated cost. Failed dispatch reservations are retained. Each HTTP request receives the remaining timeout and disables retries. Repair calls are distinct `repair-model` events and cannot satisfy the required upstream RLM subcall evidence.

The pipeline's shared deadline is a cooperative elapsed-time gate, not universal process preemption. The offline CLI now additionally runs under a parent process deadline: on Windows a kill-on-close job is attached before stdin releases the workload. Worker descendants are terminated on timeout, cancellation and normal completion. Setup failure prevents workload dispatch. Tests verify normal child cleanup, cancellation, failure before dispatch, an actual scripted upstream REPL blocked in `sleep`, and a child spawned by that REPL. The POSIX process-group implementation has not been verified on this Windows machine.

This boundary controls lifetime; it is not a filesystem/network sandbox. The helper accepts trusted, stdin-gated commands only. The shipped worker has no provider execution mode; genuine live batching remains disabled. The upstream REPL still needs a stronger security boundary before untrusted use, and genuine authorized inference remains unverified. Missing tools/browser are unmeasured, not successful. Broader framework/package support and full accessibility assurance remain open work. The public replay container installs none of these optional execution tools and has no execution endpoint.

## Adapter configuration and offline evidence

The programmatic adapter accepts `application_verification` with `scenarios` and optional `unit_cases`, using the declarative schemas above. Tests must be independently authored/reviewed; they are never created by the model being evaluated. The scenario list is required when enabling repairs. Compiler configuration uses the existing `typescript_compiler_directory`; pinned build/browser packages use the local tooling directories. No public execution route or live CLI was enabled by this integration.

The scripted official-runtime regression performs an indexed requirement read, an actual upstream `llm_query` with intercepted HTTP transport, validated task submission, source/build/browser checks, one focused scripted repair and a full recheck. A second run caps calls at two: root and generation dispatch, the repair is denied before HTTP, and private trajectory, measured stages and partial trace persist. Neither run is genuine inference, a benchmark result or proof of model reasoning.
