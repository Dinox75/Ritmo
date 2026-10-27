"""Importação local de materiais; guarda o original e extrai somente texto."""

import base64
import binascii
import hashlib
import io
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


MAX_FILE_BYTES = 5_000_000
MAX_TEXT_CHARS = 1_000_000
MAX_CHUNKS = 1200
ALLOWED = {".pdf": "PDF", ".docx": "DOCX", ".txt": "TXT"}
WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _pieces(text, locator, *, preserve_lines=False):
    text = text.strip("\r\n") if preserve_lines else " ".join(text.split())
    return [(f"{locator} · trecho {number}", text[offset:offset + 1800])
            for number, offset in enumerate(range(0, len(text), 1800), 1) if text[offset:offset + 1800].strip()]


def _extract_pdf(content):
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content), strict=False)
    if reader.is_encrypted:
        raise ValueError("PDF protegido por senha; use uma cópia sem senha")
    if len(reader.pages) > 200:
        raise ValueError("PDF excede o limite de 200 páginas")
    chunks = []
    for page_number, page in enumerate(reader.pages, 1):
        chunks.extend(_pieces(page.extract_text() or "", f"Página {page_number}"))
        if len(chunks) > MAX_CHUNKS:
            raise ValueError("texto extraído excede o limite de trechos")
    return chunks


def _extract_docx(content):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        infos = archive.infolist()
        if len(infos) > 1000 or sum(item.file_size for item in infos) > 20_000_000:
            raise ValueError("DOCX excede o limite de conteúdo expandido")
        if "[Content_Types].xml" not in archive.namelist() or "word/document.xml" not in archive.namelist():
            raise ValueError("DOCX sem documento principal")
        document = archive.getinfo("word/document.xml")
        if document.file_size > 12_000_000:
            raise ValueError("texto do DOCX é grande demais")
        root = ET.fromstring(archive.read(document))
    chunks, section = [], "Documento"
    for number, paragraph in enumerate(root.iter(WORD + "p"), 1):
        text = "".join(node.text or "" for node in paragraph.iter(WORD + "t")).strip()
        if not text:
            continue
        style = paragraph.find(f"{WORD}pPr/{WORD}pStyle")
        style_name = style.get(WORD + "val", "") if style is not None else ""
        if style_name.lower().startswith(("heading", "titulo", "título")):
            section = text[:100]
        chunks.extend(_pieces(text, f"{section} · parágrafo {number}"))
        if len(chunks) > MAX_CHUNKS:
            raise ValueError("texto extraído excede o limite de trechos")
    return chunks


def _extract_txt(content):
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1252")
    if "\x00" in text:
        raise ValueError("TXT contém bytes binários")
    chunks, buffer, first_line = [], [], 1
    for number, line in enumerate(text.splitlines(), 1):
        if sum(map(len, buffer)) + len(line) > 1600 and buffer:
            chunks.extend(_pieces("\n".join(buffer), f"Linhas {first_line}–{number - 1}", preserve_lines=True))
            buffer, first_line = [], number
        buffer.append(line)
    if buffer:
        chunks.extend(_pieces("\n".join(buffer), f"Linhas {first_line}–{number}", preserve_lines=True))
    return chunks


def import_material(database, subject_id, name, filename, encoded):
    if not isinstance(filename, str) or not isinstance(encoded, str):
        raise ValueError("arquivo inválido")
    source_name = filename.replace("\\", "/").split("/")[-1].strip()
    extension = Path(source_name).suffix.lower()
    if not source_name or len(source_name) > 200 or extension not in ALLOWED:
        raise ValueError("escolha um arquivo PDF, DOCX ou TXT")
    name = str(name).strip() or Path(source_name).stem
    if not name or len(name) > 160:
        raise ValueError("nome do material deve ter 1 a 160 caracteres")
    if len(encoded) > 6_700_000:
        raise ValueError("material excede 5 MB")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("arquivo codificado incorretamente") from error
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValueError("material deve ter até 5 MB")
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise ValueError("arquivo PDF inválido")
    if extension == ".docx" and not content.startswith(b"PK"):
        raise ValueError("arquivo DOCX inválido")

    try:
        chunks = {".pdf": _extract_pdf, ".docx": _extract_docx, ".txt": _extract_txt}[extension](content)
        if sum(len(body) for _, body in chunks) > MAX_TEXT_CHARS:
            raise ValueError("texto extraído excede 1 milhão de caracteres")
        status, error = ("ready", "") if chunks else ("no_text", "Nenhum texto extraível. PDF digitalizado requer OCR, indisponível nesta versão." if extension == ".pdf" else "Nenhum texto extraível no arquivo.")
    except Exception as failure:
        status, error, chunks = "error", str(failure)[:300] or "falha na extração", []

    folder = database.path.parent / "materials"
    folder.mkdir(parents=True, exist_ok=True)
    stored_name = uuid.uuid4().hex + extension
    target, pending = folder / stored_name, folder / (stored_name + ".tmp")
    try:
        pending.write_bytes(content)
        pending.replace(target)
        return database.add_material(subject_id, name, source_name, ALLOWED[extension],
                                     stored_name, len(content), hashlib.sha256(content).hexdigest(),
                                     chunks, status, error)
    except BaseException:
        if target.exists():
            target.unlink()
        raise
    finally:
        if pending.exists():
            pending.unlink()


def original_path(database, material_id):
    material = database.get_material(material_id)
    stored_name = material["stored_name"]
    if Path(stored_name).name != stored_name or not stored_name.startswith(material_id + "."):
        raise RuntimeError("nome de arquivo do material inválido")
    path = database.path.parent / "materials" / stored_name
    if not path.is_file() or path.resolve().parent != (database.path.parent / "materials").resolve():
        raise RuntimeError("original do material não encontrado")
    return material, path


def remove_material(database, material_id):
    material, path = original_path(database, material_id)
    tombstone = path.with_name(path.name + ".deleting")
    if tombstone.exists():
        raise RuntimeError("remoção do material já em andamento")
    path.replace(tombstone)
    try:
        database.delete_material_record(material_id)
    except BaseException:
        tombstone.replace(path)
        raise
    tombstone.unlink()
    return {"removed": material_id, "notes_preserved": True}
