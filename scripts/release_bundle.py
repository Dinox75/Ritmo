"""Build and verify an immutable, fully inventoried Windows distribution (stdlib only)."""
import argparse
import ast
import csv
import hashlib
import importlib.metadata
import json
import os
import re
import zipfile
from urllib.parse import quote
from pathlib import Path, PurePosixPath

GENERATED_EVIDENCE = {'_internal/release/source-manifest.json',
                      '_internal/release/THIRD-PARTY-NOTICES.txt',
                      '_internal/release/VC-RUNTIME-TERMS.txt'}


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


def transformed_bootloader_inputs(package, toc_paths):
    """Trace a generated EXE through trusted EXE TOC, not a false byte match."""
    sources = {}
    target = package / 'Ritmo.exe'
    if not target.is_file():
        return sources
    target_digest = sha(target.read_bytes())
    for path in toc_paths or []:
        if Path(path).name != 'EXE-00.toc':
            continue
        value = ast.literal_eval(Path(path).read_text(encoding='utf-8-sig'))
        if not isinstance(value, tuple) or not value or not isinstance(value[0], str):
            continue
        output = Path(value[0])
        if output.name.casefold() != 'ritmo.exe' or not output.is_file() or sha(output.read_bytes()) != target_digest:
            continue
        def visit(item):
            if isinstance(item, (tuple, list)):
                if len(item) == 3 and all(isinstance(v, str) for v in item):
                    name, source, kind = item
                    if kind == 'EXECUTABLE' and name.casefold() in ('runw.exe', 'run.exe') and Path(source).is_file():
                        sources[str(Path(source).resolve()).casefold()] = dict(name=name, sha256=sha(Path(source).read_bytes()), output='Ritmo.exe', output_sha256=target_digest,
                            basis='Trusted PyInstaller EXE TOC with byte-identical build output; bootloader is transformed, not byte-identical to final EXE')
                for child in item:
                    visit(child)
        visit(value)
    return sources


def inventory(package, distributions, analysis_toc=None, native_catalog=None):
    module_sources = frozen_module_sources(analysis_toc)
    bootloader_sources = transformed_bootloader_inputs(package, analysis_toc)
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
        embedded_native_inputs = []
        for item in dist.files or []:
            # RECORD evidence: match bytes AND suffix; never infer redistribution from pip freeze alone.
            source = Path(dist.locate_file(item))
            frozen_modules.update(module_sources.get(str(source.resolve()).casefold(), set()))
            embedded = bootloader_sources.get(str(source.resolve()).casefold())
            if embedded and re.sub(r'[-_.]+', '-', dist.metadata['Name']).lower() == 'pyinstaller' and sha(source.read_bytes()) == embedded['sha256']:
                embedded_native_inputs.append(embedded)
            if not source.is_file():
                continue
            suffix = str(item).replace('\\', '/').casefold()
            # PyInstaller relocates pywin32 system DLLs and win32 extensions.
            # Basename matching is permitted only for these documented layouts,
            # and ownership still requires exact SHA-256 equality.
            relocated = suffix.startswith(('pywin32_system32/', 'win32/', 'pythonwin/'))
            candidates = [f for f in files if f['path'].removeprefix('_internal/').casefold().endswith(suffix)
                          or (relocated and Path(f['path']).name.casefold() == Path(suffix).name.casefold())]
            if candidates:
                digest = sha(source.read_bytes())
                matches.extend(f['path'] for f in candidates if f['sha256'] == digest)
        record = dict(name=dist.metadata['Name'], version=dist.version)
        if not matches and not frozen_modules and not embedded_native_inputs:
            build_only.append(record)
            continue
        owned.update(matches)
        owned.update(item['output'] for item in embedded_native_inputs)
        license_texts = []
        for item in dist.files or []:
            if any(token in Path(str(item)).name.lower() for token in ('license', 'copying', 'notice')):
                source = Path(dist.locate_file(item))
                if source.is_file():
                    license_texts.append(dict(name=Path(str(item)).name, text=source.read_text(encoding='utf-8', errors='replace')))
        record.update(files=sorted(set(matches)), frozen_modules=sorted(frozen_modules), embedded_native_inputs=embedded_native_inputs, license=dist.metadata.get('License-Expression') or dist.metadata.get('License') or 'NOASSERTION', notices=license_texts)
        components.append(record)
    native = sorted(f['path'] for f in files if f['path'].lower().endswith(('.exe', '.dll', '.pyd')))
    native_components, native_license_issues = [], []
    builtin = Path(__file__).with_name('release_vendor_catalog.json')
    catalogs = ([builtin] if builtin.is_file() else []) + list(native_catalog or [])
    for catalog_path in dict.fromkeys(map(Path, catalogs)):
        catalog = json.loads(Path(catalog_path).read_text(encoding='utf-8-sig'))
        if catalog.get('schema_version') != 1:
            raise ValueError('Unsupported native catalog schema')
        for component in catalog['components']:
            matches = sorted(f['path'] for f in files if f['path'] in native and f['sha256'] in component['file_hashes'])
            if not matches:
                continue
            record = {key: component[key] for key in ('name', 'version', 'license', 'notices', 'provenance')}
            record['provenance'] = dict(record['provenance'], catalog_sha256=sha(Path(catalog_path).read_bytes()))
            record.update(files=matches)
            for key in ('purl', 'cpe'):
                if component.get(key):
                    record[key] = component[key]
            native_components.append(record)
            owned.update(matches)
            if record['license'] == 'NOASSERTION' or not record['notices']:
                native_license_issues.append(dict(component=record['name'], files=matches, reason='License or complete notice evidence missing'))
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
    return dict(native_components=native_components, native_license_issues=native_license_issues, native_metadata=native_metadata, schema_version=1, format='Ritmo package inventory (not SPDX/CycloneDX)', files=files, redistributed_components=components, build_environment_only_or_unmapped=build_only, native_files=native, unresolved_native=[p for p in native if p not in owned], license_review='required', limitations=['Frozen Python provenance uses trusted PyInstaller TOC source paths mapped to distribution RECORD; only module names are emitted. Missing provenance/match does not prove absence from bundle.', 'Native dependencies and vendor license terms require review; metadata and exact origin matches are evidence, not approval.'])


