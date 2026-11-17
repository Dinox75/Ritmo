import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('release_bundle', Path(__file__).parents[1] / 'scripts/release_bundle.py')
bundle = importlib.util.module_from_spec(SPEC)
if SPEC.loader:
    SPEC.loader.exec_module(bundle)

class ReleaseBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package = self.root / 'Ritmo'
        (self.package / '_internal').mkdir(parents=True)
        (self.package / 'Ritmo.exe').write_bytes(b'MZtest')
        (self.package / '_internal' / 'native.dll').write_bytes(b'MZnative')

    def create(self):
        return bundle.create_bundle(self.package, self.root / 'out', 'v0.1.0-preview.1', 'a' * 40, '123', [])

    def test_complete_inventory_and_distinct_archive_executable_hashes(self):
        facts = self.create()
        self.assertNotEqual(facts['archive_sha256'], facts['executable_sha256'])
        checked = bundle.verify_bundle(self.root / 'out', 'a' * 40, '123')
        self.assertEqual(checked, facts)
        sbom = json.loads((self.root / 'out' / 'sbom.json').read_text())
        self.assertEqual(len(sbom['files']), 2)
        self.assertEqual(sbom['unresolved_native'], ['Ritmo.exe', '_internal/native.dll'])
        self.assertEqual(sbom['license_review'], 'required')

    def test_private_files_rejected(self):
        for name in ('preferences.json', 'secret.env', 'source_checkout.txt', 'token.pem', 'app.db', 'weights.gguf', 'debug.log'):
            with self.subTest(name=name):
                target = self.package / '_internal' / name
                target.write_text('private')
                with self.assertRaises(ValueError):
                    self.create()
                target.unlink()

    def test_tampering_any_file_is_rejected(self):
        facts = self.create()
        archive = self.root / 'out' / facts['archive']
        with zipfile.ZipFile(archive, 'a') as zipped:
            zipped.writestr('Ritmo/_internal/extra.dll', b'extra')
        with self.assertRaises(ValueError):
            bundle.verify_bundle(self.root / 'out', 'a' * 40, '123')

    def test_approval_binds_clean_qa_and_license_review_to_exact_build(self):
        facts = self.create()
        approval = dict(source_commit='a' * 40, archive_sha256=facts['archive_sha256'], build_run_id='123', clean_windows=True, result='passed', license_review='approved', vulnerability_review='approved', reviewed_by='reviewer')
        bundle.verify_approval(approval, facts)
        for key, bad in [('archive_sha256', '0'*64), ('clean_windows', False), ('license_review', 'required'), ('reviewed_by', '')]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    bundle.verify_approval(dict(approval, **{key: bad}), facts)

    def test_standard_sbom_lists_all_native_files_with_hashes(self):
        self.create()
        standard = json.loads((self.root / 'out' / 'bom.cdx.json').read_text())
        self.assertEqual(standard['bomFormat'], 'CycloneDX')
        self.assertEqual({c['name'] for c in standard['components'] if c['type'] == 'file'}, {'Ritmo.exe', '_internal/native.dll'})
        self.assertTrue(all(c['hashes'][0]['alg'] == 'SHA-256' for c in standard['components']))

    def test_local_checkout_path_embedded_in_payload_rejected(self):
        (self.package / '_internal/native.dll').write_bytes(b'MZ' + str(Path.cwd()).encode())
        with self.assertRaises(ValueError):
            self.create()

    def test_native_metadata_has_explicit_evidence_status(self):
        self.create()
        sbom = json.loads((self.root / 'out' / 'sbom.json').read_text())
        self.assertEqual(len(sbom['native_metadata']), 2)
        self.assertTrue(all(item['status'] in ('parsed', 'unavailable') for item in sbom['native_metadata']))

    def test_frozen_python_record_provenance_marks_distribution_redistributed(self):
        import importlib.metadata
        site = self.root / 'site'
        source = site / 'example' / '__init__.py'
        source.parent.mkdir(parents=True)
        source.write_text('VALUE = 1\n')
        metadata = site / 'example-1.2.dist-info'
        metadata.mkdir()
        (metadata / 'METADATA').write_text('Metadata-Version: 2.1\nName: example\nVersion: 1.2\nLicense: MIT\n')
        (metadata / 'RECORD').write_text('example/__init__.py,,\nexample-1.2.dist-info/METADATA,,\n')
        toc = self.root / 'Analysis-00.toc'
        toc.write_text(repr(([], [('example', str(source), 'PYMODULE')], [])))
        facts = bundle.create_bundle(self.package, self.root / 'out', 'v0.1.0-preview.1', 'a'*40, '123', [importlib.metadata.PathDistribution(metadata)], analysis_toc=[toc])
        sbom = json.loads((self.root / 'out/sbom.json').read_text())
        self.assertEqual(sbom['redistributed_components'][0]['name'], 'example')
        self.assertEqual(sbom['redistributed_components'][0]['frozen_modules'], ['example'])
        self.assertEqual(sbom['build_environment_only_or_unmapped'], [])
        standard = json.loads((self.root / 'out/bom.cdx.json').read_text())
        self.assertIn(('example', '1.2'), [(c['name'], c.get('version')) for c in standard['components'] if c['type'] == 'library'])
        self.assertNotIn(str(site), (self.root / 'out/sbom.json').read_text())
        bundle.verify_bundle(self.root / 'out', 'a'*40, '123')
