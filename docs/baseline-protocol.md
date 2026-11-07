# Task Management baseline pilot

The direct runner sends the complete reviewed specification in one generation call, validates the returned artifact manifest, and uses the shared build, lint, accessibility and Chromium verifier. Optional repairs draw from the same provider reservation and time budget. The generation prompt excludes the test steps. The offline integration test substitutes a recorded artifact response and exercises the real browser checks. Its outcome is engineering evidence.

For a future authorized pilot, export the exact reviewed specification from the published Task Management record and use the same scenario file across conditions. Use the same Qwen GGUF revision, context window, sampling settings, per-call cap, aggregate limits and verification toolchain. Compare first-pass output separately from output after an identical repair policy. The earlier RLM run with selected repairs and host-composed filter remains a demonstration and must be recorded separately from a controlled comparison.

```powershell
python -m recursa.baseline --spec reviewed-task.json --scenarios examples/specs/tasks-local-acceptance.json --provider-config private-provider.json --model <model-alias> --output runs/direct-001 --authorize-live
```

The private provider file uses the supervised adapter fields `base_url`, `api_key_env`, `rates`, `budget`, and `output_tokens`. Keep it with the run configuration and put credentials in the named host environment variable. Use a fresh output directory per trial. The report includes input hashes, provider observations, elapsed time, build status and measured acceptance outcomes. Cost and requirement satisfaction remain null when unmeasured. The verifier preserves the first build result separately in its private output.

Record context-limit failures and keep larger cases with specifications beyond the model window in a separate comparison against nonrecursive context management. The next condition to implement is dependency-aware nonrecursive generation. Run all three conditions under a shared protocol before reporting comparative outcomes.
