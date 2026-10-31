# Local container execution policy — runtime verification pending

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

## Actual evidence and current blocker

Policy tests reject mutable/malicious image arguments, weakened engine metadata, host mounts/devices, injected environment, missing engine and timed-out preflight. A policy-rejected mocked container is removed before source dispatch. Mocked Docker metadata is **not** evidence of runtime isolation.

On October 31, 2026, Docker Desktop was installed and was started with its supported CLI. Its backend processes appeared, but bounded Linux-engine readiness requests continued to time out. A restart attempt also timed out; its lingering CLI helper was identified and stopped without terminating the engine or other containers. No container was executed, no image was pulled, and no runtime probe passed. Runtime isolation remains **unverified**. The real RLM REPL remains restricted to trusted offline fixtures, live batching remains disabled, and the public site remains CPU replay-only. The next runtime gate requires the local engine to finish startup, a reviewed cached image, the measured probe, and container timeout/resource/output cleanup tests.
