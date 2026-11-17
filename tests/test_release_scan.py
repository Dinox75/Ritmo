import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import release_scan as scan

class ReleaseScanTests(unittest.TestCase):
    def test_python_results_require_every_exact_requirement_and_report_skips(self):
        expected={'example': '1.0', 'second': '2.0'}
        result=scan.assess_pip(dict(dependencies=[dict(name='example',version='1.0',vulns=[])]),0,expected)
        self.assertEqual(result['status'],'incomplete')
        self.assertEqual(result['missing'], ['second==2.0'])
        result=scan.assess_pip(dict(dependencies=[dict(name='example',version='1.0',vulns=[],skip_reason='unsupported'),dict(name='second',version='2.0',vulns=[dict(id='CVE-test')])]),1,expected)
        self.assertEqual(result['status'],'findings')
        self.assertEqual(result['findings'],1)
        self.assertEqual(result['skipped'], ['example==1.0'])

    def test_native_tool_failure_never_becomes_zero_findings(self):
        self.assertEqual(scan.assess_cve(None,4)['status'],'error')
        self.assertEqual(scan.assess_cve({'metadata':{},'database_info':{},'vulnerabilities':{'report':[]}},0)['status'],'incomplete')
        report=dict(metadata={'tool':{'version':'3.4'}},database_info={'last_updated':'2026-11-17','total_entries':{'NVD':123}},vulnerabilities={'report':[]})
        self.assertEqual(scan.assess_cve(report,0)['status'],'completed')
        self.assertEqual(scan.assess_cve(report,1)['status'],'error')

    def test_exact_requirements_reject_remote_urls_and_dependency_resolution(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'requirements.txt'
            p.write_text('example==1.0\n')
            self.assertEqual(scan.read_requirements(p),{'example':'1.0'})
            for value in ['--index-url https://bad.example\n','example @ https://bad.example/a.whl\n','example>=1.0\n','-r other.txt\n']:
                p.write_text(value)
                with self.assertRaises(ValueError): scan.read_requirements(p)

    def test_pipeline_uses_verified_zip_and_writes_honest_coverage_report(self):
        from unittest.mock import patch
        import release_bundle
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);package=root/'Ritmo';(package/'_internal').mkdir(parents=True)
            (package/'Ritmo.exe').write_bytes(b'MZapp');(package/'_internal/vendor.dll').write_bytes(b'MZvendor')
            assets=root/'assets'
            facts=release_bundle.create_bundle(package,assets,'v0.1.0-preview.1','a'*40,'123',[])
            calls=[]
            def run(args, env, prefix, timeout):
                calls.append(args)
                if '-c' in args:
                    report={'pip-audit':'2.10.1','cve-bin-tool':'3.4','python':'3.11','dependencies':[]}
                    Path(str(prefix)+'.stdout.txt').write_text(json.dumps(report))
                else:
                    cache=Path(env['USERPROFILE'])/'.cache/cve-bin-tool/cve.db'
                    cache.write_bytes(b'test database snapshot')
                    output=Path(args[args.index('--output-file')+1])
                    output.write_text(json.dumps(dict(metadata={'tool':{'version':'3.4'}},database_info={'last_updated':'2026-11-17','total_entries':{'NVD':123}},vulnerabilities={'report':[]})))
                return dict(returncode=0,timed_out=False)
            with patch.object(scan,'run_command',side_effect=run):
                report=scan.scan_bundle(assets,root/'scan','a'*40,'123',Path(sys.executable),120)
            self.assertEqual(report['archive_sha256'],facts['archive_sha256'])
            self.assertFalse(report['release_approved'])
            self.assertEqual(report['result'],'coverage_review_required')
            self.assertEqual(report['coverage']['unmapped_native'],['Ritmo.exe','_internal/vendor.dll'])
            self.assertEqual(len([args for args in calls if 'cve_bin_tool.cli' in args]),2)
            self.assertEqual(len([args for args in calls if 'pip_audit' in args]),0)
            self.assertTrue((root/'scan/scan-report.json').is_file())
            self.assertTrue((root/'scan/extracted/Ritmo/_internal/vendor.dll').is_file())

    def test_missing_extraction_utility_and_errors_are_preserved_as_failures(self):
        with tempfile.TemporaryDirectory() as folder:
            log=Path(folder)/'stderr.txt'
            log.write_text('WARNING experimental json2\nERROR failed to extract app.exe: 7z not found\n')
            self.assertEqual(scan.diagnostic_failures(log),['ERROR failed to extract app.exe: 7z not found'])
