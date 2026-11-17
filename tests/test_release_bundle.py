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
        self.assertEqual(len(sbom['files']), 5)
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
        native = dict(**{k: facts[k] for k in ('source_commit','archive_sha256','build_run_id','executable_sha256')},
                      method='native-uia', result='passed', native_write_verified=True,
                      native_cancel_preserved=True,natural_shutdown=True,port_released=True,
                      environment=dict(window_station_visible=True,input_desktop_open=True),
                      stages=dict(executable=True,native_window=True,native_authorization=True,qa_native_connection=True))
        bundle.verify_approval(approval, facts, native)
        for key, bad in [('archive_sha256', '0'*64), ('clean_windows', False), ('license_review', 'required'), ('reviewed_by', '')]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    bundle.verify_approval(dict(approval, **{key: bad}), facts, native)

    def test_standard_sbom_lists_all_native_files_with_hashes(self):
        self.create()
        standard = json.loads((self.root / 'out' / 'bom.cdx.json').read_text())
        self.assertEqual(standard['bomFormat'], 'CycloneDX')
        self.assertTrue({'Ritmo.exe', '_internal/native.dll'}.issubset({c['name'] for c in standard['components'] if c['type'] == 'file'}))
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

    def test_zip_carries_notices_and_source_manifest_without_hash_recursion(self):
        facts = self.create()
        with zipfile.ZipFile(self.root / 'out' / facts['archive']) as archive:
            self.assertEqual(archive.read('Ritmo/_internal/release/THIRD-PARTY-NOTICES.txt'), (self.root / 'out/THIRD-PARTY-NOTICES.txt').read_bytes())
            source = json.loads(archive.read('Ritmo/_internal/release/source-manifest.json'))
            self.assertEqual(source['source_commit'], 'a'*40)
            self.assertNotIn('archive_sha256', source)
            self.assertEqual({f['path'] for f in source['payload_files']}, {'Ritmo.exe', '_internal/native.dll'})
        bundle.verify_bundle(self.root / 'out', 'a'*40, '123')

    def test_native_catalog_requires_exact_bytes_and_retains_unknown_license_gate(self):
        catalog = self.root / 'native-catalog.json'
        catalog.write_text(json.dumps(dict(schema_version=1, components=[dict(name='VendorRuntime', version='4.2', license='NOASSERTION', notices=[], purl='pkg:generic/vendor-runtime@4.2', cpe='cpe:2.3:a:vendor:runtime:4.2:*:*:*:*:*:*:*', provenance={'source_url':'https://vendor.example/runtime','basis':'trusted installer file match'}, file_hashes=[bundle.sha(b'MZnative')])])), encoding='utf-8')
        bundle.create_bundle(self.package, self.root / 'out', 'v0.1.0-preview.1', 'a'*40, '123', [], native_catalog=[catalog])
        sbom = json.loads((self.root / 'out/sbom.json').read_text())
        self.assertEqual(sbom['native_components'][0]['files'], ['_internal/native.dll'])
        self.assertEqual(sbom['unresolved_native'], ['Ritmo.exe'])
        self.assertTrue(sbom['native_license_issues'])
        self.assertEqual(sbom['license_review'], 'required')
        self.assertNotIn('VendorRuntime', str(sbom['build_environment_only_or_unmapped']))

    def test_record_matching_is_case_insensitive_and_handles_pywin32_relocation(self):
        import importlib.metadata
        site = self.root / 'site'
        source = site / 'pywin32_system32' / 'example.dll'
        source.parent.mkdir(parents=True)
        source.write_bytes(b'MZnative')
        metadata = site / 'example-1.2.dist-info'
        metadata.mkdir()
        (metadata / 'METADATA').write_text('Metadata-Version: 2.1\nName: example\nVersion: 1.2\nLicense: MIT\n')
        (metadata / 'RECORD').write_text('pywin32_system32/example.dll,,\n')
        (self.package / '_internal/native.dll').rename(self.package / '_internal/EXAMPLE.DLL')
        facts = bundle.create_bundle(self.package, self.root / 'out', 'v0.1.0-preview.1', 'a'*40, '123', [importlib.metadata.PathDistribution(metadata)])
        sbom = json.loads((self.root / 'out/sbom.json').read_text())
        self.assertEqual(sbom['redistributed_components'][0]['files'], ['_internal/EXAMPLE.DLL'])

    def test_source_manifest_cannot_disagree_with_external_commit(self):
        facts = self.create()
        facts['source_commit'] = 'b'*40
        bundle.write_json(self.root / 'out/build-info.json', facts)
        checksums = self.root / 'out/SHA256SUMS.txt'
        checksums.write_text(''.join(f'{bundle.sha(path.read_bytes())}  {path.name}\n' for path in sorted((self.root/'out').iterdir()) if path.name != 'SHA256SUMS.txt'), encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'Embedded source'):
            bundle.verify_bundle(self.root / 'out', 'b'*40, '123')

    def test_redistributed_requirement_scan_input_excludes_unmapped_build_packages(self):
        self.create()
        self.assertEqual((self.root / 'out/redistributed-requirements.txt').read_text(), '')
        self.assertTrue((self.root / 'out/native-components.csv').is_file())

    def test_native_catalog_never_matches_changed_bytes_by_filename(self):
        catalog = self.root / 'native-catalog.json'
        catalog.write_text(json.dumps(dict(schema_version=1, components=[dict(name='VendorRuntime', version='4.2', license='MIT', notices=[dict(name='license', text='license')], provenance={'source_url':'https://vendor.example/runtime'}, file_hashes=[bundle.sha(b'other native bytes')])])), encoding='utf-8')
        bundle.create_bundle(self.package, self.root/'out', 'v0.1.0-preview.1', 'a'*40, '123', [], native_catalog=[catalog])
        sbom = json.loads((self.root/'out/sbom.json').read_text())
        self.assertEqual(sbom['native_components'], [])
        self.assertIn('_internal/native.dll', sbom['unresolved_native'])

    def test_generated_exe_origin_requires_matching_exe_toc_output_and_record_input(self):
        import importlib.metadata
        site=self.root/'site'
        bootloader=site/'PyInstaller/bootloader/runw.exe'
        bootloader.parent.mkdir(parents=True)
        bootloader.write_bytes(b'bootloader input')
        metadata=site/'pyinstaller-6.0.dist-info'
        metadata.mkdir()
        (metadata/'METADATA').write_text('Metadata-Version: 2.1\nName: pyinstaller\nVersion: 6.0\nLicense: GPL-2.0-with-bootloader-exception\n')
        (metadata/'RECORD').write_text('PyInstaller/bootloader/runw.exe,,\n')
        output=self.root/'built/Ritmo.exe';output.parent.mkdir();output.write_bytes(b'MZtest')
        toc=self.root/'EXE-00.toc'
        toc.write_text(repr((str(output), [('runw.exe',str(bootloader),'EXECUTABLE')])))
        sbom=bundle.inventory(self.package,[importlib.metadata.PathDistribution(metadata)],analysis_toc=[toc])
        self.assertNotIn('Ritmo.exe',sbom['unresolved_native'])
        evidence=sbom['redistributed_components'][0]['embedded_native_inputs'][0]
        self.assertEqual(evidence['output_sha256'], bundle.sha(b'MZtest'))
        self.assertNotIn(str(site),json.dumps(sbom))
        output.write_bytes(b'different output')
        sbom=bundle.inventory(self.package,[importlib.metadata.PathDistribution(metadata)],analysis_toc=[toc])
        self.assertIn('Ritmo.exe',sbom['unresolved_native'])

    def test_zip_includes_exact_psf_crt_notice_and_protective_terms(self):
        facts=self.create()
        notice=(Path(__file__).parents[1]/'scripts/release_licenses/python-windows-crtlicense.txt').read_bytes()
        with zipfile.ZipFile(self.root/'out'/facts['archive']) as archive:
            terms=archive.read('Ritmo/_internal/release/VC-RUNTIME-TERMS.txt')
            self.assertIn(notice,terms)
            self.assertIn(b'Microsoft Distributable Code',terms)
            self.assertIn(b'only to Microsoft',terms)
