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
from recursa.container_rlm import scripted_responses


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
    replies = scripted_responses()
    if body['model'] in {'reviewed-root', 'reviewed-sub'}:
        sentinel = 'REVIEWED_INPUT_6073'
        assert (sentinel in json.dumps(body['messages'])) == (body['model'] == 'reviewed-sub')
        replies = {model.replace('scripted-', 'reviewed-'): reply.replace('R1', 'TITLE-1')
                   for model, reply in replies.items()}
    if body['model'] in replies:
        assert request.headers['Authorization'] == 'Bearer fixture-host-provider-key'
    return httpx.Response(200, json={
        'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': replies.get(body['model'], 'fixture reply')}}],
        'usage': {'prompt_tokens': 5, 'completion_tokens': 3, 'total_tokens': 8},
    })


with patch('httpx.HTTPTransport', return_value=httpx.MockTransport(intercepted)):
    raise SystemExit(provider_worker.main())
