# Local container execution — narrow runtime checks verified

The existing Windows job boundary terminates workers and descendants but does not restrict filesystem/network access. `recursa.sandbox` adds an opt-in Linux-container runner with no host-execution fallback. It is separate from the public replay service and is not yet connected to genuine model inference.

## What is implemented

- Explicit locally reviewed `sha256:` image ID, local Docker endpoint only, and `--pull=never`.
- Read-only root filesystem, user `65532:65532`, all capabilities dropped, no new privileges, private IPC/cgroup namespace.
- No host mounts, Docker socket, published ports, GPUs, added devices or network connectivity.
- One CPU, 256 MiB memory with the same total memory/swap cap, 32 PIDs, bounded file descriptors, 64 MiB scratch and 16 MiB temporary space.
- Workload/context passed over stdin only after inspected container settings match the policy. The host environment is not forwarded into the container. Unexpected environment injection, including Docker proxy defaults, rejects the container before dispatch.
- Combined stdout/stderr capture limited to 1 MiB under `private/`; those bytes are untrusted. Source/context and hashes are saved locally. Exit zero means only that the process exited successfully; functional success remains null.
- Deadline/output-limit/cancellation cleanup removes only this run's container. A timed-out create attempts ownership-checked recovery using its unique name and label. Cleanup failure is explicitly reported.

The supported Docker flags are documented in [Docker's container run reference](https://docs.docker.com/reference/cli/docker/container/run/). Containers share a kernel and this policy is not a claim of VM isolation or universal protection against kernel exploits. Images must be independently reviewed; pinning an arbitrary image does not make its contents trustworthy.

## Reproduction when Docker is ready

The runner never pulls or builds an image automatically. Once the local Linux engine responds and a reviewed Python image is already cached, inspect its immutable ID:

```powershell
docker image inspect python:3.12-slim --format '{{.Id}}'
python -m recursa.sandbox --image sha256:REPLACE_WITH_REVIEWED_LOCAL_ID --output runs/container-probe-001
```

The second command runs `scripts/sandbox_probe.py`, which checks non-root identity, root-write denial, scratch writes, capability/privilege/seccomp state, absent Docker socket and host sentinel environment variable, and a blocked external connection attempt. The report and bounded private probe output must be reviewed together. These narrow checks cannot prove comprehensive sandbox security.

## Actual evidence and remaining gate

Policy tests reject mutable/malicious image arguments, weakened engine metadata, host mounts/devices, injected environment, missing engine and timed-out preflight. A policy-rejected mocked container is removed before source dispatch. Mocked Docker metadata is **not** evidence of runtime isolation.

Initial readiness and restart attempts timed out. Later on October 31, 2026, the owner confirmed Desktop showed Running; the local Linux endpoint then responded with Docker 29.9.2. The official `python:3.12-slim` image was explicitly downloaded and pinned to the immutable image ID and registry digest recorded in `configs/container-image.json`. The runner itself still never pulls images.

Five real-container cases passed, with sanitized evidence in [container-2026-10-31.json](evidence/container-2026-10-31.json): the reviewed identity/filesystem/network/privilege probe, a 5-second timeout, 4 KiB combined-output enforcement, a 512 MiB allocation stopped by the 256 MiB memory cap (exit 137, OOM killed), and process creation denied at the configured PID cap. Every case verified policy settings before dispatch and confirmed container cleanup. The probe additionally checked actual cgroup CPU, memory and PID controls. These are observed narrow controls on this Linux/amd64 image, not comprehensive kernel exploit protection or model-generation evidence.

Reproduce the explicit measured suite after the pinned image is cached:

```powershell
$recursaImage = (Get-Content configs/container-image.json | ConvertFrom-Json).image_id
python scripts/verify_container.py --image $recursaImage --output runs/container-verify-001
```

The official RLM adapter now also runs inside a pinned SDK image for fixed [offline scripted fixtures](contained-rlm.md), without real credentials or provider access. Genuine model requests still need a mediated host-side gateway and explicit authorization. Live batching remains disabled; the public site remains CPU replay-only.
