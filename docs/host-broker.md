# Host-side model request mediation

The host broker receives bounded completion frames from the contained runtime. `OfflineBroker` supplies fixed scripted responses. `ProviderBroker` requires explicit authorization and creates a supervised host adapter from fixed endpoint, credential environment variable, model pricing and budget settings. The container retains `network=none` and communicates over private pipes.

## Boundary

The host fixes model names, per-call output reservations and a shared `CallBudget`. Each request must be a JSON object with exactly `type`, sequential integer `id`, allowlisted `model` and text-only `messages`. URLs, headers, token overrides, unknown models, duplicate IDs, non-text payloads and oversized frames are rejected before dispatch. A protocol violation closes the broker. Failed or oversized response attempts keep their reservations. Error replies contain classification codes only.

The child cannot set provider configuration or change the host budget. Broker counters and prompt/response hashes are recorded by the host; the child's reported call/token counts are not authoritative. Captured protocol content stays bounded under `private/`; sanitized summaries contain hashes and host observations. Output-token reservations are allowances, not measured inference-token usage.

Requests use a versioned line prefix with bounded JSON frames. Responses travel back on the same private input pipe. Container entry point, command, working directory, stdin and TTY state are inspected before source dispatch, in addition to the existing user/network/filesystem/resource policy. Bounded queues separate pipe reads and writes from the supervisor thread. The supervisor dispatches requests so cancellation reaches the provider worker, and the worker uses the earlier of the container and provider deadlines. Container output and provider response files are private.

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

The supervised integration adds two actual-container cases. One passes the scripted root and subcall through separate supervised workers and validates the returned artifact. The other caps the host at one call and verifies that the subcall is denied before a second worker starts. Both intercept HTTP in the worker. [Integration evidence](evidence/mediated-container-2026-11-07.json)

## Remaining work

The contained official RLM launcher currently uses a fixed specification fixture. A general runner for reviewed specifications, private trace export and model-backed application generation remain open. The genuine run requires explicit owner authorization and configured provider limits. Public hosting serves CPU replays and progress.
