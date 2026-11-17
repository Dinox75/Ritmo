import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import smoke_windows


class SmokeFailureEvidenceTests(unittest.TestCase):
    def test_missing_executable_keeps_failure_report_without_raw_error(self):
        with tempfile.TemporaryDirectory() as folder:
            report=Path(folder)/'smoke.json'
            with patch.object(sys,'argv',['smoke','missing.exe',str(report)]),patch.object(subprocess,'run',side_effect=FileNotFoundError('secret-cookie')):
                self.assertNotEqual(smoke_windows.main(),0)
            data=json.loads(report.read_text(encoding='utf8'))
            self.assertFalse(data['ready']);self.assertEqual(data['error_type'],'FileNotFoundError')
            self.assertNotIn('secret-cookie',report.read_text(encoding='utf8'))

    def test_nonzero_without_app_report_is_explicit_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            report=Path(folder)/'smoke.json'
            with patch.object(sys,'argv',['smoke','missing.exe',str(report)]),patch.object(subprocess,'run',return_value=subprocess.CompletedProcess([],7)):
                self.assertEqual(smoke_windows.main(),7)
            self.assertEqual(json.loads(report.read_text())['returncode'],7)


if __name__=='__main__':unittest.main()
