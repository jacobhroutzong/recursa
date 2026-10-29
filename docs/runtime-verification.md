# Section 4 — offline runtime verification

The project-local `.venv` contains official PyPI `rlms==0.1.3`. Constructors, `completion(prompt, root_prompt)`, OpenAI-compatible client routing, custom tools and logger were inspected from installed source. `requirements-live.lock` records exact installed dependency versions. PyPI installation required network approval and completed without inference calls.

`recursa.live` delegates the inference loop and REPL to upstream `RLM`. A version-locked client factory seam wraps official OpenAI clients with shared pre-dispatch reservations and disables retries. Root and sub-model configurations are separate. The initial implementation permits depth and concurrency one with zero repair attempts; deeper recursion is deliberately unsupported until the initial path is proven. `ContextIndex` records bounded indexed reads/searches. The full specification is still accessible to the REPL, so direct reads are not all instrumented; raw upstream code is captured privately.

The structured artifact contract rejects invalid paths, Windows reserved filenames, hidden files, unsupported extensions, duplicate names and unknown requirement references. It hashes and writes source only after manifest validation. This is source/schema verification, not functional app verification. No generated artifact is executed by the adapter.

## Actual observed test

The offline integration test intercepts the official client's HTTP transport with scripted responses. The scripted root emits Python that reads requirement R1, invokes `llm_query()` through upstream's local socket handler, receives a scripted JSON artifact manifest and sets the upstream answer dictionary. The test checks that a sentinel requirement body is absent from the initial root messages but present in the subcall. It verifies two intercepted requests, an actual REPL inspection event, a subcall event, artifact source writing, a private upstream trajectory and absence of the placeholder credential from the public record.

**This is not a genuine model run or evidence of model reasoning.** All responses and usage numbers in the transport test are controlled fixtures. Test outputs are temporary and are not copied into public replay captures. Existing public captures remain deterministic CPU checks.

The latest complete suite passed 24 tests in the live-enabled project environment on October 28, 2026. The standard-library-only suite skips the two optional runtime integration cases when `rlms` is unavailable. Initial testing exposed an upstream handler socket that was shut down without being closed; the version-locked adapter now closes that socket during cleanup, and the latest suite emitted no resource warning. Loopback tests need execution outside this environment's network sandbox.

An exhaustion test also exposed upstream exception wrapping: a rejected subcall initially surfaced as a generic failed run. Budget exhaustion is now sticky in the shared budget object, survives the upstream error conversion, prevents further transport dispatch and preserves a `budget-exhausted` partial trace. All reservations are synchronized, including direct concurrent use.

## Current limits

- Owner requested offline implementation/testing first. No model provider was contacted. The public API and batch CLI continue to reject live inference while integration/security verification is incomplete.
- Local execution is explicitly trusted and has host privileges. Do not use untrusted specs or publicly expose it. Docker's engine is not running on this machine. Isolated execution is unfinished.
- The batch worker enforces a hard process deadline; adapter timeout checks alone cannot terminate arbitrary Python inside a REPL. Invoke through a verified worker before enabling any genuine run.
- Reservations count failed dispatches and do not refund output allowances. Input token estimates use request bytes plus framing allowance. Rates are owner configuration and estimated, not guaranteed billing limits. Remote zero-rate assumptions are rejected. No GPU or subscription-credit assumptions exist.
- Raw trajectories stay under `private/`; export and replay scanning exclude that directory. Public source/spec content still requires manual review before publication. This does not provide universal secret redaction of arbitrary generated source.
- Function-level authorization, finite budgets, explicit model names, configured credential environment variables and trusted-local-execution flags are all required. Credential values are never configuration fields.

Section 5's offline core now uses the adapter's custom-tool interface for an adaptive dependency-aware plan, validated task submissions, durable intermediate source and declared-contract lookup. Final output paths must refer to registered task artifacts. Source checking and provenance coverage follow; these are not functional acceptance tests. Genuine backend verification remains open, and no benchmark result or completed application is claimed.
