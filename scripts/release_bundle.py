"""Build and verify an immutable, fully inventoried Windows distribution (stdlib only)."""
import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
import re
import zipfile
from urllib.parse import quote
from pathlib import Path, PurePosixPath


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def check_name(name):
    p = PurePosixPath(name)
    low = name.lower()
    forbidden = {'.git', '.env', 'preferences.json', 'prefs.json', 'source_checkout.txt', 'credentials', 'credentials.json'}
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or any(part.lower() in forbidden for part in p.parts):
        raise ValueError('Unsafe/private package path: ' + name)
    if low.endswith(('.db', '.sqlite', '.sqlite3', '.gguf', '.safetensors', '.log', '.pem', '.key', '.env')):
        raise ValueError('Private/model file: ' + name)
    if not (name == 'Ritmo/Ritmo.exe' or name.startswith('Ritmo/_internal/')):
        raise ValueError('Unexpected package path: ' + name)


def frozen_module_sources(toc_paths):
    """Read trusted PyInstaller build provenance without executing it or exposing paths."""
    sources = {}
    def visit(value):
        if isinstance(value, (tuple, list)):
            if len(value) == 3 and all(isinstance(item, str) for item in value):
                module, source, kind = value
                if kind.startswith('PYMODULE') or kind == 'PYSOURCE':
                    sources.setdefault(str(Path(source).resolve()).casefold(), set()).add(module)
            for item in value:
                visit(item)
    for path in toc_paths or []:
        visit(ast.literal_eval(Path(path).read_text(encoding='utf-8-sig')))
    return sources


