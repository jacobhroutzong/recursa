# 21. Compute Resource Optimization — Existing Subscriptions

The project owner has access to:

- **Google Colab Pro:** Primary allocation for GPU-intensive workloads, open-weight model inference, fine-tuning, and large evaluation experiments.
- **Hugging Face Pro ($9/month):** Prioritize hosting, dataset/model versioning, and public Spaces demonstrations. Do not assume dedicated GPU hardware is included.
- **Local development:** Windows 11, RTX 4070 Laptop GPU (8 GB VRAM), 32 GB RAM.
- **Codex:** Primary engineering and implementation agent.

## Compute strategy

1. Develop and test Recursa locally whenever practical.
2. Use CPU execution and remote inference APIs for workloads that do not require a local GPU.
3. Prefer Google Colab Pro over paid Hugging Face GPU instances for substantial accelerator workloads.
4. Implement portable, resumable Colab experiment scripts and notebooks, including dependency installation, checkpoints, benchmark execution, and result export.
5. Store experiment configurations and results in version-controlled files or durable storage.
6. Use Hugging Face Spaces for a CPU-first public frontend and recorded execution replays.
7. Keep live model inference optional and protected by strict usage limits.
8. Never assume Colab GPUs are continuously available or that Codex can automatically control a Colab session. Verify supported automation methods before attempting unattended execution.
9. Avoid unnecessary GPU usage, paid hardware upgrades, or new infrastructure costs.
10. Optimize for the maximum research and portfolio value using subscriptions already available.

## Automation objective

Make experiment execution as close to one-command as possible.

Provide a reproducible Colab entry point that prepares the environment, loads configurations, runs authorized experiments within a defined compute budget, saves metrics and traces, and exports artifacts for Recursa Studio.

Do not require the owner to manually copy code between notebooks or rebuild the environment for every experiment.

Prioritize a working local system and hosted portfolio demonstration before computationally expensive experiments.
