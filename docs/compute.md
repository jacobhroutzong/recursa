# Existing-subscription compute policy

1. Local CPU checks and replay development come first. Nothing in the default path imports torch, downloads weights or uses the GPU.
2. Use remote inference only when a real backend, authorization and provider-level usage limits exist. Current live configs are design examples and are rejected, even with `--authorize-live`.
3. Prefer Colab Pro for future substantial accelerators. Do not provision paid HF GPUs, new cloud services or hardware automatically.
4. Use a durable Google Drive directory for Colab batch outputs. Every trial writes its input and `running` checkpoint before work, then atomically replaces checkpoint/result JSON. Source, configuration and specification hashes prevent stale reuse. This provides between-trial recovery; model-state checkpoints are not implemented.
5. Output ZIP and CSV are regenerated after each completed/failed/timed-out trial. An abrupt VM termination may precede export; preserved trial files can be exported by rerunning. Drive must already be mounted and writable.
6. The wall budget is per invocation across the batch. Completed trials are skipped; an interrupted CPU trial may rerun. The worker is terminated on timeout. Process termination is a reliability bound for the current CPU checker, not isolation for arbitrary model-generated code. Call/cost/token budgets are zero in smoke mode; live enforcement must be verified before enabling inference. Colab compute-unit usage cannot be converted into a guaranteed monetary ceiling by this runner.
7. HF Spaces is replay-only CPU hosting. The prepared Docker image contains explicit public run files. Research outputs otherwise stay in durable Drive or reviewed version control; no automatic upload/export to third parties occurs.
8. Public live inference is disabled by architecture: there is no execution HTTP endpoint. A future local trusted REPL integration needs call, token, time, depth, repair, concurrency and conservative cost limits plus an explicit authorization flag.

## Colab use

Create the source archive with `python scripts/package_source.py`, store it at `MyDrive/Recursa/recursa-source.zip`, and upload/open the repository notebook. Run all prompts once for Drive access, loads the archive and executes the CPU config. Change the notebook's archive/config/output constants to use a different reviewed input. Every session reconstructs source from the same durable ZIP; no code copying is needed. Python 3.11+ is checked. This stdlib path needs no dependency installation. Future GPU dependencies should use a pinned optional lockfile, not an uncontrolled upgrade of the global notebook environment.

Google documents variable resource availability and VM termination. Notebook loading, mounting and cell execution are the verified supported interaction model; unattended session startup/control has not been verified and is not attempted. A future GPU experiment must explicitly record detected hardware, model revision, data revision, software lock, seeds and checkpoint compatibility, and stop if its required accelerator is absent.

References verified October 28, 2026: [Colab FAQ](https://research.google.com/colaboratory/faq.html), [HF GPU hardware](https://huggingface.co/docs/hub/spaces-gpus), [RLM runtime source](https://github.com/alexzhang13/rlm). GPU Space upgrades are separately billed; PRO does not imply dedicated GPU hardware. No subscription price or compute quota is hardcoded.
