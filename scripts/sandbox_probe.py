"""Reviewed container probe; cannot establish comprehensive sandbox security."""
import json
import os
from pathlib import Path
import socket

checks = {'nonroot_user': os.getuid() == 65532,
          'host_secret_absent': os.environ.get('RECURSA_SANDBOX_SENTINEL') is None,
          'docker_socket_absent': not Path('/var/run/docker.sock').exists()}
try:
    Path('/recursa-root-write').write_text('must fail')
    checks['root_write_blocked'] = False
except OSError:
    checks['root_write_blocked'] = True
Path('/work/scratch.txt').write_text('scratch allowed')
checks['scratch_writable'] = True
status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
checks['capabilities_dropped'] = int(status['CapEff'].strip(), 16) == 0
checks['no_new_privileges'] = status['NoNewPrivs'].strip() == '1'
checks['seccomp_filter'] = status['Seccomp'].strip() == '2'
quota, period = Path('/sys/fs/cgroup/cpu.max').read_text().split()
checks['cpu_quota_enforced'] = quota != 'max' and int(quota) <= int(period)
checks['memory_limit_enforced'] = Path('/sys/fs/cgroup/memory.max').read_text().strip() == str(256 * 1024 * 1024)
checks['pid_limit_enforced'] = Path('/sys/fs/cgroup/pids.max').read_text().strip() == '32'
try:
    with socket.create_connection(('198.51.100.1', 80), timeout=0.25):
        checks['external_connection_blocked'] = False
except OSError:
    checks['external_connection_blocked'] = True
print(json.dumps({'kind': 'reviewed-offline-container-probe', 'checks': checks}))
assert all(checks.values()), 'Container probe failed'
