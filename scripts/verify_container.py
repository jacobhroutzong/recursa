"""Explicit real-container verification; no model calls, no image pulls."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recursa.experiments import atomic_json
from recursa.sandbox import run_python


def verify(image, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Use a fresh evidence directory')
    output.mkdir(parents=True)
    cases = []
    probe = (ROOT / 'scripts/sandbox_probe.py').read_text(encoding='utf-8')
    sources = [
        ('policy-probe', probe, 30, 1048576),
        ('timeout', 'import time\nprint("started",flush=True)\ntime.sleep(60)', 5, 1048576),
        ('output-limit', 'import sys\nsys.stdout.write("x" * 2000000)\nsys.stdout.flush()', 20, 4096),
        ('memory-limit', 'buffer = bytearray(512 * 1024 * 1024)\nprint(len(buffer))', 20, 1048576),
        ('pid-limit', '''import subprocess,sys,json
children=[]
denied=False
try:
 for index in range(40):
  try: children.append(subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']))
  except OSError:
   denied=True
   break
 print(json.dumps({'denied':denied,'spawned':len(children)}),flush=True)
 assert denied and len(children)<40
finally:
 for child in children: child.terminate()
 for child in children: child.wait(timeout=2)
''', 20, 1048576)]
    os.environ['RECURSA_SANDBOX_SENTINEL'] = 'offline-probe-placeholder'
    try:
        for name, source, seconds, cap in sources:
            folder = output / name
            report = run_python(source, image, folder, max_wall_seconds=seconds, max_output_bytes=cap)
            stdout = folder / 'private/stdout.bin'
            stderr = folder / 'private/stderr.bin'
            row = {'name': name, **{k: report.get(k) for k in ('status', 'policy_verified', 'cleanup_verified', 'returncode', 'oom_killed', 'source_sha256', 'stdout_sha256', 'stderr_sha256')},
                   'stdout_bytes': stdout.stat().st_size if stdout.exists() else 0,
                   'stderr_bytes': stderr.stat().st_size if stderr.exists() else 0}
            cases.append(row)
            atomic_json(output / 'verification.json', {'image_id': image, 'cases': cases, 'status': 'in-progress', 'live_inference': False})
            assert report['policy_verified'] and report['cleanup_verified'], row
            if name == 'policy-probe':
                result = json.loads(stdout.read_text())
                row['checks'] = result['checks']
                assert report['status'] == 'completed' and all(result['checks'].values()), row
            elif name == 'timeout':
                assert report['status'] == 'timeout' and b'started' in stdout.read_bytes(), row
            elif name == 'output-limit':
                assert report['status'] == 'output-limit' and row['stdout_bytes'] + row['stderr_bytes'] <= cap, row
            elif name == 'memory-limit':
                assert report['status'] == 'failed' and report.get('oom_killed') is True, row
            else:
                assert report['status'] == 'completed' and json.loads(stdout.read_text())['denied'] is True, row
    except BaseException:
        atomic_json(output / 'verification.json', {'image_id': image, 'cases': cases, 'status': 'failed', 'live_inference': False})
        raise
    finally:
        os.environ.pop('RECURSA_SANDBOX_SENTINEL', None)
    summary = {'image_id': image, 'cases': cases, 'status': 'passed', 'live_inference': False,
               'scope': 'Five reviewed local container probes; not model synthesis or universal sandbox assurance'}
    atomic_json(output / 'verification.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.image, args.output)
    print(json.dumps({'status': result['status'], 'cases': len(result['cases']), 'live_inference': False}))