def inventory(package, distributions, analysis_toc=None):
    module_sources = frozen_module_sources(analysis_toc)
    files = []
    for path in sorted(package.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlinks are not allowed')
        if path.is_file():
            name = path.relative_to(package).as_posix()
            check_name('Ritmo/' + name)
            payload = path.read_bytes()
            roots = [str(Path.cwd()), os.environ.get('USERPROFILE', ''), os.environ.get('GITHUB_WORKSPACE', '')]
            for root in roots:
                if len(root) > 5 and any(root.lower().encode(encoding) in payload.lower() for encoding in ('utf-8', 'utf-16le')):
                    raise ValueError('Private checkout/profile path embedded in: ' + name)
            files.append(dict(path=name, sha256=sha(payload), size=len(payload)))
    components, build_only = [], []
    owned = set()
    for dist in distributions:
        matches = []
        frozen_modules = set()
        for item in dist.files or []:
            # RECORD evidence: match bytes AND suffix; never infer redistribution from pip freeze alone.
            source = Path(dist.locate_file(item))
            frozen_modules.update(module_sources.get(str(source.resolve()).casefold(), set()))
            if not source.is_file():
                continue
            suffix = str(item).replace('\\', '/')
            candidates = [f for f in files if f['path'].removeprefix('_internal/').endswith(suffix)]
            if candidates:
                digest = sha(source.read_bytes())
                matches.extend(f['path'] for f in candidates if f['sha256'] == digest)
        record = dict(name=dist.metadata['Name'], version=dist.version)
        if not matches and not frozen_modules:
            build_only.append(record)
            continue
        owned.update(matches)
        license_texts = []
        for item in dist.files or []:
            if any(token in Path(str(item)).name.lower() for token in ('license', 'copying', 'notice')):
                source = Path(dist.locate_file(item))
                if source.is_file():
                    license_texts.append(dict(name=Path(str(item)).name, text=source.read_text(encoding='utf-8', errors='replace')))
        record.update(files=sorted(set(matches)), frozen_modules=sorted(frozen_modules), license=dist.metadata.get('License-Expression') or dist.metadata.get('License') or 'NOASSERTION', notices=license_texts)
        components.append(record)
    native = sorted(f['path'] for f in files if f['path'].lower().endswith(('.exe', '.dll', '.pyd')))
    native_metadata = []
    for name in native:
        item = dict(path=name, status='unavailable', reason='PE metadata unavailable; manual native review required')
        try:
            import pefile
            with pefile.PE(str(package / name), fast_load=False) as pe:
                version = {}
                for group in getattr(pe, 'FileInfo', []):
                    for entry in group:
                        for table in getattr(entry, 'StringTable', []):
                            for key, value in table.entries.items():
                                label = key.decode('utf-8', errors='replace')
                                if label in ('CompanyName', 'ProductName', 'FileDescription', 'FileVersion', 'ProductVersion', 'LegalCopyright'):
                                    version[label] = value.decode('utf-8', errors='replace')
                item = dict(path=name, status='parsed', machine=pe.FILE_HEADER.Machine, timestamp=pe.FILE_HEADER.TimeDateStamp, version=version)
        except Exception:  # optional parser: missing/invalid PE evidence remains an explicit review gate
            pass
        native_metadata.append(item)
    return dict(native_metadata=native_metadata, schema_version=1, format='Ritmo package inventory (not SPDX/CycloneDX)', files=files, redistributed_components=components, build_environment_only_or_unmapped=build_only, native_files=native, unresolved_native=[p for p in native if p not in owned], license_review='required', limitations=['Frozen Python provenance uses trusted PyInstaller TOC source paths mapped to distribution RECORD; only module names are emitted. Missing provenance/match does not prove absence from bundle.', 'Native dependencies and vendor license terms require manual review; metadata is evidence, not approval.'])


def create_bundle(package, out, version, commit, run_id, distributions=None, analysis_toc=None):
    if not re.fullmatch(r'v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-preview\.[1-9]\d*', version):
        raise ValueError('Invalid preview version')
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Expected full source SHA')
    sbom = inventory(package, importlib.metadata.distributions() if distributions is None else distributions, analysis_toc)
    if not (package / 'Ritmo.exe').is_file() or not any(f['path'].startswith('_internal/') for f in sbom['files']):
        raise ValueError('Incomplete EXE + _internal package')
    out.mkdir(parents=True, exist_ok=False)
    archive = f'Ritmo-{version}-windows-x64.zip'
    with zipfile.ZipFile(out / archive, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
        for item in sbom['files']:
            zipped.write(package / item['path'], 'Ritmo/' + item['path'])
    write_json(out / 'sbom.json', sbom)
    standard = dict(bomFormat='CycloneDX', specVersion='1.6', version=1,
                    components=[dict(type='file', name=f['path'], **{'bom-ref': 'file:' + f['path']}, hashes=[dict(alg='SHA-256', content=f['sha256'])]) for f in sbom['files']])
    for component in sbom['redistributed_components']:
        normalized = re.sub(r'[-_.]+', '-', component['name']).lower()
        purl = f"pkg:pypi/{quote(normalized)}@{quote(component['version'])}"
        library = dict(type='library', name=component['name'], version=component['version'], purl=purl,
                       **{'bom-ref': purl}, properties=[dict(name='ritmo:frozen-modules', value=json.dumps(component['frozen_modules']))])
        if component['license'] != 'NOASSERTION':
            library['licenses'] = [dict(license=dict(name=component['license']))]
        standard['components'].append(library)
    write_json(out / 'bom.cdx.json', standard)
    notices = ['THIRD PARTY NOTICES — REVIEW REQUIRED', 'This inventory does not grant redistribution rights.', *sbom['limitations']]
    for component in sbom['redistributed_components']:
        notices.append(f"\n{component['name']} {component['version']}\nDeclared license: {component['license']}")
        notices.extend(n['name'] + '\n' + n['text'] for n in component['notices'])
    notices.append('\nUNRESOLVED NATIVE LICENSES:\n' + '\n'.join(sbom['unresolved_native']))
    (out / 'THIRD-PARTY-NOTICES.txt').write_text('\n'.join(notices) + '\n', encoding='utf-8')
    write_json(out / 'build-dependencies.json', [dict(name=d.metadata['Name'], version=d.version) for d in (importlib.metadata.distributions() if distributions is None else distributions)])
    facts = dict(schema_version=1, version=version, source_commit=commit, build_run_id=str(run_id), archive=archive, archive_sha256=sha((out / archive).read_bytes()), executable_sha256=sha((package / 'Ritmo.exe').read_bytes()), files=sbom['files'])
    facts['evidence_sha256'] = {p.name: sha(p.read_bytes()) for p in out.iterdir() if p.name != archive}
    write_json(out / 'build-info.json', facts)
    (out / 'SHA256SUMS.txt').write_text(''.join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(out.iterdir()) if p.is_file()), encoding='ascii')
    return facts


def verify_bundle(out, commit, run_id):
    facts = json.loads((out / 'build-info.json').read_text(encoding='utf-8-sig'))
    if facts['source_commit'] != commit or facts['build_run_id'] != str(run_id):
        raise ValueError('Source/run mismatch')
    name = facts['archive']
    if Path(name).name != name or '/' in name or '\\' in name:
        raise ValueError('Unsafe archive name')
    for line in (out / 'SHA256SUMS.txt').read_text().splitlines():
        digest, filename = line.split('  ', 1)
        if Path(filename).name != filename or sha((out / filename).read_bytes()) != digest:
            raise ValueError('Checksum mismatch')
    for filename, digest in facts['evidence_sha256'].items():
        if Path(filename).name != filename or sha((out / filename).read_bytes()) != digest:
            raise ValueError('Evidence checksum mismatch')
    if sha((out / name).read_bytes()) != facts['archive_sha256']:
        raise ValueError('ZIP checksum mismatch')
    with zipfile.ZipFile(out / name) as zipped:
        names = zipped.namelist()
        expected = {'Ritmo/' + f['path']: f for f in facts['files']}
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError('Package file set mismatch')
        if 'Ritmo/Ritmo.exe' not in names or not any(n.startswith('Ritmo/_internal/') for n in names):
            raise ValueError('Incomplete package')
        for filename in names:
            check_name(filename)
            data = zipped.read(filename)
            if sha(data) != expected[filename]['sha256'] or len(data) != expected[filename]['size']:
                raise ValueError('Package file checksum mismatch')
        if sha(zipped.read('Ritmo/Ritmo.exe')) != facts['executable_sha256']:
            raise ValueError('EXE checksum mismatch')
    return facts


def verify_approval(approval, facts):
    for field in ('source_commit', 'archive_sha256', 'build_run_id'):
        if approval.get(field) != facts[field]:
            raise ValueError('Approval mismatch: ' + field)
    for field, expected in dict(clean_windows=True, result='passed', license_review='approved', vulnerability_review='approved').items():
        if approval.get(field) != expected:
            raise ValueError('Approval missing: ' + field)
    if not str(approval.get('reviewed_by', '')).strip():
        raise ValueError('Reviewer required')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['pack', 'verify'])
    parser.add_argument('--package', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--version')
    parser.add_argument('--commit', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--approval', type=Path)
    parser.add_argument('--analysis-toc', type=Path, action='append', help='Trusted PyInstaller Analysis/PYZ TOC; repeatable')
    args = parser.parse_args()
    facts = create_bundle(args.package, args.out, args.version, args.commit, args.run_id, analysis_toc=args.analysis_toc) if args.mode == 'pack' else verify_bundle(args.out, args.commit, args.run_id)
    if args.approval:
        verify_approval(json.loads(args.approval.read_text(encoding='utf-8-sig')), facts)
    print(json.dumps({k: facts[k] for k in ('source_commit', 'archive_sha256', 'executable_sha256')}))
