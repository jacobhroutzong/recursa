# Recursa handoff

Recursa is a research workbench for turning reviewed specifications into web application candidates and inspecting the evidence behind each run. The local pipeline combines an official RLM controller, indexed context, mediated model calls, and independent browser verification. The CPU-hosted Studio exposes reviewed records and replays. [Architecture](architecture.md)

## Verification and findings

| Gate | Recorded evidence |
| --- | --- |
| Genuine inference | An authorized Qwen run recorded context inspection and a subcall. The first Task Management build failed browser acceptance. The repaired, host-composed showcase passed four declared workflows. [Run evidence](evidence/task-management-local-model.md) |
| Application evidence | The Task Management, Operations Analytics, and Aviation Operations showcases each have source, a Chromium capture, and four recorded workflows. The Operations and Aviation records disclose host corrections or assembly. [Generated artifacts](https://jacobroutzong-recursa.hf.space/#artifacts) |
| Engineering verification | The published benchmark revision passed 110 local tests, both hosted CPU replay lanes, and hosted Chromium and Linux containment. Artifact dependencies and provenance are exercised by build and boundary checks. [GitHub run](https://github.com/jacobhroutzong/recursa/actions/runs/42421876298) |
| Research | The expanded series ran 18 matched trials. Five Task Management candidates reached build measurement, two built, and the two builds passed 0 of 8 browser checks. Operations and Aviation outcomes remained unmeasured at build and browser stages. [Protocol and results](baseline-protocol.md#expanded-results) |
| Public demo | The current public release serves 45 versioned benchmark traces and the three workflow replays. No key is needed to inspect recorded evidence. [Execution Explorer](https://jacobroutzong-recursa.hf.space/#execution) |
| Reproduction | The local and Colab procedures are documented. The owner reported a successful Colab CPU smoke run for batch `46597473698c60f5`. Drive-backed resume after runtime deletion is untested on Colab and was waived for this release. GPU model and training-state recovery remain research opportunities. [Reproduction guide](reproduction.md) |
| Portfolio | The case study, screenshots, diagram, and live Studio embed passed prepublication checks. [Portfolio record](portfolio.md) |

## Artifacts and deployment

The [repository](https://github.com/jacobhroutzong/recursa) contains the implementation, [reviewed specifications](../examples/specs/), [public trace archive](../apps/studio/benchmark-traces.json), [screenshot](screenshots/studio.png), and [Colab notebook](../notebooks/recursa_colab.ipynb). Local run folders retain raw model traffic and generated candidates for private review. The public deployment contains only allowlisted recordings, source from reviewed showcases, and replay assets.

The Space and portfolio serve the verified milestone release. The completion checkpoint records the deployed revisions, final checks, benchmark results, and Colab limitation. [Live Space](https://huggingface.co/spaces/jacobroutzong/recursa) · [Production portfolio](https://jacobroutzong.dev/projects/recursa/) · [Completion checkpoint](completion-checkpoint.md#published-milestone--complete)

## Engineering opportunities

1. Predeclare a larger-context local study and compare it against a nonrecursive baseline with equivalent context handling.
2. Run isolated ablations for adaptive inspection, subcalls, contract checks and repair after the broader study has enough browser measurements.
3. Add model-state recovery only when a concrete Colab workload warrants it. Preserve existing between-trial CPU checkpoints as the default.
