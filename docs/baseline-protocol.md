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

## Repeated trials

The follow-up uses two fresh seed blocks for each case, for 12 trials across the three methods. It reuses the pilot's Qwen weights, 8,192-token context, six-call ceiling, 2,304 output tokens per call, 120-second deadline, and zero-repair policy. Both cases use the same budgets. Seed 17 runs Task Management then Operations Analytics, with direct, structured, and contained RLM in that order. Seed 73 reverses both the case and method orders. Prompt caching is disabled. The initial Task Management pilot is displayed separately.

Operations Analytics retains all ten original requirements and adds a fixed synthetic input and observable UI contracts in `examples/specs/operations-local-reviewed.json`. Four independent scenarios check exclusion counts and KPI arithmetic, filtering and staffing totals, drill-down, and saved views with incomplete staffing. A hand-authored Chromium control passed all four before interpretation of the generated runs. The scenarios cover a subset of the specification. For example, they do not exercise CSV downloads or verify sorting before pagination.

```powershell
python scripts/run_task_comparison.py --server <llama-server> --weights <Qwen3-4B-Q4_K_M.gguf> --output runs/series-17 --cases tasks operations --seed 17 --authorize-live
python scripts/run_task_comparison.py --server <llama-server> --weights <Qwen3-4B-Q4_K_M.gguf> --output runs/series-73 --cases operations tasks --seed 73 --reverse --authorize-live
```

The runner writes a private checkpoint after every arm. The series assembler takes the four case-and-seed `comparison-record.json` files, checks matched inputs and limits, and writes the measured Studio record. Missing build or browser measurements stay null. This is a two-case pilot with two seeds, so the results do not establish a general method advantage.

### Repeated results

| Specification | Method | Builds passed / measured | Browser scenarios passed / measured |
| --- | --- | ---: | ---: |
| Task Management | Direct | 0 / 2 | Unmeasured |
| Task Management | Structured | 2 / 2 | 0 / 8 |
| Task Management | Contained RLM | 1 / 2 | 0 / 4 |
| Operations Analytics | Direct | Unmeasured | Unmeasured |
| Operations Analytics | Structured | Unmeasured | Unmeasured |
| Operations Analytics | Contained RLM | 0 / 1 | Unmeasured |

Both direct Operations runs ended at the 2,304-token output cap. Both structured Operations runs stopped on invalid manifest JSON in the state stage. The seed-17 Operations RLM returned source that failed the build. For seed 73, the broker rejected an incomplete model response. Overall, three Task Management builds reached Chromium, and all 12 measured scenarios failed. The original repaired Task Management showcase is separate. [Series record](../apps/studio/comparison-series.json)

## Paired repair trials

The paired series reruns both seed blocks with the same first-pass generation settings and budgets. After each arm, the runner saves its first-pass measurement before attempting repair. Every method uses the same host-side policy and model for repair. The contained RLM still generates through the isolated runtime.

Eligible source must have recorded failed verification. A trial that stops before producing a measurable candidate, or one with no failed checks, skips repair. The model sees the reviewed specification, the existing files, and measured failure diagnostics. Browser diagnostics include scenario IDs, requirement IDs, completed step counts, and blocked activity. The repair can replace existing files with the same requirement provenance. The small-app scope permits neighboring files after a known diagnostic implicates the app. It forbids adding paths and limits the candidate to 16 files.

Repair and recheck share a separate 90-second allowance. Repair inference has at most one call, 2,304 output tokens, and 32,000 input bytes, with an earlier 24,000-character bound on the repair context. A malformed response, unchanged source, or unavailable recheck leaves the after measurement null. Every changed candidate goes through the original build and browser verifier. The repaired showcase and historical first-pass series remain separate.

To reproduce, run the two seed commands above with fresh output directories and add `--repair`. Assemble those four case-and-seed records into `apps/studio/repair-series.json` using `scripts/assemble_comparison_series.py`.

Seven of the 12 fresh trials had a failed source candidate eligible for repair. Three produced accepted edits and a completed recheck. Both direct Task Management repairs took failed builds to passing builds, with 0 of 4 Chromium scenarios passing each time. The seed-73 Task Management RLM repair kept its passing build and remained at 0 of 4 browser passes. Two structured Task Management replies and the seed-17 Task Management RLM reply failed manifest validation. The one eligible Operations Analytics repair stopped on an incomplete response. The five other Operations trials had no source candidate eligible for repair.

The Benchmarks view links each row to measured phase timing in the Execution Explorer. First-pass wall time includes generation and verification. Expand that phase to see all 22 recorded initial model requests across the paired series, including three incomplete responses. Repair-call and recheck timings are child phases of repair wall time. [Paired record](../apps/studio/repair-series.json)

The historical call nodes show llama-server prompt evaluation plus token generation. They exclude transport, model orchestration, and verification. The recovery script aligns private provider reservations and server timing rows in original single-slot execution order and checks token counts for completed responses. Incomplete responses are matched against the configured output cap. Earlier archives without this timing evidence continue to show no per-call measurement.

New runs measure host request wall time around the transport, including worker overhead for supervised calls, and label that source separately. A request denied before transport has no duration. The public timing records contain durations, token counts, and classifications. Provider bodies and prompts stay private.
