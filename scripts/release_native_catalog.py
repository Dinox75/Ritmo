"""Bind installed Python native bytes to a verified installer and upstream SBOM.

This does not verify an installer signature itself: the caller must supply the
receipt from its verified installation step. No binaries are executed or installed.
"""
import argparse
import fnmatch
import hashlib
import json
from pathlib import Path

VERSION = '3.14.10'
INSTALLER_URL = 'https://www.python.org/ftp/python/3.14.10/python-3.14.10-amd64.exe'
INSTALLER_SHA256 = '92480239264744fe0386a1bd8275786fefa126e3129e56a68e22b52c73329965'
SBOM_URL = INSTALLER_URL + '.spdx.json'
SBOM_SHA256 = '631d10bf095ea6855a0d20fa0553d2de6f68288fc5b5ca943f1cb74d8dcc0b5c'


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pe_version(path):
    try:
        import pefile
        with pefile.PE(str(path)) as pe:
            for group in getattr(pe, 'FileInfo', []):
                for entry in group:
                    for table in getattr(entry, 'StringTable', []):
                        value = table.entries.get(b'FileVersion')
                        if value:
                            return value.decode('utf-8', errors='replace')
    except Exception:
        pass
    return 'NOASSERTION'


def create_catalog(python_base, vendor_sbom, receipt, rules, resource_root=None):
    if (receipt.get('installer_sha256') != INSTALLER_SHA256
            or receipt.get('signature_status') != 'Valid'
            or 'Python Software Foundation' not in receipt.get('signer_subject', '')
            or receipt.get('source_url') != INSTALLER_URL
            or receipt.get('version') != VERSION):
        raise ValueError('Verified pinned PSF installer receipt required')
    vendor = json.loads(Path(vendor_sbom).read_text(encoding='utf-8-sig'))
    cpython = [p for p in vendor['packages'] if p['name'].lower() == 'cpython' and p.get('versionInfo') == VERSION]
    if len(cpython) != 1 or not any(c['algorithm'] == 'SHA256' and c['checksumValue'] == INSTALLER_SHA256 for c in cpython[0].get('checksums', [])):
        raise ValueError('Vendor SBOM does not bind the pinned Python installer')
    # Inspect only the installer's base root/DLLs; never include site-packages or
    # user directories in Python-base provenance.
    paths = list(Path(python_base).glob('*'))
    if (Path(python_base) / 'DLLs').is_dir():
        paths += list((Path(python_base) / 'DLLs').rglob('*'))
    native = [p for p in paths if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.dll', '.pyd')]
    matched, components = set(), []
    for rule in rules['components']:
        files = [p for p in native if any(fnmatch.fnmatchcase(p.name.casefold(), pattern.casefold()) for pattern in rule['patterns'])]
        if not files:
            continue
        upstream = [p for p in vendor['packages'] if p['name'] == rule.get('vendor_package') and p.get('versionInfo') == rule.get('version')]
        if rule.get('vendor_package') and len(upstream) != 1:
            raise ValueError('Native rule does not match a unique vendor component: ' + rule['name'])
        versions = {pe_version(p) for p in files} if rule.get('version_from') == 'pe' else {rule['version']}
        if len(versions) != 1:
            raise ValueError('Different native PE versions require separate component rules')
        version = next(iter(versions))
        notices = []
        for notice in rule['notices']:
            if resource_root is None:
                raise ValueError('License resource directory required')
            path = Path(resource_root) / notice['file']
            if path.name != notice['file'] or file_sha(path) != notice['sha256']:
                raise ValueError('Pinned license text differs: ' + notice['file'])
            notices.append(dict(name=notice['file'], text=path.read_text(encoding='utf-8-sig'), source_url=notice['source_url'], sha256=notice['sha256']))
        component = dict(name=rule['name'], version=version, license=rule['license'], notices=notices,
                         file_hashes=sorted({file_sha(p) for p in files}),
                         provenance=dict(basis='Exact hash of files in the verified PSF installer base; dependency identity from pinned upstream build rules',
                                         installer_url=INSTALLER_URL, installer_sha256=INSTALLER_SHA256,
                                         vendor_sbom_url=SBOM_URL, vendor_sbom_sha256=file_sha(vendor_sbom),
                                         vendor_package_id=upstream[0]['SPDXID'] if upstream else None,
                                         evidence_urls=rule['evidence_urls'], build_evidence=rule.get('build_evidence', []), base_files=sorted(p.name for p in files)))
        for ref in upstream[0].get('externalRefs', []) if upstream else []:
            if ref['referenceType'] == 'cpe23Type':
                component['cpe'] = ref['referenceLocator']
            elif ref['referenceType'] == 'purl':
                component['purl'] = ref['referenceLocator']
        if rule.get('purl'):
            component['purl'] = rule['purl']
        components.append(component)
        matched.update(files)
    return dict(schema_version=1, python_version=VERSION, installer_receipt_sha256=hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest(),
                components=components, unmapped_base_files=[dict(name=p.name, sha256=file_sha(p), pe_version=pe_version(p)) for p in native if p not in matched],
                license_review='required', vulnerability_review='required',
                limitations=['These are locally observed installed-base hashes, not vendor-provided binary file hashes. The official SPDX lists package/source hashes only.',
                             'The caller must retain its authentic installer download/signature/installation receipt; a JSON receipt alone is not a signature.',
                             'Component rules establish origin, not vulnerability or redistribution approval. Unmapped files and NOASSERTION licenses remain gates.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-base', type=Path, required=True)
    parser.add_argument('--vendor-sbom', type=Path, required=True)
    parser.add_argument('--installer-receipt', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if file_sha(args.vendor_sbom) != SBOM_SHA256:
        raise ValueError('Official pinned SPDX bytes differ')
    resources = Path(__file__).parent / 'release_licenses'
    rules = json.loads((Path(__file__).parent / 'release_native_rules.json').read_text(encoding='utf-8'))
    catalog = create_catalog(args.python_base, args.vendor_sbom, json.loads(args.installer_receipt.read_text(encoding='utf-8-sig')), rules, resources)
    with args.out.open('x', encoding='utf-8') as stream:
        json.dump(catalog, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(dict(components=len(catalog['components']), unmapped_base_files=len(catalog['unmapped_base_files']))))
