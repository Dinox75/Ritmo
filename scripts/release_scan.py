"""Scan a verified release ZIP, without installing or resolving application deps.

Windows runner; invoke with an existing isolated scanner Python. A successful
scan is evidence, never a license, QA or publication approval.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

from release_bundle import verify_bundle, write_json

PINNED_TOOLS = {'pip-audit': '2.10.1', 'cve-bin-tool': '3.4'}


def canonical(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_requirements(path):
    expected = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9][A-Za-z0-9_.+!-]*)', line)
        if not match:
            raise ValueError('Only exact package==version entries are accepted')
        name, version = match.groups()
        name = canonical(name)
        if name in expected:
            raise ValueError('Duplicate redistributed requirement')
        expected[name] = version
    return expected


def assess_pip(data, returncode, expected):
    result = dict(status='error', findings=0, missing=[], skipped=[])
    if returncode not in (0, 1) or not isinstance(data, dict) or not isinstance(data.get('dependencies'), list):
        return result
    seen = {}
    for item in data['dependencies']:
        key = canonical(item['name'])
        seen[key] = item.get('version')
        if item.get('skip_reason'):
            result['skipped'].append(key + '==' + str(item.get('version')))
        if not isinstance(item.get('vulns', []), list):
            return result
        result['findings'] += len(item.get('vulns', []))
    result['missing'] = sorted(f'{name}=={version}' for name, version in expected.items() if seen.get(name) != version)
    result['unexpected'] = sorted(name for name in seen if name not in expected)
    if result['findings']:
        result['status'] = 'findings'
    elif returncode != 0:
        result['status'] = 'error'
    elif result['missing'] or result['skipped'] or result['unexpected']:
        result['status'] = 'incomplete'
    else:
        result['status'] = 'completed'
    return result


def assess_cve(data, returncode):
    result = dict(status='error', findings=0)
    if returncode not in (0, 1) or not isinstance(data, dict):
        return result
    try:
        if data['metadata']['tool']['version'] != PINNED_TOOLS['cve-bin-tool']:
            return result
        database = data['database_info']
        if not database.get('last_updated') or database.get('total_entries', {}).get('NVD', 0) <= 0:
            return dict(result, status='incomplete', reason='Missing populated NVD snapshot metadata')
        entries = [entry for report in data['vulnerabilities']['report'] for entry in report['entries']]
        result['findings'] = len(entries)
        result['database_info'] = database
        result['status'] = 'findings' if entries else ('completed' if returncode == 0 else 'error')
    except (KeyError, TypeError):
        result['status'] = 'incomplete'
    return result


def run_command(args, env, prefix, timeout):
    """Keep exact stdout/stderr and a return code, including missing tools/timeouts."""
    result = dict(returncode=None, timed_out=False)
    with Path(str(prefix) + '.stdout.txt').open('wb') as stdout, Path(str(prefix) + '.stderr.txt').open('wb') as stderr:
        try:
            completed = subprocess.run(args, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, timeout=timeout, check=False)
            result['returncode'] = completed.returncode
        except subprocess.TimeoutExpired:
            result.update(timed_out=True, error='Scanner timeout')
        except OSError as error:
            result['error'] = type(error).__name__
    return result


def load_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, ValueError):
        return None


def diagnostic_failures(path):
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    pattern = r'\b(?:ERROR|CRITICAL)\b|Traceback|(?:failed|cannot|could not)\s+(?:to\s+)?extract|unsupported archive|7z.*not found'
    return [line for line in text.splitlines() if re.search(pattern, line, re.IGNORECASE)]


def scan_bundle(assets, out, commit, run_id, tools_python, timeout=1800, database=None):
    assets, out, tools_python = assets.resolve(), out.resolve(), tools_python.resolve()
    # Validate BEFORE making output or extracting/launching any scanner.
    facts = verify_bundle(assets, commit, run_id)
    sbom = load_json(assets / 'sbom.json')
    if sbom is None:
        raise ValueError('Package inventory required')
    expected = read_requirements(assets / 'redistributed-requirements.txt')
    evidenced = {canonical(item['name']): item['version'] for item in sbom['redistributed_components']}
    if expected != evidenced:
        raise ValueError('Scan requirements differ from evidenced redistributed inventory')
    out.mkdir(parents=True, exist_ok=False)
    extracted = out / 'extracted'
    extracted.mkdir()
    with zipfile.ZipFile(assets / facts['archive']) as archive:
        # verify_bundle already checked safe paths, exact membership and every hash.
        archive.extractall(extracted)
    report = dict(schema_version=1, source_commit=commit, build_run_id=str(run_id), archive=facts['archive'], archive_sha256=facts['archive_sha256'],
                  started_utc=datetime.now(timezone.utc).isoformat(), release_approved=False, checks={},
                  coverage=dict(python_requirements=expected, unmapped_native=sbom['unresolved_native'],
                                native_without_cpe=[item['name'] for item in sbom.get('native_components', []) if not item.get('cpe')],
                                native_unknown_version=[item['name'] for item in sbom.get('native_components', []) if item['version'] == 'NOASSERTION'],
                                build_environment_only_or_unmapped=sbom.get('build_environment_only_or_unmapped', [])),
                  limitations=['CVE-bin-tool 3.4 scans finite binary patterns and supplied CSV identities; it has no Windows PE language scanner.',
                               'Zero reported CVEs does not establish complete vulnerability coverage. Static inner libraries and unmatched identities need evidence review.',
                               'No license, native-window, recovery or publication approval is inferred from this scan.'])
    profile = out / 'scanner-profile'
    (profile / '.cache/cve-bin-tool').mkdir(parents=True)
    temporary = out / 'tmp'
    temporary.mkdir()
    env = os.environ.copy()
    # Python 3.4 tool hardcodes Path("~") on Windows. Give ONLY child scanners
    # their own profile; never read/update the user's vulnerability/pip cache.
    env.update(USERPROFILE=str(profile), LOCALAPPDATA=str(profile / 'Local'), APPDATA=str(profile / 'Roaming'), TEMP=str(temporary), TMP=str(temporary))
    for key in ('PYTHONPATH', 'PYTHONHOME', 'NVD_API_KEY', 'PIP_INDEX_URL', 'PIP_EXTRA_INDEX_URL', 'PIP_CONFIG_FILE', 'NO_EXIT_CVE_NUM'):
        env.pop(key, None)
    metadata_code = "import importlib.metadata as m,json,platform;print(json.dumps({'pip-audit':m.version('pip-audit'),'cve-bin-tool':m.version('cve-bin-tool'),'python':platform.python_version(),'dependencies':sorted((d.metadata['Name'],d.version) for d in m.distributions())}))"
    metadata = run_command([str(tools_python), '-c', metadata_code], env, out / 'tool-versions', 60)
    versions = load_json(out / 'tool-versions.stdout.txt')
    report['tools'] = versions
    if metadata['returncode'] != 0 or not isinstance(versions, dict) or any(versions.get(name) != version for name, version in PINNED_TOOLS.items()):
        report.update(result='scan_error', error='Pinned preinstalled scanner versions required', exit_code=2)
        write_json(out / 'scan-report.json', report)
        return report
    if os.name != 'nt':
        report.update(result='scan_error', error='CVE-bin-tool 3.4 isolated-profile wrapper currently requires Windows', exit_code=2)
        write_json(out / 'scan-report.json', report)
        return report
    if expected:
        pip_output = out / 'pip-audit.json'
        pip_args = [str(tools_python), '-m', 'pip_audit', '--requirement', str(assets / 'redistributed-requirements.txt'), '--no-deps', '--disable-pip', '--strict', '--vulnerability-service', 'pypi', '--format', 'json', '--output', str(pip_output), '--cache-dir', str(out / 'pypi-cache'), '--progress-spinner', 'off']
        execution = run_command(pip_args, env, out / 'pip-audit', timeout)
        report['checks']['python'] = dict(assess_pip(load_json(pip_output), execution['returncode'], expected), execution=execution)
    else:
        report['checks']['python'] = dict(status='not_applicable', findings=0, reason='No evidenced redistributed Python distributions')
    cache = profile / '.cache/cve-bin-tool'
    snapshot = cache / 'cve.db'
    if database:
        shutil.copyfile(database, snapshot)
        report['supplied_database_sha256'] = file_sha(snapshot)
    common = [str(tools_python), '-m', 'cve_bin_tool.cli', '--nvd-api-key', 'no', '--disable-version-check', '--format', 'json2']
    for name, inputs in (('native-binaries', [str(extracted / 'Ritmo')]), ('native-identities', ['--input-file', str(assets / 'native-components.csv')])):
        output = out / (name + '.json')
        update = ['--update', 'never', '--offline'] if database or name == 'native-identities' else ['--update', 'latest']
        args = common + update + ['--output-file', str(output), '--append', str(out / (name + '-intermediate.json'))] + inputs
        execution = run_command(args, env, out / name, timeout)
        report['checks'][name] = dict(assess_cve(load_json(output), execution['returncode']), execution=execution)
        diagnostics = diagnostic_failures(out / (name + '.stderr.txt'))
        if diagnostics:
            report['checks'][name]['diagnostic_failures'] = diagnostics
            if report['checks'][name]['status'] == 'completed':
                report['checks'][name]['status'] = 'incomplete'
        intermediate = load_json(out / (name + '-intermediate.json'))
        if isinstance(intermediate, dict):
            report['checks'][name]['detection_summary'] = intermediate.get('metadata')
    if snapshot.is_file():
        report['cve_database'] = dict(sha256=file_sha(snapshot), size=snapshot.stat().st_size, observed_mtime_utc=datetime.fromtimestamp(snapshot.stat().st_mtime, timezone.utc).isoformat(), file='scanner-profile/.cache/cve-bin-tool/cve.db')
    else:
        report['checks']['database-snapshot'] = dict(status='error', findings=0, reason='Scanner database missing; snapshot cannot be reproduced')
    checks = list(report['checks'].values())
    if any(item['status'] in ('error', 'incomplete') for item in checks):
        report.update(result='scan_error', exit_code=2)
    elif any(item.get('findings', 0) for item in checks):
        report.update(result='findings_require_review', exit_code=1)
    elif any(report['coverage'][key] for key in ('unmapped_native', 'native_without_cpe', 'native_unknown_version')):
        report.update(result='coverage_review_required', exit_code=3)
    else:
        report.update(result='completed_no_reported_findings', exit_code=0)
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    write_json(out / 'scan-report.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--tools-python', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=1800, help='Seconds per scanner; timeouts remain errors')
    parser.add_argument('--database', type=Path, help='Replay an explicitly supplied CVE3.4 database snapshot offline')
    args = parser.parse_args()
    result = scan_bundle(args.assets, args.out, args.commit, args.run_id, args.tools_python, args.timeout, args.database)
    print(json.dumps({key: result[key] for key in ('result', 'exit_code', 'archive_sha256', 'release_approved')}))
    sys.exit(result['exit_code'])
