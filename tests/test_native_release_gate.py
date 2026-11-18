import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('release_gate',Path(__file__).parents[1]/'scripts/release_bundle.py')
bundle=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundle)


class NativeReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.facts=dict(source_commit='a'*40,archive_sha256='b'*64,build_run_id='123',executable_sha256='c'*64)
        self.native=dict(**self.facts,method='native-uia',result='passed',
                         stages=dict(executable=True,native_window=True,native_authorization=True,qa_native_connection=True),
                         environment=dict(window_station_visible=True,input_desktop_open=True),
                         native_write_verified=True,native_cancel_preserved=True,natural_shutdown=True,port_released=True)
        self.approval=dict(**{k:self.facts[k] for k in ('source_commit','archive_sha256','build_run_id')},
                           clean_windows=True,result='passed',license_review='approved',vulnerability_review='approved',reviewed_by='reviewer')

    def test_requires_native_evidence_even_when_api_approval_passes(self):
        with self.assertRaises(ValueError):bundle.verify_approval(self.approval,self.facts)

    def test_exact_native_ui_pass_does_not_require_cdp(self):
        bundle.verify_approval(self.approval,self.facts,dict(self.native,cdp={'connected':False}))

    def test_every_native_binding_and_action_is_required(self):
        for key,value in [('archive_sha256','d'*64),('source_commit','d'*40),('executable_sha256','d'*64),
                          ('build_run_id','124'),('native_cancel_preserved',False),('native_write_verified',False),
                          ('natural_shutdown',False),('port_released',False),('forced_cleanup',True),('method','external-browser')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                bundle.verify_approval(self.approval,self.facts,dict(self.native,**{key:value}))
        for stage in self.native['stages']:
            with self.subTest(stage=stage),self.assertRaises(ValueError):
                bundle.verify_approval(self.approval,self.facts,dict(self.native,stages=dict(self.native['stages'],**{stage:False})))


if __name__=='__main__':unittest.main()
