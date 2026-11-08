# Recursa completion checkpoint

The public Studio is a working development preview. The engineering path has a genuine contained local RLM run with recorded context inspection and a subcall. The three planned examples have scoped Chromium verification, inspectable source, and captured workflows. The replay service publishes 45 versioned benchmark traces and a 24-check sandbox and replay audit. [Studio](https://jacobroutzong-recursa.hf.space/) · [Ordered implementation record](implementation-progress.md)

| Area | Checkpoint | Completion gate |
| --- | --- | --- |
| Engineering | Local RLM, host broker, artifact registry, build and acceptance pipeline, budget and cleanup checks are exercised. Hosted Windows and Linux replay, Chromium, and containment checks passed. All 110 local tests passed with the Apache 2.0 release changes. The wheel, Colab ZIP, and replay image carry the license and notice | Run the final release checks |
| Demonstration | Three of three examples are verified within their declared scenarios. Desktop and mobile walkthroughs verified the execution graph, all three workflow replays, downloaded source and specifications, and the updated portfolio's live embed and full-screen fallback | Recheck the updated portfolio URL after publication |
| Research | Direct, structured and contained RLM completed an 18-trial schedule across Task Management, Operations Analytics and Aviation Operations. The expanded Operations suite includes sorting and CSV checks | Document the measured limits of the local model and scope broader evaluation if needed for general claims |
| Portfolio and handoff | The updated case study, architecture diagram, screenshots, attribution, and handoff are prepared locally | Publish and verify the production page |
| Compute | A fresh local extraction ran the notebook cells, reused a completed checkpoint, recovered a seeded interrupted checkpoint, and exported CSV and ZIP. The Windows launcher also passed from the extracted archive | The owner reported Colab CPU batch `46597473698c60f5` complete. Drive-backed resume after runtime deletion is untested on Colab and was waived for this release |

## Roadmap

1. **Repository and release quality.** `python -S scripts/verify_checkout.py` verifies CPU replay and resume from a clean checkout. The [Verification workflow](https://github.com/jacobhroutzong/recursa/actions/workflows/verification.yml) tracks hosted Windows and Linux checks and an isolated Docker and Chromium job. The [setup guide](reproduction.md), [upstream attribution](attribution.md), and [Apache 2.0 license](../LICENSE) are ready.
2. **Research evaluation.** The expanded benchmark adds Aviation and the two Operations checks for sorting before pagination (`OPS-07`) and filtered CSV export (`OPS-09`). The [benchmark protocol](baseline-protocol.md) describes the two matched seed blocks, common limits, and measured denominators. Showcase runs and repair trials remain separate.
3. **Final demonstration and case study.** The Studio walkthrough, local portfolio verification suite, and desktop and mobile embed checks passed. [Portfolio record](portfolio.md)
4. **Reproduction and handoff.** The local launcher and notebook smoke path have been exercised. The owner reported the Colab CPU smoke result and waived the fresh-runtime resume check. [Reproduction guide](reproduction.md) · [Handoff](handoff.md)

The benchmark characterizes the three methods under one local model and budget. The owner accepted the current Studio and 18-trial benchmark as the feature-complete release baseline.
