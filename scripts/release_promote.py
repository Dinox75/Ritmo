"""Promotion helpers. No build, no overwrite; external commands use argument arrays."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile
from release_bundle import verify_bundle, verify_approval, write_json


def command(*args, check=True):
    return subprocess.run(args, check=check, capture_output=True).stdout


def fetch_artifact(repo, artifact_id, expected_digest, destination):
    if not artifact_id.isdigit() or len(expected_digest) != 64:
        raise ValueError('Exact artifact ID and SHA-256 required')
    metadata = json.loads(command('gh', 'api', f'repos/{repo}/actions/artifacts/{artifact_id}'))
    if metadata['expired'] or metadata.get('digest') != 'sha256:' + expected_digest:
        raise ValueError('Artifact expired or digest differs from reviewed transport digest')
    raw = command('gh', 'api', f'repos/{repo}/actions/artifacts/{artifact_id}/zip')
    if hashlib.sha256(raw).hexdigest() != expected_digest:
        raise ValueError('Artifact transport checksum mismatch')
    destination.mkdir(parents=True, exist_ok=False)
    import io
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for member in archive.infolist():
            if member.is_dir() or Path(member.filename).name != member.filename or '\\' in member.filename or ':' in member.filename:
                raise ValueError('Artifact must contain only flat evidence files')
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError('Duplicate artifact members')
        archive.extractall(destination)
    return metadata


def same_bytes(expected, downloaded):
    return expected.is_file() and downloaded.is_file() and hashlib.sha256(expected.read_bytes()).digest() == hashlib.sha256(downloaded.read_bytes()).digest()


def promote(repo, assets, facts, visibility):
    version, commit = facts['version'], facts['source_commit']
    files = sorted(p for p in assets.iterdir() if p.is_file())
    owner, repository = repo.split('/')
    ref = f'ghcr.io/{repo.lower()}-windows:{version}'
    tag_result = subprocess.run(['gh', 'api', f'repos/{repo}/git/ref/tags/{version}'], capture_output=True)
    if tag_result.returncode == 0:
        tag = json.loads(tag_result.stdout)['object']
        if tag['type'] != 'commit' or tag['sha'] != commit:
            raise ValueError('Existing tag does not directly target approved commit')
    else:
        # Fail closed for access/network errors; only a verified 404 is absence.
        if b'404' not in tag_result.stderr:
            raise ValueError('Cannot inspect tag')
    # The tags endpoint cannot discover a draft whose tag is still pending.
    # A successful authenticated paginated listing distinguishes absence from
    # permissions/network errors and also finds partially created drafts.
    def find_release():
        pages = json.loads(command('gh', 'api', '--paginate', '--slurp', f'repos/{repo}/releases?per_page=100'))
        matches = [release for page in pages for release in page if release['tag_name'] == version]
        if len(matches) > 1:
            raise ValueError('Multiple releases for tag; inspect drafts before resuming')
        return matches[0] if matches else None
    release = find_release()
    if release is None:
        command('gh', 'release', 'create', version, '--repo', repo, '--target', commit, '--draft', '--prerelease', '--title', f'Ritmo {version}', '--notes', f'Windows x64; extraia EXE e _internal juntos. Sem assinatura digital. Código: {commit}. OCI: {ref}')
        release = find_release()
        if release is None:
            raise ValueError('New draft not visible; inspect authenticated release list before resuming')
    # A draft without a tag will create its tag from target_commitish at publish.
    # Accept only the exact reviewed commit, never an unresolved branch name.
    if release['draft'] and release.get('target_commitish') != commit:
        raise ValueError('Existing draft target differs from approved source commit')
    existing = {a['name'] for a in release['assets']}
    allowed = {p.name for p in files}
    if existing - allowed:
        raise ValueError('Unexpected release assets; refuse overwrite')
    with tempfile.TemporaryDirectory() as temp:
        tmp = Path(temp)
        for file in files:
            if file.name in existing:
                raw = command('gh', 'release', 'download', version, '--repo', repo, '--pattern', file.name, '--output', str(tmp / file.name))
                if not same_bytes(file, tmp / file.name):
                    raise ValueError('Existing release asset differs: ' + file.name)
            else:
                if not release['draft']:
                    raise ValueError('Published release is incomplete; refuse mutation')
                command('gh', 'release', 'upload', version, str(file), '--repo', repo)
        manifest_result = subprocess.run(['oras', 'manifest', 'fetch', ref], capture_output=True)
        if manifest_result.returncode:
            # ORAS reports MANIFEST_UNKNOWN/NAME_UNKNOWN for authenticated absence only.
            if not any(marker in manifest_result.stderr for marker in (b'MANIFEST_UNKNOWN', b'NAME_UNKNOWN', b'404 Not Found')):
                raise ValueError('Cannot inspect OCI tag')
            command('oras', 'push', ref, '--artifact-type', 'application/vnd.ritmo.windows-x64.v1', '--annotation', f'org.opencontainers.image.source=https://github.com/{repo}', '--annotation', f'org.opencontainers.image.revision={commit}', *[f'{p.name}:application/zip' if p.suffix == '.zip' else f'{p.name}:application/octet-stream' for p in files])
        manifest = json.loads(command('oras', 'manifest', 'fetch', ref))
        expected_layers = {p.name: 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        layers = {layer.get('annotations', {}).get('org.opencontainers.image.title'): layer['digest'] for layer in manifest['layers']}
        if layers != expected_layers or manifest.get('annotations', {}).get('org.opencontainers.image.revision') != commit:
            raise ValueError('Existing OCI bytes/revision differ; refuse overwrite')
        oci = tmp / 'oci'
        oci.mkdir()
        command('oras', 'pull', ref, '--output', str(oci))
        downloads = tmp / 'release'
        downloads.mkdir()
        command('gh', 'release', 'download', version, '--repo', repo, '--dir', str(downloads))
        if any(not same_bytes(p, oci / p.name) or not same_bytes(p, downloads / p.name) for p in files):
            raise ValueError('Downloaded Release/OCI bytes differ')
    # Package linkage and visibility are a gate, not a claim inferred from push success.
    account = json.loads(command('gh', 'api', f'users/{owner}'))
    prefix = 'orgs' if account['type'] == 'Organization' else 'users'
    package = json.loads(command('gh', 'api', f'{prefix}/{owner}/packages/container/{repository.lower()}-windows'))
    if package.get('visibility') != visibility or package.get('repository', {}).get('full_name', '').lower() != repo.lower():
        raise ValueError('GHCR visibility or repository association differs; inspect package settings and resume')
    if release['draft']:
        command('gh', 'release', 'edit', version, '--repo', repo, '--draft=false', '--prerelease')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'artifact-id', 'artifact-digest', 'qa-artifact-id', 'qa-artifact-digest', 'commit', 'run-id', 'reviewer'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--license-approved', action='store_true', required=True)
    parser.add_argument('--vulnerabilities-approved', action='store_true', required=True)
    parser.add_argument('--visibility', choices=('public', 'private'), default='public')
    parser.add_argument('--dry-run-receipt', type=Path)
    args = parser.parse_args()
    assets = Path.cwd() / 'release-assets'
    metadata = fetch_artifact(args.repo, args.artifact_id, args.artifact_digest, assets)
    qa_metadata = fetch_artifact(args.repo, args.qa_artifact_id, args.qa_artifact_digest, Path('qa-evidence'))
    if metadata['name'] != 'ritmo-distribuicao' or qa_metadata['name'] != 'ritmo-clean-windows-qa':
        raise ValueError('Unexpected artifact names')
    if str(metadata['workflow_run']['id']) != args.run_id or str(qa_metadata['workflow_run']['id']) != args.run_id:
        raise ValueError('QA and build must belong to approved run')
    run = json.loads(command('gh', 'api', f'repos/{args.repo}/actions/runs/{args.run_id}'))
    if run['conclusion'] != 'success' or run['head_sha'] != args.commit or run['head_branch'] != 'main' or run['event'] != 'workflow_dispatch' or run['path'] != '.github/workflows/distribute-windows.yml':
        raise ValueError('Approved build workflow/run/source mismatch')
    facts = verify_bundle(assets, args.commit, args.run_id)
    approval = json.loads(Path('qa-evidence/clean-windows.json').read_text(encoding='utf-8-sig'))
    approval.update(license_review='approved', vulnerability_review='approved', reviewed_by=args.reviewer)
    verify_approval(approval, facts)
    receipt = dict(source_commit=args.commit, build_run_id=args.run_id, artifact_id=args.artifact_id, artifact_digest=args.artifact_digest, qa_artifact_id=args.qa_artifact_id, qa_artifact_digest=args.qa_artifact_digest, archive_sha256=facts['archive_sha256'], reviewer=args.reviewer, verification='passed')
    if args.publish:
        if not args.dry_run_receipt or json.loads(args.dry_run_receipt.read_text()) != receipt:
            raise ValueError('An identical successful dry-run receipt is required before publication')
        os.chdir(assets)
        promote(args.repo, Path.cwd(), facts, args.visibility)
    else:
        write_json(Path('dry-run-receipt.json'), receipt)
    print('Promotion verification passed; published=' + str(args.publish))
