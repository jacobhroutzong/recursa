# Verification record

Verified locally October 28, 2026 using bundled Python 3.12.14 on Windows.

- Seven unittest cases passed: deterministic report provenance, dependency failures, CPU batch execution/export/resume, input fingerprint changes, live-mode rejection, timeout/interruption checkpoints, invalid budgets/traversal, and HTTP replay boundaries (several assertions share a case).
- HTTP replay returns a run archive and Studio; arbitrary file paths, missing runs and `/api/execute` return 404. Loopback HTTP verification required running outside the network sandbox.
- Studio opened in the in-app browser at localhost:7861. Actual saved CPU run loaded; execution explorer showed three recorded events; selecting validation displayed the real requirement order, SHA256 and check results. Screenshot saved at `docs/screenshots/studio.png`.
- Studio inline JavaScript passed `node --check` during implementation.
- CPU batch used zero model calls and zero paid inference. No GPU allocation or infrastructure upgrades occurred.

Update October 29: official `rlms==0.1.3` is installed in the project `.venv`. The latest complete offline suite passed 33 cases, including official RLM/REPL/subcall wiring, pre-dispatch exhaustion, structured context, concurrent reservations, artifact paths, dependency-aware task state/refinement, bounded repair, source-bound release evidence and optional pinned TypeScript checking. The JavaScript syntax checker parsed a filesystem-write payload without creating its target file. TypeScript accepted a contract, rejected TS2322, and never executed a source-level throw. Private run-shaped JSON is excluded from the replay archive. Scripted transport fixtures are not genuine model evidence.

Publication verified: GitHub source and CPU Basic Space are public; the deployed Space's health, progress and CPU replay endpoints responded correctly. The production portfolio page, embedded Studio, fallback and homepage/Projects links were verified in the browser. Portfolio PR #6 passed GitHub verification, Docker smoke and Pages preview before merging. An unrelated pre-existing Workers build remains failed on both unchanged main and the PR.

Not verified: authenticated Colab execution, mobile browser layout, live model inference, generated application functionality, baseline comparisons or training-state checkpoints. The system remains an offline-tested core and replay foundation, not completion of the master specification's RLM success criteria.
