# Open-model comparative research protocol

This is an additive, offline-only component and does not unlock Recursa live inference or change the P0 plan.

Compare three experimental arms: direct, externalized context without subcalls, and externalized context with recursive subcalls. Match pinned model/tokenizer commits, task suite digest, decoding, seed, evaluation protocol, and budgets. See recursa/research_manifest.py and tests/test_research_manifest.py.

A validator result means comparable configuration only; it is not evidence of real inference or performance improvement. Record actual authorized traces, successful outcomes, latencies, tokens, cost, and failures before making any measured claims. Check model licenses and available hardware before selecting OLMo, Apertus, or another open model. Openness is distinct from intelligence and compute efficiency.

Keep public Studio replay-only and do not enable paid compute or arbitrary model code execution. The new lab for internal activation analysis should remain separate from Recursa until the genuine model-backed vertical slice is verified.
