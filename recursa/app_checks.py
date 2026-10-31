"""Fixed source lint rules and declarative browser unit checks; no host evaluation."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import os

from recursa.artifacts import validate_artifacts
from recursa.browser_checks import check_application
from recursa.build import build_application
from recursa.budget import Deadline

ROOT = Path(__file__).resolve().parents[1]


def lint_sources(artifacts, compiler_directory=None, *, max_seconds=15):
    if type(max_seconds) not in (int, float) or not 0 < max_seconds <= 15:
        raise ValueError('Lint timeout must be positive and at most 15 seconds')
    ids = {r for a in artifacts for r in a.get('requirements', [])}
    artifacts = validate_artifacts({'artifacts': artifacts}, ids)
    compiler = Path(compiler_directory or ROOT / 'tooling/typecheck/node_modules/typescript')
    empty = {'status': 'unavailable', 'checks': [], 'lint_success': None}
    node = shutil.which('node')
    try:
        if not node or json.loads((compiler / 'package.json').read_text())['version'] != '5.9.3':
            return empty
    except (OSError, ValueError, KeyError):
        return empty
    environment = dict(os.environ)
    environment.pop('NODE_OPTIONS', None)
    environment.pop('NODE_PATH', None)
    try:
        result = subprocess.run([node, str(ROOT / 'scripts/lint_sources.mjs')],
            input=json.dumps({'artifacts': artifacts, 'compiler': str(compiler.resolve())}),
            capture_output=True, text=True, timeout=max_seconds, env=environment)
        if result.returncode:
            return empty
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {'status': 'timeout', 'lint_success': False, 'checks': [
            {'path': a['path'], 'kind': 'lint', 'status': 'timeout'} for a in artifacts if Path(a['path']).suffix in {'.ts', '.tsx', '.js', '.jsx'}]}
    except (OSError, ValueError):
        return empty


def validate_unit_cases(cases, artifacts, ids):
    paths = {a['path'] for a in artifacts}
    if not isinstance(cases, list) or not 1 <= len(cases) <= 32 or len(json.dumps(cases, allow_nan=False)) > 100000:
        raise ValueError('Provide 1–32 bounded JSON unit cases')
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {'id', 'module', 'export', 'arguments', 'expected', 'requirements'}:
            raise ValueError('Unit cases require declarative fields only')
        if not isinstance(case['id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', case['id']) or case['id'] in seen:
            raise ValueError('Unit IDs must be safe and unique')
        seen.add(case['id'])
        if case['module'] not in paths or Path(case['module']).suffix not in {'.ts', '.js'}:
            raise ValueError('Unit module must be an existing validated source')
        if not isinstance(case['export'], str) or not re.fullmatch(r'[A-Za-z_$][\w$]{0,100}', case['export']):
            raise ValueError('Unit export must be a named function')
        if not isinstance(case['arguments'], list) or len(case['arguments']) > 16 or not isinstance(case['requirements'], list) or not case['requirements'] or any(r not in ids for r in case['requirements']):
            raise ValueError('Unit arguments/references must be bounded and known')
    return cases


def check_units(artifacts, cases, output_dir, *, frontend_tools=None, browser_tools=None, deadline=None):
    deadline = deadline or Deadline(75)
    ids = {r for a in artifacts for r in a['requirements']}
    artifacts = validate_artifacts({'artifacts': artifacts}, ids)
    validate_unit_cases(cases, artifacts, ids)
    # Use a disjoint directory so application paths cannot collide with the
    # trusted harness. Imports resolve only to validated source artifacts.
    prefix = 'recursa-unit-harness'
    while any(a['path'].split('/')[0] == prefix for a in artifacts):
        prefix += '-x'
    modules = list(dict.fromkeys(c['module'] for c in cases))
    source = '\n'.join(f'import * as m{i} from {json.dumps("../" + module)};' for i, module in enumerate(modules))
    source += '\nconst modules: Record<string, any> = {' + ','.join(f'{json.dumps(module)}:m{i}' for i, module in enumerate(modules)) + '};\n'
    source += '''const canonical = (value: any): any => Array.isArray(value) ? value.map(canonical) : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(k => [k, canonical(value[k])])) : value;
'''
    source += 'const cases = ' + json.dumps(cases, allow_nan=False) + ';\n'
    source += '''for (const item of cases) {
      const row = document.createElement('p'); row.dataset.testid = item.id;
      try {
        const actual = await modules[item.module][item.export](...item.arguments);
        row.textContent = JSON.stringify(canonical(actual)) === JSON.stringify(canonical(item.expected)) ? 'PASS' : 'FAIL';
      } catch { row.textContent = 'FAIL'; }
      document.body.append(row);
    }
'''
    refs = sorted(ids)
    inputs = [a for a in artifacts if a['path'] != 'index.html'] + [
        {'path': 'index.html', 'content': f'<!doctype html><html lang="en"><head><title>Unit checks</title></head><body><script type="module" src="{prefix}/main.ts"></script></body></html>', 'requirements': refs},
        {'path': prefix + '/main.ts', 'content': source, 'requirements': refs}]
    build = build_application(inputs, output_dir, max_seconds=deadline.remaining(30), **({'tool_directory': frontend_tools} if frontend_tools is not None else {}))
    if build['build_success'] is not True:
        return {'status': build['status'], 'checks': build['checks'], 'unit_test_pass_rate': None, 'build': build}
    scenarios = [{'id': c['id'], 'source_path': c['module'], 'requirements': c['requirements'],
                  'steps': [{'action': 'expect_text', 'target': {'test_id': c['id']}, 'value': 'PASS'}]} for c in cases]
    # A fresh browser context per case also reruns the entire module fixture;
    # declared cases must be pure and independent of order/shared state.
    report = check_application(build['dist_path'], scenarios, tool_directory=browser_tools, max_seconds=deadline.remaining(45, minimum=1))
    for check in report['checks']:
        check['kind'] = 'unit'
    return {'status': report['status'], 'checks': report['checks'],
            'unit_test_pass_rate': report.get('e2e_pass_rate'), 'build': build,
            'scope': 'Independently authored JSON cases against named exports, executed only in isolated Chromium'}
