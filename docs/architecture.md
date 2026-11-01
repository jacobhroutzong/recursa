# 3. Technical architecture decision

The official `rlms==0.1.3` distribution was installed into a project-local Python 3.12 environment and inspected directly. Its import namespace is `rlm`. Exact installed dependencies are in `requirements-live.lock`. The default replay/CPU path remains dependency-free; live inference is optional.

## Module boundaries

| Module | Responsibility | Current implementation |
| --- | --- | --- |
| Context environment | Validate and index requirements; track bounded reads | `engine.py`, `context.py` |
| Recursive controller | Official RLM completion with compact root instructions | `live.py`, local trusted-execution mode only |
| Task graph | Requirement ordering and model-selected synthesis dependencies | `engine.validate_spec`, `taskgraph.py`; offline refinement/state tests pass |
| Artifact registry | Validate paths, requirement references and source hashes | `artifacts.py`; functional build verification pending |
| Verification engine | Source checks, then build/test/repair | `verification.py` parses JS/JSON; build/functional tests/repair pending |
| Experiment runner | Checkpoint/resume and budgets | `experiments.py`; CPU path verified |
| Trace API | Read-only evidence delivery | `server.py`; schema hardening pending section 9 |
| Studio | Replay inspection and source viewing | Existing standalone HTML/JS prototype |

The initial stdlib API and frontend avoid build/install cost while proving the core. React/TypeScript/FastAPI migration is deferred until the model-backed vertical slice works, per section 14's P0 gate. Provider details stay out of Studio. No empty packages are created merely to match the suggested layout.

## Verified runtime interfaces

`RLM.completion(prompt, root_prompt=None)` loads `prompt` as external context. The compact `root_prompt` explains the task. `other_backends` and `other_backend_kwargs` configure a separate sub-model. `custom_tools` inject indexed requirement readers. `RLMLogger()` captures trajectories in memory; raw trajectories remain private. `max_depth`, `max_iterations`, `max_timeout`, `max_tokens` and `max_concurrent_subcalls` exist in the installed version. The official OpenAI-compatible client accepts a base URL and sampling args.

The runtime's budget checks occur after iterations and depend on provider cost support. They are insufficient alone for a strict monetary cap. Recursa must reserve configured upper estimates before each provider request, count failed attempts and disable implicit retries. Cost estimates depend on owner-supplied rates; they are not provider billing guarantees.

The direct local REPL executes model code with host-process privileges and requires explicitly trusted experiments. After initial startup failures, five narrow container probes passed. The adapter now runs inside the SDK container for fixed scripted fixtures, with stale-image rejection and parent-side artifact validation. Real-provider mediation and genuinely authorized contained inference remain acceptance gates. Public hosting continues to serve replays only.
