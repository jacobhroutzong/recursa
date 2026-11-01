# Official RLM inside the offline container lane

The official `rlms==0.1.3` adapter now runs inside the constrained Python container for fixed scripted integration fixtures. This is actual container/REPL execution with intercepted HTTP transport, **not genuine model inference**. The generic provider-enabled adapter still requires trusted local execution; a host-side provider gateway has not been implemented.

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

Only this fixed scripted fixture mode exists. Model request mediation outside the container, shared host-side provider budgets/credentials, complete private trace export and genuinely authorized model-backed application generation remain unfinished. The public service remains read-only CPU replay, with no container-launch or live-inference endpoint. These controls are narrow measured isolation evidence, not universal kernel exploit protection or benchmark results.
