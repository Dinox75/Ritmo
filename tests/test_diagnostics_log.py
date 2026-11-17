import tempfile
import unittest
from pathlib import Path

from dashboard.app import recent_log_lines


class DiagnosticsLogTests(unittest.TestCase):
    def test_reads_latest_lines_from_large_log(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ritmo.log"
            newest = [f"evento recente {i}: diagnóstico" for i in range(56)]
            path.write_bytes(b"old event\n" * 20000 + ("\r\n".join(newest) + "\r\n").encode())
            self.assertEqual(recent_log_lines(path), newest[-50:])

    def test_does_not_expose_partial_bounded_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ritmo.log"
            self.assertEqual(recent_log_lines(path), [])
            path.write_bytes(b"x" * 10000 + b"\r\nultima linha\n")
            self.assertEqual(recent_log_lines(path, max_bytes=48), ["ultima linha"])
