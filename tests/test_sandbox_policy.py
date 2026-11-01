"""Policy/failure tests only. Mocked Docker metadata is NOT isolation evidence."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from recursa.sandbox import create_arguments, policy_matches, run_python, BOOTSTRAP

IMAGE = 'sha256:' + 'a' * 64
NAME = 'recursa-' + 'b' * 32
CID = 'c' * 64


def metadata(name=NAME):
    return {'Id': CID, 'Image': IMAGE, 'State': {'Status': 'created'}, 'Config': {'User': '65532:65532', 'Labels': {'recursa.sandbox': name},
            'Entrypoint': ['python'], 'Cmd': ['-I', '-c', BOOTSTRAP], 'WorkingDir': '/work', 'OpenStdin': True, 'Tty': False,
            'Env': ['PATH=/usr/local/bin', 'HOME=/tmp', 'PYTHONDONTWRITEBYTECODE=1']},
            'Mounts': [], 'HostConfig': {'NetworkMode': 'none', 'ReadonlyRootfs': True, 'CapDrop': ['ALL'],
            'SecurityOpt': ['no-new-privileges=true'], 'Memory': 268435456, 'MemorySwap': 268435456,
            'NanoCpus': 1000000000, 'PidsLimit': 32, 'IpcMode': 'private', 'CgroupnsMode': 'private',
            'LogConfig': {'Type': 'none'}, 'Tmpfs': {
                '/tmp': 'rw,nosuid,nodev,noexec,size=16m,mode=1777',
                '/work': 'rw,nosuid,nodev,noexec,size=64m,uid=65532,gid=65532,mode=700'}}}


class SandboxPolicyTests(unittest.TestCase):
    def test_rejects_mutable_images_and_argument_injection(self):
        for image in ('python:latest', '--privileged', 'sha256:' + 'a' * 63, IMAGE + ';echo bad'):
            with self.assertRaises(ValueError):
                create_arguments(image, NAME)
        args = create_arguments(IMAGE, NAME)
        self.assertIn('--pull=never', args)
        self.assertNotIn('--volume', args)

    def test_observed_policy_rejects_weakened_limits_mounts_and_environment(self):
        self.assertTrue(policy_matches(metadata(), IMAGE, NAME, ['PATH=/usr/local/bin']))
        for field, value in [('NetworkMode', 'host'), ('Privileged', True), ('Memory', 0), ('NanoCpus', 0),
                             ('Binds', ['/host:/host']), ('DeviceRequests', [{'Count': -1}]), ('CapAdd', ['SYS_ADMIN'])]:
            changed = metadata()
            changed['HostConfig'][field] = value
            self.assertFalse(policy_matches(changed, IMAGE, NAME, ['PATH=/usr/local/bin']), field)
        changed = metadata()
        changed['Config']['Env'].append('HTTPS_PROXY=private-proxy-placeholder')
        self.assertFalse(policy_matches(changed, IMAGE, NAME, ['PATH=/usr/local/bin']))
        for field, value in [('Entrypoint', ['sh']), ('WorkingDir', '/'), ('Tty', True)]:
            changed = metadata()
            changed['Config'][field] = value
            self.assertFalse(policy_matches(changed, IMAGE, NAME, ['PATH=/usr/local/bin']))

    def test_unavailable_engine_never_falls_back_to_host(self):
        with tempfile.TemporaryDirectory() as tmp, patch('recursa.sandbox.shutil.which', return_value=None), patch('recursa.sandbox.subprocess.Popen') as start:
            target = Path(tmp) / 'MUST_NOT_EXIST'
            result = run_python(f'open({str(target)!r},"w").write("bad")', IMAGE, Path(tmp) / 'run')
            self.assertEqual(result['status'], 'unavailable')
            self.assertIsNone(result['functional_success'])
            self.assertFalse(result['policy_verified'])
            self.assertFalse(target.exists())
            start.assert_not_called()

    def test_rejected_container_policy_is_removed_before_source_dispatch(self):
        calls = []
        def fake(command, **kwargs):
            args = command[3:]
            calls.append(args)
            if args[:1] == ['info']:
                value = '"linux"'
            elif args[:2] == ['image', 'inspect']:
                value = json.dumps([{'Id': IMAGE, 'Os': 'linux', 'Config': {'Env': ['PATH=/usr/local/bin']}}])
            elif args[:2] == ['container', 'create']:
                value = CID
            elif args[:2] == ['container', 'inspect']:
                own_name = next(c[c.index('--name') + 1] for c in calls if c[:2] == ['container', 'create'])
                observed = metadata(own_name)
                observed['HostConfig']['NetworkMode'] = 'host'
                value = json.dumps([observed])
            elif args[:3] == ['container', 'rm', '--force']:
                self.assertEqual(args[-1], CID)
                value = CID
            else:
                self.fail('Unexpected Docker command')
            return subprocess.CompletedProcess(command, 0, value.encode(), b'')
        with tempfile.TemporaryDirectory() as tmp, patch('recursa.sandbox.shutil.which', return_value='docker'), patch('recursa.sandbox.subprocess.run', side_effect=fake), patch('recursa.sandbox.subprocess.Popen') as start:
            result = run_python('raise Exception("must never run")', IMAGE, Path(tmp) / 'run')
            self.assertEqual(result['status'], 'policy-rejected')
            self.assertTrue(result['cleanup_verified'])
            start.assert_not_called()

    def test_preflight_timeout_is_unmeasured_and_does_not_create_container(self):
        with tempfile.TemporaryDirectory() as tmp, patch('recursa.sandbox.shutil.which', return_value='docker'), patch('recursa.sandbox.subprocess.run', side_effect=subprocess.TimeoutExpired('docker', 1)) as command:
            result = run_python('print("fixture")', IMAGE, Path(tmp) / 'run', max_wall_seconds=1)
            self.assertEqual(result['status'], 'unavailable')
            self.assertFalse(result['policy_verified'])
            self.assertEqual(command.call_count, 1)
