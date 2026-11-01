# Host-side model request mediation — scripted backend only

`recursa.broker.OfflineBroker` now mediates the contained official RLM's completion requests over bounded stdin/stdout pipes. The container keeps `network=none`; no host port, host mount, real credential or network-provider callback is exposed. Only fixed scripted text responses are implemented.

## Boundary

The owner-controlled broker fixes model names, reply strings, per-call output reservations and a shared `CallBudget`. Each request must be a JSON object with exactly `type`, sequential integer `id`, allowlisted `model` and text-only `messages`. URLs, headers, token overrides, unknown models, duplicate IDs, non-text payloads and oversized frames are rejected before dispatch. A protocol violation closes the broker. Failed or oversized response attempts keep their reservations. Error replies contain classification codes only.

The child cannot set provider configuration or change the host budget. Broker counters and prompt/response hashes are recorded by the host; the child's reported call/token counts are not authoritative. Captured protocol content stays bounded under `private/`; sanitized summaries contain hashes and host observations. Output-token reservations are allowances, not measured inference-token usage.

Requests use a versioned line prefix with bounded JSON frames. Responses travel back on the same private input pipe. Container entry point, command, working directory, stdin and TTY state are inspected before source dispatch, in addition to the existing user/network/filesystem/resource policy. The existing non-mediated container path remains available. Containers still share a kernel; these controls are not a universal sandbox-security claim.

## Actual observed verification

```powershell
python scripts/build_rlm_image.py
python scripts/verify_mediated_container.py --output runs/mediated-container-001
```

The dependency layer is cached; source changes require a source-matched runtime image. Three actual-container checks passed with the [recorded evidence](evidence/mediated-container-2026-10-31.json):

1. Official root/subcall flow: two scripted completions dispatched by the host, requirement inspection and a returned validated artifact.
2. Host budget denial: the child permits two calls, while the host permits one. The host denies the subcall before its scripted backend dispatch and no artifact is claimed.
3. Request override rejection: a container attempts to supply a URL; the host rejects it with zero reservations and zero dispatches.

A dedicated host-only sentinel was set during the suite and was absent inside both RLM fixtures. Container policy and cleanup were verified in all cases. The five basic isolation/resource probes and the two earlier contained-RLM fixtures were rerun successfully after the protocol change. Unit tests also cover replay, response expansion, input byte limits, unknown models and sanitized rejection.

## Remaining work

The broker still has no live-provider dispatch path. A separate [host provider adapter](provider-adapter.md) now has intercepted HTTP tests for authorization, fixed settings, retained reservations, usage reconciliation and sanitized failures. It is not connected to the runner, which accepts only the concrete offline broker type. Supervised provider execution, broker integration, independently authorized endpoint/model selection, full private trace export and genuine application-generation evaluation remain open. A generic “continue” cannot initiate inference. Public hosting remains CPU replay-only with no execution or broker endpoint.
