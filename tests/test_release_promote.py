import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import release_promote

class PromotionTests(unittest.TestCase):
    def test_equal_bytes_required_for_existing_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / 'a', Path(folder) / 'b'
            a.write_bytes(b'approved')
            b.write_bytes(b'changed')
            self.assertFalse(release_promote.same_bytes(a, b))
            b.write_bytes(b'approved')
            self.assertTrue(release_promote.same_bytes(a, b))
            b.unlink()
            self.assertFalse(release_promote.same_bytes(a, b))

    def test_bad_artifact_identifiers_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as folder:
            for artifact, digest in [('untrusted/path', 'a'*64), ('12', 'short')]:
                with self.assertRaises(ValueError):
                    release_promote.fetch_artifact('owner/repo', artifact, digest, Path(folder) / 'out')

class PromotionDraftTests(unittest.TestCase):
    def exercise(self, target=None, existing_asset=False, fail_listing=False, changed_asset=False):
        import hashlib
        import json
        from types import SimpleNamespace
        from unittest.mock import patch
        self.calls = []
        with tempfile.TemporaryDirectory() as folder:
            assets = Path(folder)
            (assets / 'candidate.zip').write_bytes(b'approved zip')
            self.release = None if target is None else dict(id=42, tag_name='v0.1.0-preview.1', target_commitish=target, draft=True, assets=[dict(name='candidate.zip')] if existing_asset else [])
            def run(args, **kwargs):
                self.calls.append(tuple(args))
                if args[:2] == ['gh', 'api'] and '/git/ref/tags/' in args[2]:
                    return SimpleNamespace(returncode=1, stderr=b'HTTP 404: Not Found', stdout=b'')
                if args[:3] == ['oras', 'manifest', 'fetch']:
                    return SimpleNamespace(returncode=1, stderr=b'MANIFEST_UNKNOWN', stdout=b'')
                raise AssertionError('Unexpected direct external operation: ' + repr(args))
            def command(*args, **kwargs):
                self.calls.append(args)
                if args[:2] == ('gh', 'api') and 'repos/owner/repo/releases?per_page=100' in args:
                    if fail_listing:
                        raise release_promote.subprocess.CalledProcessError(1, args, stderr=b'HTTP 403')
                    return json.dumps([[self.release] if self.release else []]).encode()
                if args[:3] == ('gh', 'release', 'create'):
                    self.release = dict(id=42, tag_name='v0.1.0-preview.1', target_commitish='a'*40, draft=True, assets=[])
                    return b''
                if args[:3] == ('gh', 'release', 'upload'):
                    self.release['assets'].append(dict(name=Path(args[4]).name))
                    return b''
                if args[:3] == ('gh', 'release', 'download'):
                    destination = Path(args[args.index('--output')+1]) if '--output' in args else Path(args[args.index('--dir')+1]) / 'candidate.zip'
                    destination.write_bytes(b'different' if changed_asset else b'approved zip')
                    return b''
                if args[:2] == ('oras', 'push') or args[:3] == ('gh', 'release', 'edit'):
                    return b''
                if args[:3] == ('oras', 'manifest', 'fetch'):
                    return json.dumps(dict(annotations={'org.opencontainers.image.revision':'a'*40}, layers=[dict(digest='sha256:'+hashlib.sha256(b'approved zip').hexdigest(), annotations={'org.opencontainers.image.title':'candidate.zip'})])).encode()
                if args[:2] == ('oras', 'pull'):
                    (Path(args[args.index('--output')+1])/'candidate.zip').write_bytes(b'approved zip')
                    return b''
                if args == ('gh', 'api', 'users/owner'):
                    return b'{"type":"User"}'
                if args == ('gh', 'api', 'users/owner/packages/container/repo-windows'):
                    return b'{"visibility":"public","repository":{"full_name":"owner/repo"}}'
                raise AssertionError('Unexpected external operation: ' + repr(args))
            with patch.object(release_promote.subprocess, 'run', side_effect=run), patch.object(release_promote, 'command', side_effect=command):
                release_promote.promote('owner/repo', assets, dict(version='v0.1.0-preview.1', source_commit='a'*40), 'public')

    def test_new_draft_found_without_tag_endpoint_and_published_after_downloads(self):
        self.exercise()
        self.assertEqual(sum(call[:3] == ('gh','release','create') for call in self.calls), 1)
        self.assertEqual(self.calls[-1][:3], ('gh', 'release', 'edit'))

    def test_draft_with_wrong_commit_is_never_reused(self):
        with self.assertRaisesRegex(ValueError, 'target'):
            self.exercise(target='b'*40)
        self.assertFalse(any(call[:2] == ('oras', 'push') or call[:2] == ('gh', 'release') for call in self.calls))

    def test_matching_partial_draft_reuses_bytes_without_recreation_or_upload(self):
        self.exercise(target='a'*40, existing_asset=True)
        self.assertFalse(any(call[:3] in (('gh','release','create'), ('gh','release','upload')) for call in self.calls))

    def test_listing_failure_never_creates_another_draft(self):
        with self.assertRaises(release_promote.subprocess.CalledProcessError):
            self.exercise(fail_listing=True)
        self.assertFalse(any(call[:3] == ('gh','release','create') for call in self.calls))

    def test_changed_partial_asset_is_never_overwritten(self):
        with self.assertRaisesRegex(ValueError, 'differs'):
            self.exercise(target='a'*40, existing_asset=True, changed_asset=True)
        self.assertFalse(any(call[:3] == ('gh','release','upload') for call in self.calls))
