import ctypes
import logging
import os
import sys
import unittest
from unittest.mock import MagicMock


@unittest.skipUnless(sys.platform=='win32','Windows inherited-handle bootstrap')
class AuthorizationPipeTests(unittest.TestCase):
    def test_invalid_handle_does_not_issue_credential(self):
        from utils.authorization_pipe import write_one_time_code
        session=MagicMock()
        with self.assertRaises(ValueError):write_one_time_code(0,session)
        session.issue_code.assert_not_called()

    def test_private_pipe_delivers_only_one_time_code_and_never_logs_it(self):
        import msvcrt
        from dashboard.session import AppSession
        from utils.authorization_pipe import write_one_time_code
        read,write=os.pipe();kernel=ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype=ctypes.c_void_p
        handle=ctypes.c_void_p()
        current=ctypes.c_void_p(kernel.GetCurrentProcess())
        assert kernel.DuplicateHandle(current,ctypes.c_void_p(msvcrt.get_osfhandle(write)),current,ctypes.byref(handle),0,False,2)
        os.close(write)
        session=AppSession()
        try:
            with self.assertLogs(level=logging.INFO) as log:write_one_time_code(handle.value,session)
            code=os.read(read,512).decode('ascii').strip()
            self.assertTrue(session.exchange(code));self.assertFalse(session.exchange(code))
            self.assertNotIn(code,''.join(log.output));self.assertNotIn(session.token,''.join(log.output))
        finally:os.close(read)
