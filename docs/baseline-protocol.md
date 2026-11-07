# Task Management baseline pilot

The direct runner sends the complete reviewed specification in one generation call. The structured runner orders requirements by dependency, generates a state and persistence module, then passes its source and declared interfaces to a second call for browser UI assembly. A fixed task graph enforces the dependency and rejects attempts to overwrite the state artifact. The contained RLM inspects external context and decides when to call the model recursively. All three methods validate returned manifests and use the same build, lint, accessibility and Chromium verifier. Prompts exclude the test steps. Offline integration checks intercept transport and exercise real browser verification.

The local pilot uses the exact reviewed specification from the published Task Management record. It uses the same four acceptance scenarios across conditions, with the diagnostics anchored to `index.html` to allow each method to choose its own JavaScript filenames. The model uses the same Qwen GGUF revision, context window, sampling settings and per-call limits throughout. Each arm has 120 seconds, six calls, 13,824 reserved output tokens, and no repairs. Direct uses one generation call by design. Structured uses two calls and the RLM can make adaptive calls within the shared ceiling. Wall time includes verification and, for the RLM, container overhead. It excludes model startup.

The first calibration pass found that the original diagnostic path `app.js` rejected a direct build whose module was named `task.js`. The structured model returned the state module in a different JSON envelope. The RLM exhausted its call budget. Before repeating all three arms, we changed the diagnostic path across methods and gave the structured state prompt an explicit manifest example. All interaction steps and assertions stayed the same. The earlier repaired showcase also remains separate from the comparison.

## Measured local pilot

| Method | Build | Browser acceptance | Completed calls | Input / output tokens | Wall time |
| --- | --- | --- | ---: | ---: | ---: |
| Direct LLM | Failed | Unmeasured | 1 | 488 / 1,000 | 16.8 s |
| Structured | Passed | 0 of 4 | 2 | 1,198 / 1,057 | 26.2 s |
| Contained RLM | Unmeasured | Unmeasured | 6 | 6,934 / 2,139 | 47.7 s |

The direct candidate used a script entry that did not satisfy the shared production requirement for a local ES module. The structured candidate built and failed all four declared scenarios. The blank-title test encountered a blocked native dialog, the persistence scenario reached its final accessibility audit, and the filters and mobile keyboard scenarios stopped on assertions. The RLM reported requirement inspection and a subcall. The host verified container policy and cleanup, counted six successful completions, and rejected the next request at the shared call cap. That trial produced no source package for verification.

The measured record excludes the earlier calibration pass and the repaired demonstration. [Recorded metrics](../apps/studio/task-comparison.json) · [Studio Benchmarks](https://jacobroutzong-recursa.hf.space/#benchmarks)

```powershell
python scripts/build_rlm_image.py
python scripts/run_task_comparison.py --server <llama-server> --weights <Qwen3-4B-Q4_K_M.gguf> --output runs/pilot-001 --authorize-live
```

Use a CUDA-capable llama-server build with reasoning and prompt-cache controls, and make its vendor libraries available to that process. The script starts and stops a loopback server with the digest-checked weights and a temporary process-local key. Use a fresh output directory. Only the aggregate `comparison-record.json` is suitable for review and publication. It includes input and runtime hashes, provider-reported tokens for completed calls, elapsed time, build status and measured acceptance outcomes. Individual provider responses, server logs and generated candidate source stay private. Cost and requirement satisfaction remain null when unmeasured.

The baseline CLI also accepts `--method direct` or `--method structured` for standalone runs. Each requires reviewed specification and scenario files, an explicitly authorized supervised provider configuration, a selected model, and a fresh output directory. Optional repairs draw from the same provider reservation and time budget.

This pilot uses one trial per method on one small specification. A research comparison still needs repeated trials across specification sizes, with context-limit failures recorded separately from execution failures.
