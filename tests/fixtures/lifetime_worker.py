"""Trusted offline worker used only by process-boundary regression tests."""
import json
import os
from pathlib import Path
import subprocess
import sys

# No work, child launch or RLM execution happens before the parent's stdin gate.
config = json.loads(sys.stdin.buffer.read())
root = Path(config['directory'])


def mark_started():
    heartbeat = root / 'heartbeat.txt'
    code = 'import pathlib,time\np=pathlib.Path(' + repr(str(heartbeat)) + ')\nwhile True:\n p.write_text(str(time.time_ns()))\n time.sleep(0.05)'
    child = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    (root / 'child-pid.txt').write_text(str(child.pid))
    (root / 'started.txt').write_text('started')
    return 'started'


if config['mode'] == 'spawn-exit':
    mark_started()
elif config['mode'] == 'spawn-hang':
    import time
    mark_started()
    time.sleep(60)
elif config['mode'] == 'hang-rlm':
    import httpx
    import openai
    from unittest.mock import patch
    from rlm import RLM
    original = openai.OpenAI
    def transport(request):
        body = json.loads(request.content)
        return httpx.Response(200, json={'id': 'offline', 'object': 'chat.completion', 'created': 0,
            'model': body['model'], 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content':
                '```repl\nmark_started()\nimport time\ntime.sleep(60)\n```'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}})
    def factory(**kwargs):
        return original(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    with patch('openai.OpenAI', side_effect=factory):
        controller = RLM(backend='openai', backend_kwargs={'model_name': 'scripted-only', 'api_key': 'offline-placeholder',
            'base_url': 'http://127.0.0.1:9999/v1', 'max_retries': 0}, environment='local',
            max_depth=1, max_iterations=1, max_timeout=90, custom_tools={'mark_started': mark_started})
        controller.completion({'fixture': 'No real inference'})
else:
    raise ValueError('Unknown fixture mode')
