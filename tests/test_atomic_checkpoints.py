import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recursa.experiments import atomic_json


class AtomicCheckpointTests(unittest.TestCase):
    def test_transient_replace_lock_retries_without_partial_json(self):
        replace = os.replace
        count = 0
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'checkpoint.json'
            atomic_json(target, {'status': 'old'})
            def locked(source, destination):
                nonlocal count
                count += 1
                self.assertEqual(json.loads(target.read_text())['status'], 'old')
                if count < 3:
                    raise PermissionError('transient lock')
                return replace(source, destination)
            with patch('recursa.experiments.os.replace', side_effect=locked), patch('recursa.experiments.time.sleep'):
                atomic_json(target, {'status': 'complete'})
            self.assertEqual(count, 3)
            self.assertEqual(json.loads(target.read_text())['status'], 'complete')
            self.assertEqual(list(Path(tmp).glob('*.tmp')), [])

    def test_permanent_lock_remains_an_error_and_preserves_previous_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'checkpoint.json'
            atomic_json(target, {'status': 'old'})
            with patch('recursa.experiments.os.replace', side_effect=PermissionError('locked')) as replace, patch('recursa.experiments.time.sleep'):
                with self.assertRaises(PermissionError):
                    atomic_json(target, {'status': 'new'})
                self.assertEqual(replace.call_count, 6)
            self.assertEqual(json.loads(target.read_text())['status'], 'old')
            self.assertEqual(list(Path(tmp).glob('*.tmp')), [])
