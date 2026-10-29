# Portfolio integration — development preview

**Project:** Recursa — Recursive Application Synthesis  
**Category:** AI Systems / Inference Research

Current truthful summary: A CPU-first experiment and replay workbench for application-synthesis research, with structured requirement validation, resumable experiment batches, source-aware provenance and an interactive trace inspector. Model-backed RLM synthesis remains under development.

Target summary after genuine inference is verified: An experimental Recursive Language Model system that programmatically explores large specifications, generates typed web applications, and visualizes recursive inference and validation.

The dedicated Astro page at `/projects/recursa/` follows the existing Markdown project-content convention. The shared Selected projects list puts Recursa on the homepage and Projects listing. The page embeds the CPU replay Space, includes a full-screen fallback and actual Studio capture, and explicitly separates deterministic checks and scripted integration fixtures from genuine model evidence. It makes no benchmark-superiority claims.

Portfolio change: https://github.com/jacobhroutzong/portfolio-website/pull/6, merged October 29, 2026. The latest main activity snapshot was incorporated without force-pushing. Local lint, Astro validation, 97 Node tests, 20 Vitest tests, 319 Python reference checks, 150 randomized comparisons, production build/link checking and Worker function compilation passed. GitHub verification and Docker checks passed, as did Cloudflare Pages preview. The separate pre-existing Workers build failed on both unchanged main and this branch; its infrastructure was not modified.

The owner authorized publication. Source: https://github.com/jacobhroutzong/recursa. Space: https://huggingface.co/spaces/jacobroutzong/recursa. The production page, actual embedded Studio, full-screen fallback and Recursa links on both the homepage and Projects listing were verified in the in-app browser on October 29. A direct scripted HTTP request received 403, while normal browser navigation displayed the deployed content. Colab remains prepared but untested in an authenticated session.
