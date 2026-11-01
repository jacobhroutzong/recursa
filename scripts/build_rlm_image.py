"""Build an allowlisted local RLM runtime image. Never includes host credentials."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recursa.container_rlm import runtime_source_hash
from recursa.experiments import atomic_json
from recursa.processes import run_worker
from recursa.sandbox import ENDPOINT


def build():
    base = json.loads((ROOT / 'configs/container-image.json').read_text())
    source_hash = runtime_source_hash()
    directory = ROOT / '.cache/rlm-runtime-images' / source_hash[:16]
    context = directory / 'context'
    (context / 'recursa').mkdir(parents=True, exist_ok=True)
    for path in (ROOT / 'recursa').glob('*.py'):
        shutil.copyfile(path, context / 'recursa' / path.name)
    shutil.copyfile(ROOT / 'requirements-live.lock', context / 'requirements-live.lock')
    digest = base['repo_digests'][0]
    if not digest.startswith('python@sha256:') or len(digest.split(':')[-1]) != 64:
        raise ValueError('Pinned official Python digest required')
    dockerfile = f'''FROM {digest}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements-live.lock /opt/recursa/requirements-live.lock
RUN python -m pip install --no-cache-dir --disable-pip-version-check -r /opt/recursa/requirements-live.lock
COPY recursa /usr/local/lib/python3.12/site-packages/recursa
LABEL recursa.runtime.source-sha256="{source_hash}"
USER 65532:65532
WORKDIR /work
'''
    (context / 'Dockerfile').write_text(dockerfile, encoding='utf-8')
    image_file = directory / 'image-id.txt'
    docker = shutil.which('docker')
    if not docker:
        raise RuntimeError('Local Docker CLI unavailable')
    arguments = [docker, '--host', ENDPOINT, 'build', '--quiet', '--platform=linux/amd64',
                 '--iidfile', str(image_file), str(context)]
    # The trusted launcher waits on stdin until the Windows job is attached.
    gate = "import json,os,subprocess,sys; args=json.load(sys.stdin); env={k:v for k,v in os.environ.items() if not k.upper().startswith('DOCKER_')}; raise SystemExit(subprocess.call(args,env=env))"
    result = run_worker([sys.executable, '-c', gate], json.dumps(arguments).encode(), timeout=300, cwd=ROOT)
    atomic_json(directory / 'build-report.json', result)
    if result['status'] != 'complete' or not image_file.exists():
        raise RuntimeError('Runtime image build failed; no host fallback')
    image = image_file.read_text().strip()
    import re
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('Invalid built image identity')
    record = {'image_id': image, 'base_image_repo_digest': digest, 'platform': 'linux/amd64',
              'runtime_source_sha256': source_hash, 'requirements_sha256': hashlib.sha256((ROOT / 'requirements-live.lock').read_bytes()).hexdigest(),
              'scope': 'Local pinned SDK image for offline container fixtures; no provider gateway'}
    atomic_json(ROOT / '.cache/rlm-runtime-image.json', record)
    print(json.dumps(record, indent=2))
    return record


if __name__ == '__main__':
    build()
