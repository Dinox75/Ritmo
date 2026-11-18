import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import scan_grype_bundle as scan


class GrypeEvidenceTests(unittest.TestCase):
    def report(self,matches=None):
        return dict(matches=matches or [],descriptor=dict(version=scan.VERSION,db=dict(status=dict(valid=True))))
    def test_native_positive_control_and_valid_database_are_required(self):
        self.assertEqual(scan.assess(self.report(),0,self.report())['status'],'incomplete')
        positive=self.report([{'vulnerability':{'id':'CVE-2014-0160'}}])
        self.assertEqual(scan.assess(self.report(),0,positive)['status'],'completed_no_reported_findings')
        invalid=self.report();invalid['descriptor']['db']['status']['valid']=False
        self.assertEqual(scan.assess(invalid,0,positive)['status'],'incomplete')
    def test_tool_failure_or_findings_never_turn_into_pass(self):
        positive=self.report([{'vulnerability':{'id':'CVE-2014-0160'}}])
        self.assertEqual(scan.assess(None,1,positive)['status'],'error')
        self.assertEqual(scan.assess(self.report([{}]),0,positive)['status'],'findings_require_review')
