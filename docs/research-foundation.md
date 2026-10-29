# 2. Research foundation

Reviewed October 28, 2026: [paper v1](https://arxiv.org/html/2512.24601v1), [official runtime](https://github.com/alexzhang13/rlm), [minimal implementation](https://github.com/alexzhang13/rlm-minimal), and [runtime documentation](https://alexzhang13.github.io/rlm/).

The architectural commitment is to place specifications in a Python environment and let a model choose how to inspect them and invoke focused subcalls. A fixed decomposition script is an ordinary workflow. Codex engineering agents are implementation collaborators, not RLM runtime nodes. Deterministic validation alone demonstrates neither recursion nor synthesis quality.

The paper compares direct models, context-management workflows and RLM variants across tasks with different context-access demands. Its ablation without subcalls is useful: external inspection and recursive inference must be evaluated separately. Recursa's application-generation hypothesis extends the method to a different task and must collect independent evidence. Original-paper performance numbers are not Recursa results.

Long trajectories introduce variable runtime/cost, and redundant verification can waste calls. Therefore Recursa needs pre-dispatch reservations, hard process deadlines and bounded observations. Small specifications may not benefit from the extra orchestration. Baselines must share models, specifications, verification and budgets; context overflow must be reported and addressed using a suitable context-management comparison.

## Implementable fidelity checks

| Property | Required evidence |
| --- | --- |
| Externalized context | Initial root messages omit complete requirement bodies; REPL has full specification |
| Programmatic inspection | Executed code and recorded inspection IDs, not a fixed illustration |
| Recursive inference | Actual provider response to a subcall made from executed root code |
| Adaptive decomposition | Root chooses operations; application code is not a hardcoded pipeline output |
| Persistent intermediate artifacts | Validated source manifest with requirement IDs and hashes |
| Bounded observations | Inspection limits and configured runtime observation truncation |

Scripted transport tests can prove wiring but cannot satisfy the real-model evidence requirement. Nested RLM calls should follow a verified depth-one implementation rather than be assumed from a function name.
