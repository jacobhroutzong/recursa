# Verification record

Verified locally October 28, 2026 using bundled Python 3.12.14 on Windows.

- Seven unittest cases passed: deterministic report provenance, dependency failures, CPU batch execution/export/resume, input fingerprint changes, live-mode rejection, timeout/interruption checkpoints, invalid budgets/traversal, and HTTP replay boundaries (several assertions share a case).
- HTTP replay returns a run archive and Studio; arbitrary file paths, missing runs and `/api/execute` return 404. Loopback HTTP verification required running outside the network sandbox.
- Studio opened in the in-app browser at localhost:7861. Actual saved CPU run loaded; execution explorer showed three recorded events; selecting validation displayed the real requirement order, SHA256 and check results. Screenshot saved at `docs/screenshots/studio.png`.
- Studio inline JavaScript passed `node --check` during implementation.
- CPU batch used zero model calls and zero paid inference. No GPU allocation or infrastructure upgrades occurred.

Update: official `rlms==0.1.3` is installed in the project `.venv`. The latest complete offline suite passed 24 cases, including official RLM/REPL/subcall wiring, exhaustion before transport dispatch, context sections/hierarchy/contracts, concurrent reservations, artifact paths, dependency-aware task state/refinement and non-executing JavaScript source checks. The syntax checker was tested with a filesystem-write payload; it parsed the source and did not create the target file. Private run-shaped JSON is excluded from the replay archive. See `runtime-verification.md` and `synthesis-verification.md`. Scripted transport fixtures are not genuine model evidence.

Not verified: Colab execution/authentication, Docker image build, Hugging Face publication, mobile browser layout, live inference, generated application functionality, baseline comparison or training checkpoints. No public deployment exists. The system is an offline-tested core and replay foundation, not completion of the master specification's RLM success criteria.
