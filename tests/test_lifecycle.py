import unittest
from unittest.mock import patch
from utils.lifecycle import event


class LifecycleTests(unittest.TestCase):
    def test_desktop_native_cancel_records_only_outcome(self):
        from desktop import DesktopApp
        app=DesktopApp()
        with patch('desktop.confirm_erase_native',return_value=False), self.assertLogs(level='INFO') as log:
            app.request_erase()
        self.assertIn('native_erase_cancelled',''.join(log.output))
        self.assertFalse(app.erase_requested)

    def test_allowlisted_four_phase_evidence_and_no_credentials(self):
        with self.assertLogs(level='INFO') as log:
            value=event('native_shown','native','shown',surface='application')
        self.assertEqual(value['phase'],'native')
        self.assertIn('RITMO_LIFECYCLE',log.output[0])
        for field in ('cookie','token','code','headers','url','body'):
            with self.assertRaises(ValueError):event('bad','authorization','failed',**{field:'sensitive-sentinel'})
        self.assertNotIn('sensitive-sentinel',''.join(log.output))

    def test_dynamic_error_messages_and_unknown_surfaces_refused(self):
        with self.assertRaises(ValueError):event('bad','authorization','failed',error_type='Failure with secret payload')
        with self.assertRaises(ValueError):event('bad','native','shown',surface='http://local/?secret=value')
