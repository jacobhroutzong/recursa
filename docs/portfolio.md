# Portfolio integration

**Recursa Studio** · AI Systems / Inference Research

Recursa wraps the official Recursive Language Models runtime in a local research workbench. It records specification inspection and model calls, validates returned web applications against independently authored browser scenarios, and publishes reviewed evidence to a CPU-only replay Studio.

The Astro case study uses the existing project-content entry and Selected projects links. It includes a Studio embed with a full-screen fallback, an architecture diagram, a recorded Execution Explorer screenshot, an Aviation Chromium capture, and the measured benchmark denominators. The portfolio copy distinguishes the three verified, host-assisted showcases from the unassisted first-pass benchmark.

[Current portfolio](https://jacobroutzong.dev/projects/recursa/) · [Studio](https://jacobroutzong-recursa.hf.space/) · [Source](https://github.com/jacobhroutzong/recursa) · [Architecture](architecture.md) · [Protocol and results](baseline-protocol.md)

The original portfolio integration shipped in [portfolio PR #6](https://github.com/jacobhroutzong/portfolio-website/pull/6). The updated case study passed the local portfolio verification suite, including 108 Node tests, 33 Vitest tests, the Python and NumPy checks, the Astro build, internal link checks, and Worker compilation. Chromium verified the homepage and Projects links, both screenshots, architecture diagram, embedded replay Studio, and full-screen fallback at 1440 and 390 pixels. The owner cleared publication after the Colab CPU smoke run and waived fresh-runtime resume verification. [Remaining release gates](completion-checkpoint.md)

## Recursa Studio portfolio handoff

| Research area | Existing destination and source | What visitors can inspect |
| --- | --- | --- |
| **Application Synthesis** | [Recursa Studio](https://jacobroutzong.dev/projects/recursa/studio/) · [Recursa case study](https://jacobroutzong.dev/projects/recursa/) · [Recursa source](https://github.com/jacobhroutzong/recursa) | RLM specification inspection and focused subcalls, recorded synthesis traces, artifacts, build and browser verification, and matched-method benchmarks. |
| **Agent Optimization** | [Harness² Lab](https://jacobroutzong.dev/projects/harness2-lab/) · [Harness² Lab source](https://github.com/jacobhroutzong/harness2-lab) | Propose → Probe → Compose, selection, harness components, reusable lessons, edit lineage, and adaptive compute experiments. |

Use **Recursa Studio** as the parent identity on the Recursa case study and its homepage Selected projects and Projects listing entries. Link both areas from the case study, with the static Studio as the primary Application Synthesis destination. Add a reciprocal **Recursa Studio** link from the existing Harness² page to the Studio overview. Keep the existing project URLs, direct Space fallback, and Harness² navigation. Retain the first-party Harness² frontend and the Cloudflare Pages `/api/harness2-lab/*` proxy to its existing Hugging Face Space.

After the Recursa change lands, use that commit as the source of truth. From the portfolio checkout, run `python scripts/export-recursa-studio.py RECURSA_CHECKOUT EMPTY_OUTPUT_DIR`, review the output, and sync it to `public/projects/recursa/studio/`. The exporter rewrites replay URLs for the static path, regenerates the inline-script CSP, and copies the license and notice. Review the diff against the existing snapshot and update the SHA-256 entry for `projects/recursa/studio/index.html` in `scripts/public-research-digests.json`. Keep the publication allowlist aligned with reviewed output paths and investigate any unexpected evidence or asset changes before repinning them. Run `npm run verify` and exercise the static Studio and reciprocal links on desktop and mobile. The build runs the internal-link and public-boundary checks. [Portfolio publication policy](https://github.com/jacobhroutzong/portfolio-website/blob/main/docs/PUBLICATION.md)

Use a clean Recursa checkout that preserves repository line endings. A Windows checkout with `core.autocrlf=true` changes the exported bytes of several replay JSON files that the server serves verbatim. In the A1 export comparison, those differences were line endings only, and `index.html` was the only content change across the 99 exported files.

Keep the evidence labels on both pages. Recursa's public Studio is replay-only. Its recorded model calls are distinct from deterministic CPU and scripted fixtures. Repaired or host-assisted browser passes are distinct from unassisted first-pass measurements. Leave unmeasured performance and cost values unmeasured. Harness² can run its stochastic simulator interactively, and its scores describe that toy world. The projects retain independent runtimes, and no matched experiment establishes a synthesis benefit from combining them.

Credit the original Recursive Language Models work by Alex L. Zhang, Tim Kraska, and Omar Khattab, and the original Harness² work by Xu et al. Retain both repositories' Apache-2.0 license and notice files and the upstream component attributions in the existing distributions. [Recursive Language Models](https://arxiv.org/abs/2512.24601) · [Harness² paper](https://arxiv.org/abs/2610.14224)
