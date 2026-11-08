# Portfolio integration

**Recursa — Recursive Application Synthesis** · AI Systems / Inference Research

Recursa wraps the official Recursive Language Models runtime in a local research workbench. It records specification inspection and model calls, validates returned web applications against independently authored browser scenarios, and publishes reviewed evidence to a CPU-only replay Studio.

The Astro case study uses the existing project-content entry and Selected projects links. It includes a Studio embed with a full-screen fallback, an architecture diagram, a recorded Execution Explorer screenshot, an Aviation Chromium capture, and the measured benchmark denominators. The portfolio copy distinguishes the three verified, host-assisted showcases from the unassisted first-pass benchmark.

[Current portfolio](https://jacobroutzong.dev/projects/recursa/) · [Studio](https://jacobroutzong-recursa.hf.space/) · [Source](https://github.com/jacobhroutzong/recursa) · [Architecture](architecture.md) · [Protocol and results](baseline-protocol.md)

The original portfolio integration shipped in [portfolio PR #6](https://github.com/jacobhroutzong/portfolio-website/pull/6). The updated case study passed the local portfolio verification suite, including 108 Node tests, 33 Vitest tests, the Python and NumPy checks, the Astro build, internal link checks, and Worker compilation. Chromium verified the homepage and Projects links, both screenshots, architecture diagram, embedded live Studio, and full-screen fallback at 1440 and 390 pixels. The owner cleared publication after the Colab CPU smoke run and waived fresh-runtime resume verification. [Remaining release gates](completion-checkpoint.md)