def create_bundle(package, out, version, commit, run_id, distributions=None, analysis_toc=None, native_catalog=None):
    if not re.fullmatch(r'v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)-preview\.[1-9]\d*', version):
        raise ValueError('Invalid preview version')
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Expected full source SHA')
    distributions = list(importlib.metadata.distributions() if distributions is None else distributions)
    sbom = inventory(package, distributions, analysis_toc, native_catalog)
    if not (package / 'Ritmo.exe').is_file() or not any(f['path'].startswith('_internal/') for f in sbom['files']):
        raise ValueError('Incomplete EXE + _internal package')
    out.mkdir(parents=True, exist_ok=False)
    archive = f'Ritmo-{version}-windows-x64.zip'
    # The embedded source manifest covers the original payload; it deliberately
    # contains no ZIP hash, avoiding self-referential hash recursion.
    source_manifest = dict(schema_version=1, version=version, source_commit=commit,
                           build_run_id=str(run_id), payload_files=list(sbom['files']))
    generated = {}
    notices = ['THIRD PARTY NOTICES — REVIEW REQUIRED', 'This inventory does not grant redistribution rights.', *sbom['limitations']]
    for component in sbom['redistributed_components'] + sbom['native_components']:
        notices.append(f"\n{component['name']} {component['version']}\nDeclared license: {component['license']}")
        notices.extend(n['name'] + '\n' + n['text'] for n in component['notices'])
    notices.append('\nUNRESOLVED NATIVE ORIGINS:\n' + '\n'.join(sbom['unresolved_native']))
    notices.append('\nUNRESOLVED NATIVE LICENSE EVIDENCE:\n' + json.dumps(sbom['native_license_issues'], ensure_ascii=False))
    generated['_internal/release/THIRD-PARTY-NOTICES.txt'] = ('\n'.join(notices) + '\n').encode('utf-8')
    generated['_internal/release/source-manifest.json'] = (json.dumps(source_manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    resources = Path(__file__).with_name('release_licenses')
    crt_notice = (resources / 'python-windows-crtlicense.txt').read_bytes()
    if sha(crt_notice) != '3c71b3ae243121f6f227374cd1ef7c59ed07b1969b330d0e947f91a3a1b3fd73':
        raise ValueError('Pinned PSF Microsoft CRT notice differs')
    generated['_internal/release/VC-RUNTIME-TERMS.txt'] = (resources / 'ritmo-microsoft-terms.txt').read_bytes() + b'\n' + crt_notice
    for name, data in generated.items():
        if any(item['path'] == name for item in sbom['files']):
            raise ValueError('Generated evidence path collides with package payload')
        sbom['files'].append(dict(path=name, sha256=sha(data), size=len(data)))
    with zipfile.ZipFile(out / archive, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
        for item in source_manifest['payload_files']:
            zipped.write(package / item['path'], 'Ritmo/' + item['path'])
        for name, data in generated.items():
            zipped.writestr('Ritmo/' + name, data)
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
    for component in sbom['native_components']:
        library = dict(type='library', name=component['name'], version=component['version'],
                       properties=[dict(name='ritmo:provenance', value=json.dumps(component['provenance']))])
        for key in ('purl', 'cpe'):
            if component.get(key):
                library[key] = component[key]
        if component['license'] != 'NOASSERTION':
            library['licenses'] = [dict(license=dict(name=component['license']))]
        standard['components'].append(library)
    write_json(out / 'bom.cdx.json', standard)
    (out / 'redistributed-requirements.txt').write_text(''.join(
        f"{component['name']}=={component['version']}\n" for component in sbom['redistributed_components']), encoding='utf-8')
    with (out / 'native-components.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['vendor', 'product', 'version'])
        for component in sbom['native_components']:
            fields = component.get('cpe', '').split(':')
            if len(fields) >= 6 and fields[:2] == ['cpe', '2.3']:
                writer.writerow(fields[3:6])
    (out / 'THIRD-PARTY-NOTICES.txt').write_bytes(generated['_internal/release/THIRD-PARTY-NOTICES.txt'])
    write_json(out / 'build-dependencies.json', [dict(name=d.metadata['Name'], version=d.version) for d in (importlib.metadata.distributions() if distributions is None else distributions)])
    facts = dict(schema_version=1, version=version, source_commit=commit, build_run_id=str(run_id), archive=archive, archive_sha256=sha((out / archive).read_bytes()), executable_sha256=sha((package / 'Ritmo.exe').read_bytes()), files=sbom['files'])
    facts['evidence_sha256'] = {p.name: sha(p.read_bytes()) for p in out.iterdir() if p.name != archive}
    write_json(out / 'build-info.json', facts)
    (out / 'SHA256SUMS.txt').write_text(''.join(f"{sha(p.read_bytes())}  {p.name}\n" for p in sorted(out.iterdir()) if p.is_file()), encoding='ascii')
    verify_bundle(out, commit, str(run_id))
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
        embedded_name = 'Ritmo/_internal/release/source-manifest.json'
        if embedded_name in names:
            embedded = json.loads(zipped.read(embedded_name))
            if any(embedded.get(key) != facts[key] for key in ('source_commit', 'build_run_id', 'version')):
                raise ValueError('Embedded source manifest differs from external manifest')
            payload = {item['path']: item for item in facts['files'] if item['path'] not in GENERATED_EVIDENCE}
            if {item['path']: item for item in embedded['payload_files']} != payload:
                raise ValueError('Embedded source payload manifest differs')
            if zipped.read('Ritmo/_internal/release/THIRD-PARTY-NOTICES.txt') != (out / 'THIRD-PARTY-NOTICES.txt').read_bytes():
                raise ValueError('Embedded notices differ from external notices')
    return facts


def verify_approval(approval, facts, native=None):
    for field in ('source_commit', 'archive_sha256', 'build_run_id'):
        if approval.get(field) != facts[field]:
            raise ValueError('Approval mismatch: ' + field)
    for field, expected in dict(clean_windows=True, result='passed', license_review='approved', vulnerability_review='approved').items():
        if approval.get(field) != expected:
            raise ValueError('Approval missing: ' + field)
    if not str(approval.get('reviewed_by', '')).strip():
        raise ValueError('Reviewer required')
    if not isinstance(native, dict):
        raise ValueError('Real native-window evidence required')
    for field in ('source_commit', 'archive_sha256', 'build_run_id', 'executable_sha256'):
        if native.get(field) != facts[field]:
            raise ValueError('Native evidence mismatch: ' + field)
    if native.get('method') != 'native-uia' or native.get('result') != 'passed' or native.get('forced_cleanup'):
        raise ValueError('Native acceptance did not pass naturally')
    for field in ('native_write_verified', 'native_cancel_preserved', 'natural_shutdown', 'port_released'):
        if native.get(field) is not True:
            raise ValueError('Native action missing: ' + field)
    for stage in ('executable', 'native_window', 'native_authorization', 'qa_native_connection'):
        if native.get('stages', {}).get(stage) is not True:
            raise ValueError('Native stage missing: ' + stage)
    for field in ('window_station_visible', 'input_desktop_open'):
        if native.get('environment', {}).get(field) is not True:
            raise ValueError('Graphical Windows session required: ' + field)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['pack', 'verify'])
    parser.add_argument('--package', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--version')
    parser.add_argument('--commit', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--approval', type=Path)
    parser.add_argument('--native-evidence', type=Path)
    parser.add_argument('--analysis-toc', type=Path, action='append', help='Trusted PyInstaller Analysis/PYZ TOC; repeatable')
    parser.add_argument('--native-catalog', type=Path, action='append', help='Exact hash native origin/license catalog; repeatable')
    args = parser.parse_args()
    facts = create_bundle(args.package, args.out, args.version, args.commit, args.run_id, analysis_toc=args.analysis_toc, native_catalog=args.native_catalog) if args.mode == 'pack' else verify_bundle(args.out, args.commit, args.run_id)
    if args.approval:
        verify_approval(json.loads(args.approval.read_text(encoding='utf-8-sig')), facts,
                        json.loads(args.native_evidence.read_text(encoding='utf-8-sig')) if args.native_evidence else None)
    print(json.dumps({k: facts[k] for k in ('source_commit', 'archive_sha256', 'executable_sha256')}))
