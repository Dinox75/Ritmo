"""Importação, trechos, backup e seleção de câmera sem tocar em dados reais."""

import base64
import io
import json
import tempfile
import threading
import types
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from unittest.mock import patch

from dashboard.app import make_server
from monitor.cameras import test_camera
from storage.database import Database
from storage.materials import import_material, remove_material


def sample_pdf():
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):
        DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 720 Td (Conceito em PDF) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def sample_docx():
    document = (b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                b'<w:body><w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Secao</w:t></w:r></w:p>'
                b'<w:p><w:r><w:t>Conceito no DOCX</w:t></w:r></w:p></w:body></w:document>')
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", document)
    return output.getvalue()


class MaterialCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "ritmo.db")
        self.db.initialize()
        self.subject = self.db.create_subject("Física")

    def tearDown(self):
        self.temp.cleanup()

    def add(self, filename, content):
        return import_material(self.db, self.subject["id"], "", filename,
                               base64.b64encode(content).decode("ascii"))

    def test_pdf_docx_txt_chunks_note_link_backup_and_removal(self):
        pdf = self.add("aula.pdf", sample_pdf())
        docx = self.add("aula.docx", sample_docx())
        txt = self.add("resumo.txt", "Primeira linha\nSegunda linha com acento: ação".encode())
        self.assertEqual([item["status"] for item in (pdf, docx, txt)], ["ready"] * 3)
        self.assertIn("Conceito em PDF", pdf["chunks"][0]["body"])
        self.assertEqual(pdf["chunks"][0]["locator"], "Página 1 · trecho 1")
        self.assertIn("Conceito no DOCX", " ".join(item["body"] for item in docx["chunks"]))
        self.assertIn("Segunda linha", txt["chunks"][0]["body"])
        note = self.db.create_note(self.subject["id"], "Minha anotação", material_id=pdf["id"],
                                   chunk_id=pdf["chunks"][0]["id"])
        linked = self.db.list_notes()[0]
        self.assertEqual(linked["id"], note["id"])
        self.assertEqual(linked["material_name"], "aula")
        self.assertIn("Conceito em PDF", linked["quote"])
        with self.assertRaises(ValueError):
            self.db.create_note(self.subject["id"], "Inválida", material_id=pdf["id"],
                                chunk_id=docx["chunks"][0]["id"])
        self.assertEqual(len(self.db.list_notes()), 1)
        backup = self.db.create_backup()
        with zipfile.ZipFile(backup["path"]) as archive:
            self.assertEqual(archive.testzip(), None)
            self.assertIn("database/ritmo.db", archive.namelist())
            for item in (pdf, docx, txt):
                self.assertIn("materials/" + item["stored_name"], archive.namelist())
            restored = Path(self.temp.name) / "restored.db"
            restored.write_bytes(archive.read("database/ritmo.db"))
            self.assertEqual(len(Database(restored).list_materials()), 3)
        self.db.rename_material(pdf["id"], "PDF renomeado")
        self.assertEqual(self.db.list_notes()[0]["material_name"], "PDF renomeado")
        original = Path(self.temp.name) / "materials" / pdf["stored_name"]
        self.assertTrue(original.is_file())
        remove_material(self.db, pdf["id"])
        self.assertFalse(original.exists())
        self.assertEqual(len(self.db.list_materials()), 2)
        self.assertEqual(self.db.list_notes()[0]["body"], "Minha anotação")
        self.assertIsNone(self.db.list_notes()[0]["material_id"])

    def test_invalid_and_scanned_files_keep_original_without_crashing(self):
        with self.assertRaisesRegex(ValueError, "PDF inválido"):
            self.add("fake.pdf", b"not a PDF")
        broken = self.add("broken.docx", b"PKbroken")
        self.assertEqual(broken["status"], "error")
        self.assertTrue((Path(self.temp.name) / "materials" / broken["stored_name"]).is_file())
        scanned = self.add("scan.pdf", self._blank_pdf())
        self.assertEqual(scanned["status"], "no_text")
        self.assertIn("OCR", scanned["error"])
        self.assertEqual(self.add("depois.txt", b"Ainda funciona")["status"], "ready")

    @staticmethod
    def _blank_pdf():
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        output = io.BytesIO(); writer.write(output)
        return output.getvalue()

    def test_http_upload_original_note_and_delete_confirmation(self):
        server = make_server(self.db, 0)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        def call(route, method="GET", body=None):
            request = urllib.request.Request(base + route,
                data=json.dumps(body).encode() if body is not None else None,
                headers={"Content-Type": "application/json"}, method=method)
            with urllib.request.urlopen(request) as response:
                return json.load(response)

        try:
            item = call("/api/materials", "POST", {"subject_id": self.subject["id"],
                "name": "Texto", "filename": "x.txt", "content_base64": base64.b64encode(b"Trecho de teste").decode()})
            self.assertEqual(call("/api/materials")[0]["id"], item["id"])
            with urllib.request.urlopen(base + "/api/materials/" + item["id"] + "/original") as response:
                self.assertEqual(response.read(), b"Trecho de teste")
                self.assertIn("attachment", response.headers["Content-Disposition"])
            with self.assertRaises(urllib.error.HTTPError) as error:
                call("/api/materials/" + item["id"], "DELETE", {"confirmation": "não"})
            self.assertEqual(error.exception.code, 400)
            self.assertTrue(call("/api/materials/" + item["id"], "DELETE", {"confirmation": "REMOVER"})["notes_preserved"])
            self.assertEqual(call("/api/materials"), [])
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_camera_without_device_releases_handle_and_does_not_switch_index(self):
        camera = types.SimpleNamespace(released=False)
        camera.isOpened = lambda: False
        camera.release = lambda: setattr(camera, "released", True)
        cv2 = types.ModuleType("cv2")
        cv2.CAP_DSHOW = 700
        calls = []
        cv2.VideoCapture = lambda index, backend: (calls.append((index, backend)) or camera)
        with patch.dict("sys.modules", {"cv2": cv2}), patch("monitor.cameras._privacy_denied", return_value=False):
            result = test_camera(3, names=[])
        self.assertEqual(result["status"], "not_found")
        self.assertEqual(calls, [(3, 700)])
        self.assertTrue(camera.released)


if __name__ == "__main__":
    unittest.main()
