# Recursa completion checkpoint

The public Studio is a working development preview. The engineering path has a genuine contained local RLM run with recorded context inspection and a subcall. The three planned examples have scoped Chromium verification, inspectable source, and captured workflows. The replay service publishes 45 versioned benchmark traces and a 24-check sandbox and replay audit. [Studio](https://jacobroutzong-recursa.hf.space/) · [Ordered implementation record](implementation-progress.md)

| Area | Checkpoint | Completion gate |
| --- | --- | --- |
| Engineering | Local RLM, host broker, artifact registry, build and acceptance pipeline, budget and cleanup checks are exercised. Hosted Windows and Linux replay, Chromium, and containment checks passed at the benchmark checkpoint. The wheel, Colab ZIP, and replay image carry the license and notice | Final local regression and release package checks passed |
| Demonstration | Three of three examples are verified within their declared scenarios. Desktop and mobile walkthroughs verified the execution graph, all three workflow replays, downloaded source and specifications, and the updated portfolio's live embed and full-screen fallback | Production Studio and portfolio verified |
| Research | Direct, structured and contained RLM completed an 18-trial schedule across Task Management, Operations Analytics and Aviation Operations. The expanded Operations suite includes sorting and CSV checks | The accepted benchmark and its measurement limits are recorded below |
| Portfolio and handoff | The case study, architecture diagram, screenshots, attribution, and handoff are published | Production navigation, screenshots, Studio embed, and full-screen fallback verified |
| Compute | A fresh local extraction ran the notebook cells, reused a completed checkpoint, recovered a seeded interrupted checkpoint, and exported CSV and ZIP. The Windows launcher also passed from the extracted archive | The owner reported Colab CPU batch `46597473698c60f5` complete. Drive-backed resume after runtime deletion is untested on Colab and was waived for this release |

## Roadmap

1. **Repository and release quality.** `python -S scripts/verify_checkout.py` verifies CPU replay and resume from a clean checkout. The [Verification workflow](https://github.com/jacobhroutzong/recursa/actions/workflows/verification.yml) tracks hosted Windows and Linux checks and an isolated Docker and Chromium job. The [setup guide](reproduction.md), [upstream attribution](attribution.md), and [Apache 2.0 license](../LICENSE) are ready.
2. **Research evaluation.** The expanded benchmark adds Aviation and the two Operations checks for sorting before pagination (`OPS-07`) and filtered CSV export (`OPS-09`). The [benchmark protocol](baseline-protocol.md) describes the two matched seed blocks, common limits, and measured denominators. Showcase runs and repair trials remain separate.
3. **Final demonstration and case study.** The Studio walkthrough, local portfolio verification suite, and desktop and mobile embed checks passed. [Portfolio record](portfolio.md)
4. **Reproduction and handoff.** The local launcher and notebook smoke path have been exercised. The owner reported the Colab CPU smoke result and waived the fresh-runtime resume check. [Reproduction guide](reproduction.md) · [Handoff](handoff.md)

The benchmark characterizes the three methods under one local model and budget. The owner accepted the current Studio and 18-trial benchmark as the feature-complete release baseline.

## Published milestone · COMPLETE

The Apache 2.0 release and updated portfolio went live on November 7, 2026.

- Source release `e5635ddeb7f458d64eb933e156b5315fe53b72f9`. The final regression passed 110 tests. Local notebook checks passed checkpoint reuse, recovery from a seeded interrupted checkpoint, and CSV and ZIP export. The packaged license and notice matched the repository files. [Source release](https://github.com/jacobhroutzong/recursa/commit/e5635ddeb7f458d64eb933e156b5315fe53b72f9)
- Studio release `d97e73bf7951b1f1ae9d7deed2cb9ed828c38c12`. Production returned the expected release record, all 18 expanded trial traces, and replay-only health. The mobile benchmark walkthrough passed, and the published license, notice, and attribution matched the staged files. [Space commit](https://huggingface.co/spaces/jacobroutzong/recursa/commit/d97e73bf7951b1f1ae9d7deed2cb9ed828c38c12) · [Live Studio](https://jacobroutzong-recursa.hf.space/#benchmarks)
- Portfolio release `15eab4e7866e204e71dc6b4a21d4bd0b9373c246`. The final portfolio suite passed 109 Node tests and 33 Vitest tests, plus build and link checks. Chromium verified the production case study, homepage and Projects links, screenshots, Studio embed, and full-screen fallback at 1440 and 390 pixels. [Portfolio commit](https://github.com/jacobhroutzong/portfolio-website/commit/15eab4e7866e204e71dc6b4a21d4bd0b9373c246) · [Production portfolio](https://jacobroutzong.dev/projects/recursa/)
- The 18-trial benchmark measured five Task Management builds. Two built successfully, and the resulting candidates passed 0 of 8 measured browser checks. Operations and Aviation stopped before build measurement, so their build and browser outcomes remain unmeasured. [Benchmark results](baseline-protocol.md#expanded-results)
- The owner reported Colab CPU batch `46597473698c60f5` complete and supplied checkpoint and run file hashes. Drive-backed resume after destroying a Colab runtime remains untested and was explicitly waived for this release.
