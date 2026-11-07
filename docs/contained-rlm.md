# Official RLM inside the offline container lane

The official `rlms==0.1.3` adapter runs inside a constrained Python container. The host broker mediates completion requests over bounded pipes and owns provider access. The verification fixtures exercise the actual container and REPL with intercepted model responses. [Host broker](host-broker.md)

## Build once, then verify

```powershell
python scripts/build_rlm_image.py
python scripts/verify_rlm_container.py --output runs/contained-rlm-001
```

The builder uses the pinned official Python base digest in `configs/container-image.json`. Its dedicated build context contains only the Recursa Python modules, the pinned dependency lock and a generated fixed Dockerfile. No workspace credentials, private runs, host configuration or arbitrary project files are copied. The installed packages are the exact versions in `requirements-live.lock`. Dependency setup uses the network; inference does not. Subsequent source rebuilds reuse the dependency layer.

A stdin-gated launcher is attached to the existing Windows lifetime boundary before the Docker build CLI starts. The resulting immutable image ID, module/requirements hash and platform are saved to `.cache/rlm-runtime-image.json`. The parent rejects a stale source hash or mismatched image before executing a fixture. Runtime containers retain the existing no-network/no-host-mount/non-root/read-only/capability/resource policy and never receive real provider credentials.

## Measured results

The two-case suite passed on October 31, 2026. Sanitized [contained-rlm evidence](evidence/contained-rlm-2026-10-31.json) records the image and source identities, returned artifact hash and container cleanup:

- Inspection/subcall/artifact: a sentinel requirement remains outside the initial root messages, is read through the indexed tool, and reaches the upstream `llm_query()` subcall. A scripted artifact is submitted through the task graph and returned. The parent independently validates its path and requirement references before writing it.
- Exhaustion: a one-call budget permits only the scripted root request, prevents subcall HTTP dispatch, returns `budget-exhausted` and preserves the structured partial result in the bounded private stdout capture. No artifact is fabricated. Container policy and cleanup pass in both cases.

The source response and token-usage values are controlled fixture data. The parent labels all results `offline-scripted-container` with `live_inference=false`; these outputs are not added to public model-replay archives. Upstream diagnostics and temporary trajectories stay inside scratch and are discarded when the container is removed. The bounded private stdout capture preserves the returned structured run metadata; fuller bounded private trajectory export remains future work.

## Remaining gate

The remaining evidence gaps are an authorized model run and model-backed application verification. Public Studio serves CPU replays and progress.


## Reviewed specifications

The local runner accepts a reviewed JSON specification and an explicit provider configuration. Use `configs/live.example.json` as a starting point for a private copy. Set the root and subcall models, endpoint, pricing estimates, and call, input, output, cost, and time limits. Store the credential in the named host environment variable. The contained runner supports one trial with zero repair attempts and uses the specification supplied on the command line.

After reviewing the specification and authorizing model calls, build the pinned image with `python scripts/build_rlm_image.py` and run:

```powershell
python -m recursa.container_rlm --spec examples/specs/tasks.json --config private-config.json --image sha256:<local-image-id> --output runs/reviewed-001 --authorize-live
```

The container receives the specification, selected model names, and a local transport placeholder. The host broker owns the real endpoint, credential lookup, and call budget. The parent accepts a single bounded result, validates artifact paths and requirement IDs, and writes byte-preserving source files. `source-returned` means the source passed these checks and the run reported context inspection and a completed subcall. Functional success stays null. Container claims, broker observations, and provider-reported usage are kept distinct in `reviewed-report.json`.

Specifications are limited to 200,000 encoded bytes and result frames to 128 KiB. The run permits up to 64 calls, 32 iterations, and 120 seconds. Browser verification and repair are separate from this runner. Provider responses and container streams remain under the private run directory. Do not publish the output directory.

The offline verification runs a reviewed title-validator specification through an actual container and supervised worker. The host worker intercepts both model requests. A second case confirms that a one-call budget denies the subcall. [Verification record](evidence/reviewed-container-2026-11-07.json)


## Open a private replay in Studio

After the runner returns, select **Import run** in Studio and open `private/studio-replay.json` from that run directory. The file is loaded into the browser session. It includes host broker outcomes and budget counters, container policy and cleanup observations, and separately labeled context and subcall claims from the container. The trace is grouped by evidence source and has no event durations. Source remains in the run directory.

The replay omits specification text, messages, endpoint settings, model aliases, provider response bodies, and source contents. The archive excludes private directories, generated artifact directories, and any run marked with private visibility. Fixture replays carry unknown inference provenance and unmeasured functional success. Chromium checks at widths of 1280 and 390 pixels verified file import, trace inspection, unavailable duration display, and browser-only handling. [Container replay verification](evidence/private-replay-2026-11-07.json)
