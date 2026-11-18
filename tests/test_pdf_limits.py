"""Compressed synthetic streams exercise extraction limits and recovery."""

import io
import base64
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tests.test_materials import sample_pdf
from storage.database import Database
from storage.materials import import_material


def compressed_pdf(expanded_bytes=9_000_000):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    writer = PdfWriter()
    writer.add_page(PdfReader(io.BytesIO(sample_pdf())).pages[0])
    stream = DecodedStreamObject()
    stream.set_data(b" " * expanded_bytes + b"BT /F1 12 Tf 72 720 Td (Synthetic) Tj ET")
    writer.pages[0][NameObject("/Contents")] = writer._add_object(stream.flate_encode())
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class PdfLimitCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Database(Path(self.temp.name) / "ritmo.db")
        self.db.initialize()
        self.subject = self.db.create_subject("Synthetic PDF limits")

    def add(self, filename, content):
        return import_material(self.db, self.subject["id"], "", filename,
                               base64.b64encode(content).decode("ascii"))

    def test_compressed_stream_is_rejected_and_next_pdf_import_succeeds(self):
        content = compressed_pdf()
        self.assertLess(len(content), 20_000)
        rejected = self.add("compressed.pdf", content)
        self.assertEqual(rejected["status"], "error")
        self.assertTrue(rejected["error"])
        self.assertEqual(rejected["chunks"], [])
        original = self.db.path.parent / "materials" / rejected["stored_name"]
        self.assertEqual(original.read_bytes(), content)
        self.assertEqual(self.add("recovery.pdf", sample_pdf())["status"], "ready")

    def test_concurrent_compressed_imports_fail_independently_and_recover(self):
        content = compressed_pdf()
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(self.add, f"compressed-{index}.pdf", content) for index in range(3)]
            self.assertEqual([future.result(timeout=20)["status"] for future in futures], ["error"] * 3)
        self.assertEqual(self.add("recovery.pdf", sample_pdf())["status"], "ready")
