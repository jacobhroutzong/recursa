# Section 5 — bounded repair coordinator

`recursa.repair.repair_artifacts` accepts validated artifacts, known requirement IDs, the failed verification report, a repair callback and a re-verification callback. It makes no provider request itself and never executes generated applications. A future model callback must share the controller's call/cost/time budget; genuine model-backed repair is not yet wired into live inference.

Only existing files implicated by measured failed checks may change. Requirement provenance cannot change, paths cannot expand, and dependency contracts and diagnostics are bounded. Invalid output and unchanged source stop the loop. Failed attempts are preserved. Callback and verification errors expose classifications, not raw exception messages. Optional output stores state atomically and keeps source-bearing contexts under `private/`.

A successful syntax repair means only that the previously failed syntax checks passed on recheck. Missing or unavailable verification produces `verification-incomplete` and retains the last measured source state. Functional success remains unmeasured. Attempt counts are finite and explicitly configurable; no more model calls are implied than the callback's own authorized budget permits.

Offline tests cover actual non-executing Node parsing of a corrected JavaScript fixture, allowlist/provenance violations, no-op edits, context limits, exhausted attempts, callback failures and unknown verification. These are implementation tests, not evidence of genuine model repair or generated-app success.
