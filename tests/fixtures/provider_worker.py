"""Trusted offline transport interceptor; never use as an experiment backend."""
import json
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import httpx
from recursa import provider_worker


def intercepted(request):
    body = json.loads(request.content)
    text = body['messages'][0]['content']
    if text.startswith('hang:'):
        directory = Path(text[5:])
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])
        (directory / 'child-pid.txt').write_text(str(child.pid))
        (directory / 'started.txt').write_text('scripted transport entered')
        time.sleep(300)
    if text == 'http-error':
        return httpx.Response(500, json={'error': 'private-provider-body'})
    return httpx.Response(200, json={
        'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'fixture reply'}}],
        'usage': {'prompt_tokens': 5, 'completion_tokens': 3, 'total_tokens': 8},
    })


with patch('httpx.HTTPTransport', return_value=httpx.MockTransport(intercepted)):
    raise SystemExit(provider_worker.main())
