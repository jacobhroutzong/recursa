"""Opt-in local Docker execution. No image pulls, host mounts or host fallback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid

from recursa.budget import BudgetExceeded, Deadline
from recursa.experiments import atomic_json

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = "import json,sys; p=json.load(sys.stdin); exec(compile(p['source'],'<recursa-sandbox>','exec'),{'__name__':'__main__','context':p.get('context')})"
ENDPOINT = 'npipe:////./pipe/dockerDesktopLinuxEngine' if os.name == 'nt' else 'unix:///var/run/docker.sock'


def create_arguments(image, name):
    if not isinstance(image, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('Use an explicit, locally reviewed immutable image ID')
    if not re.fullmatch(r'recursa-[0-9a-f]{32}', name):
        raise ValueError('Invalid sandbox container name')
    return ['container', 'create', '--pull=never', '--name', name, '--label', 'recursa.sandbox=' + name,
            '--interactive', '--network=none', '--read-only', '--user=65532:65532',
            '--cap-drop=ALL', '--security-opt=no-new-privileges=true', '--ipc=private', '--cgroupns=private',
            '--cpus=1', '--memory=256m', '--memory-swap=256m', '--pids-limit=32',
            '--ulimit=nofile=128:128', '--log-driver=none',
            '--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777',
            '--tmpfs=/work:rw,nosuid,nodev,noexec,size=64m,uid=65532,gid=65532,mode=700',
            '--workdir=/work', '--env=HOME=/tmp', '--env=PYTHONDONTWRITEBYTECODE=1',
            '--entrypoint=python', image, '-I', '-c', BOOTSTRAP]


def policy_matches(container, image, name, image_environment):
    """Verify observed engine configuration before releasing any source bytes."""
    h, c = container.get('HostConfig', {}), container.get('Config', {})
    security = set(h.get('SecurityOpt') or [])
    tmp = h.get('Tmpfs') or {}
    expected_environment = dict(item.split('=', 1) for item in image_environment)
    expected_environment.update(HOME='/tmp', PYTHONDONTWRITEBYTECODE='1')
    observed_environment = dict(item.split('=', 1) for item in c.get('Env', []))
    return (container.get('Image') == image and c.get('User') == '65532:65532'
        and observed_environment == expected_environment
        and c.get('Labels', {}).get('recursa.sandbox') == name
        and h.get('NetworkMode') == 'none' and h.get('ReadonlyRootfs') is True
        and not h.get('Privileged') and not h.get('CapAdd') and set(h.get('CapDrop') or []) == {'ALL'}
        and bool(security & {'no-new-privileges=true', 'no-new-privileges:true', 'no-new-privileges'})
        and h.get('Memory') == 256 * 1024 * 1024 and h.get('MemorySwap') == 256 * 1024 * 1024
        and h.get('NanoCpus') == 1000000000 and h.get('PidsLimit') == 32
        and h.get('IpcMode') == 'private' and h.get('CgroupnsMode') == 'private'
        and not h.get('Binds') and not h.get('Mounts') and not h.get('Devices') and not h.get('DeviceRequests')
        and not h.get('ExtraHosts') and not h.get('GroupAdd') and not any('unconfined' in s for s in security)
        and not h.get('PortBindings') and not h.get('PublishAllPorts') and not h.get('PidMode')
        and h.get('LogConfig', {}).get('Type') == 'none'
        and not any(m.get('Type') != 'tmpfs' for m in container.get('Mounts', []))
        and set(tmp) == {'/tmp', '/work'}
        and all(flag in tmp['/work'].split(',') for flag in ('noexec', 'nosuid', 'nodev', 'size=64m', 'uid=65532', 'gid=65532'))
        and all(flag in tmp['/tmp'].split(',') for flag in ('noexec', 'nosuid', 'nodev', 'size=16m')))


def run_python(source, image, output_dir, *, context=None, max_wall_seconds=30, max_output_bytes=1048576):
    """Execute Python only after a local engine and hardened policy are verified.

    Container output is untrusted, bounded, and private. Exit zero does not prove
    task correctness. Docker containers share a kernel; this is not a VM claim.
    """
    name = 'recursa-' + uuid.uuid4().hex
    arguments = create_arguments(image, name)
    if not isinstance(source, str) or len(source.encode()) > 100000:
        raise ValueError('Source must be bounded text')
    payload = json.dumps({'source': source, 'context': context}, allow_nan=False).encode()
    if len(payload) > 500000 or type(max_output_bytes) is not int or not 1024 <= max_output_bytes <= 1048576:
        raise ValueError('Sandbox input/output exceeds bounds')
    if type(max_wall_seconds) not in (int, float) or not 0 < max_wall_seconds <= 120:
        raise ValueError('Sandbox wall budget must be positive and at most 120 seconds')
    deadline = Deadline(max_wall_seconds)
    directory = Path(output_dir).resolve()
    if directory.exists():
        raise ValueError('Use a fresh output directory')
    (directory / 'private').mkdir(parents=True)
    report = {'status': 'unavailable', 'image_id': image, 'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
              'live_inference': False, 'policy_verified': False, 'cleanup_verified': None,
              'returncode': None, 'functional_success': None, 'max_wall_seconds': max_wall_seconds,
              'scope': 'Local container process result only; untrusted output is not research evidence'}
    atomic_json(directory / 'input.json', {'source': source, 'context': context, 'image_id': image})
    executable = shutil.which('docker')
    container_id = None
    process = None
    overflow = threading.Event()
    create_attempted = False
    readers = []
    environment = {k: v for k, v in os.environ.items() if not k.upper().startswith('DOCKER_')}

    def command(args, timeout):
        return subprocess.run([executable, '--host', ENDPOINT, *args], capture_output=True, timeout=timeout, env=environment)

    def decoded(args):
        result = command(args, deadline.remaining(10))
        if result.returncode:
            raise RuntimeError('Docker command unavailable')
        return json.loads(result.stdout)

    try:
        if not executable:
            return report
        engine = decoded(['info', '--format', '{{json .OSType}}'])
        if engine != 'linux':
            raise RuntimeError('Linux engine required')
        inspected = decoded(['image', 'inspect', image])[0]
        if inspected.get('Id') != image or inspected.get('Os') != 'linux':
            raise RuntimeError('Reviewed local Linux image unavailable')
        create_attempted = True
        created = command(arguments, deadline.remaining(10))
        candidate = created.stdout.decode().strip()
        if created.returncode or not re.fullmatch(r'[0-9a-f]{64}', candidate):
            raise RuntimeError('Container creation unavailable')
        container_id = candidate
        observed = decoded(['container', 'inspect', container_id])[0]
        if not policy_matches(observed, image, name, inspected.get('Config', {}).get('Env', [])):
            report['status'] = 'policy-rejected'
            return report
        report['policy_verified'] = True
        report['container_id'] = container_id
        atomic_json(directory / 'policy.json', {'HostConfig': observed['HostConfig'], 'image_id': image, 'user': observed['Config']['User']})
        report['status'] = 'running'
        atomic_json(directory / 'sandbox-report.json', report)
        process = subprocess.Popen([executable, '--host', ENDPOINT, 'container', 'start', '--attach', '--interactive', container_id],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        output_lock = threading.Lock()
        total = 0

        def drain(stream, target):
            nonlocal total
            with target.open('wb') as output:
                while chunk := stream.read(4096):
                    with output_lock:
                        keep = max(0, min(len(chunk), max_output_bytes - total))
                        total += keep
                        output.write(chunk[:keep])
                        if keep < len(chunk):
                            overflow.set()

        def send():
            try:
                process.stdin.write(payload)
                process.stdin.close()
            except (OSError, ValueError):
                pass

        for stream, filename in ((process.stdout, 'stdout.bin'), (process.stderr, 'stderr.bin')):
            reader = threading.Thread(target=drain, args=(stream, directory / 'private' / filename), daemon=True)
            reader.start()
            readers.append(reader)
        threading.Thread(target=send, daemon=True).start()
        while process.poll() is None:
            if overflow.is_set():
                report['status'] = 'output-limit'
                break
            try:
                process.wait(timeout=min(0.1, deadline.remaining()))
            except subprocess.TimeoutExpired:
                pass
        else:
            state = decoded(['container', 'inspect', container_id])[0]['State']
            report['returncode'] = state.get('ExitCode')
            report['oom_killed'] = state.get('OOMKilled')
            report['status'] = 'completed' if state.get('ExitCode') == 0 else 'failed'
    except (BudgetExceeded, subprocess.TimeoutExpired):
        report['status'] = 'timeout' if container_id else 'unavailable'
        report['error_classification'] = 'DeadlineExceeded'
    except KeyboardInterrupt:
        report['status'] = 'cancelled'
        raise
    except (OSError, ValueError, RuntimeError, KeyError, IndexError) as error:
        report['status'] = 'error' if container_id else 'unavailable'
        report['error_classification'] = type(error).__name__
    finally:
        if create_attempted and not container_id:
            # A timed-out create may still have reached the daemon. Recover only
            # this run's generated name with its matching ownership label.
            try:
                found = command(['container', 'inspect', name], 10)
                if found.returncode == 0:
                    owned = json.loads(found.stdout)[0]
                    candidate = owned.get('Id', '')
                    if owned.get('Config', {}).get('Labels', {}).get('recursa.sandbox') == name and re.fullmatch(r'[0-9a-f]{64}', candidate):
                        container_id = candidate
            except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
                report['cleanup_verified'] = False
                report['status'] = 'cleanup-failed'
        if container_id:
            try:
                removed = command(['container', 'rm', '--force', container_id], 10)
                report['cleanup_verified'] = removed.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                report['cleanup_verified'] = False
            if not report['cleanup_verified']:
                report['status'] = 'cleanup-failed'
        if process:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            for reader in readers:
                reader.join(timeout=2)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream:
                    stream.close()
            if overflow.is_set() and report['status'] in {'completed', 'failed'}:
                report['status'] = 'output-limit'
        for path in (directory / 'private').glob('*.bin'):
            report[path.stem + '_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        atomic_json(directory / 'sandbox-report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, help='Reviewed local sha256 image ID; no pulling')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = (ROOT / 'scripts/sandbox_probe.py').read_text(encoding='utf-8')
    report = run_python(source, args.image, args.output)
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'completed' and report['cleanup_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
