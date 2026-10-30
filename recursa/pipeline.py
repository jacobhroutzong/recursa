"""Offline application verification and bounded repair, independent of inference."""
from pathlib import Path

from recursa.artifacts import save_artifacts, validate_artifacts
from recursa.app_checks import lint_sources, check_units, validate_unit_cases
from recursa.browser_checks import check_application, validate_scenarios
from recursa.build import build_application
from recursa.experiments import atomic_json
from recursa.repair import repair_artifacts
from recursa.verification import check_sources, declared_coverage


def verify_application(spec, artifacts, output_dir, *, scenarios=None,
                       typescript_directory=None, frontend_tools=None, browser_tools=None,
                       repair_callback=None, max_repairs=0, unit_cases=None):
    """Run bounded stages; functional success describes only declared scenarios.

    Scenarios must be independently reviewed. Callers supplying inference through
    repair_callback must enforce a shared provider budget. This function makes no
    provider calls. Stages have individual hard deadlines; at most ten repairs.
    """
    if type(max_repairs) is not int or not 0 <= max_repairs <= 10:
        raise ValueError("Repair count must be an integer from 0 to 10")
    if max_repairs and not callable(repair_callback):
        raise ValueError("Requested repairs require a budgeted callback")
    ids = {r['id'] for r in spec['requirements']}
    artifacts = validate_artifacts({'artifacts': artifacts}, ids)
    if unit_cases is not None:
        validate_unit_cases(unit_cases, artifacts, ids)
    if scenarios is not None:
        validate_scenarios(scenarios)
        paths = {a['path'] for a in artifacts}
        if any(set(s['requirements']) - ids or s.get('source_path', 'index.html') not in paths for s in scenarios):
            raise ValueError("Scenarios must reference known requirements and artifact paths")
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    attempts = []

    def verify(candidate):
        stage = directory / f"verification-{len(attempts):03}"
        stage.mkdir()
        static = check_sources(candidate, typescript_directory=typescript_directory,
                               scratch_directory=stage / 'private/typecheck')
        lint = lint_sources(candidate, typescript_directory)
        build = build_application(candidate, stage, **({'tool_directory': frontend_tools} if frontend_tools is not None else {}))
        browser = {'status': 'not-run', 'checks': [], 'functional_success': None, 'e2e_pass_rate': None}
        if build['build_success'] is True and scenarios is not None:
            browser = check_application(build['dist_path'], scenarios, tool_directory=browser_tools)
        unit = {'status': 'not-run', 'checks': [], 'unit_test_pass_rate': None}
        if unit_cases is not None:
            unit = check_units(candidate, unit_cases, stage / 'units', frontend_tools=frontend_tools, browser_tools=browser_tools)
        checks = static['checks'] + lint['checks'] + build['checks'] + browser['checks'] + unit['checks']
        failed = any(c['status'] in {'failed', 'timeout'} for c in checks)
        complete = (build['build_success'] is True and browser['functional_success'] is True
                    and static.get('typecheck_success') is not False and lint['lint_success'] is True
                    and (unit_cases is None or unit['unit_test_pass_rate'] == 1))
        audits = [audit for c in browser['checks'] for audit in c.get('accessibility_audits', [])]
        requested_audits = sum(step['action'] == 'audit_accessibility' for s in (scenarios or []) for step in s['steps'])
        accessibility = (False if any(not a['passed'] for a in audits) else
                         True if requested_audits and len(audits) == requested_audits else None)
        report = {'status': 'failed' if failed else 'passed' if complete else 'incomplete',
                  'checks': checks, 'build_success': build['build_success'],
                  'functional_success': browser['functional_success'],
                  'typecheck_success': static.get('typecheck_success'),
                  'lint_success': lint['lint_success'],
                  'unit_test_pass_rate': unit['unit_test_pass_rate'],
                  'accessibility_success': accessibility,
                  'end_to_end_pass_rate': browser.get('e2e_pass_rate'),
                  'dist_path': build.get('dist_path'),
                  'scope': 'Declared offline acceptance scenarios only; not evidence of model synthesis',
                  'stages': {'source': static, 'lint': lint, 'build': build, 'browser': browser, 'unit': unit}}
        attempts.append(report)
        atomic_json(stage / 'verification.json', report)
        return report

    initial = verify(artifacts)
    repair = repair_artifacts(artifacts, ids, initial, repair_callback, verify,
                              max_attempts=max_repairs, output_dir=directory / 'repair')
    final = repair['verification']
    save_artifacts(directory / 'artifacts', repair['artifacts'])
    result = {'status': final['status'], 'artifacts': repair['artifacts'],
              'verification': final, 'coverage': declared_coverage(spec, repair['artifacts']),
              'repair_status': repair['status'], 'repair_attempts': len(repair['attempts']),
              'verification_passes': len(attempts)}
    atomic_json(directory / 'application-report.json', result)
    return result
