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
