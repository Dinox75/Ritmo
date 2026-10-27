"""Importação tolerante do CSV sem cabeçalho do WorkWatch original."""

import csv
import hashlib
import io
import re
from datetime import datetime, timezone
from pathlib import Path

from storage.event_writer import EventWriter


EVENT_NAMES = {
    "EVENTO_CLASSIFICACAO": "classification",
    "EVENTO_INATIVIDADE": "idle",
    "EVENTO_PRESENCA": "presence",
    "EVENTO_MULTITAREFA": "multitask",
}


def import_legacy(database, path):
    path = Path(path).resolve()
    with path.open(newline="", encoding="utf-8-sig") as source:
        return _import_rows(database, csv.reader(source), str(path))


def import_legacy_text(database, content, source_name="arquivo.csv"):
    if not isinstance(source_name, str) or len(source_name) > 255 or not source_name.lower().endswith(".csv") or Path(source_name).name != source_name:
        raise ValueError("selecione um arquivo CSV")
    if not isinstance(content, str) or len(content.encode("utf-8")) > 5_000_000:
        raise ValueError("CSV deve ser texto de até 5 MB")
    identity = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return _import_rows(database, csv.reader(io.StringIO(content.lstrip("\ufeff"))), identity)


def _import_rows(database, rows, source_identity):
    writer = EventWriter(database)
    writer.start()
    accepted, rejected = 0, []
    try:
        for number, row in enumerate(rows, 1):
            try:
                if len(row) < 4:
                    raise ValueError("menos de quatro campos")
                date, clock = row[0].strip(), row[1].strip()
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) or not re.fullmatch(r"\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?", clock):
                    raise ValueError("data ou horário fora do formato AAAA-MM-DD,HH:MM:SS")
                local = datetime.fromisoformat(f"{date}T{clock}")
                at = local.astimezone(timezone.utc).isoformat()
                kind = row[2].strip()
                if kind in EVENT_NAMES:
                    sensor = EVENT_NAMES[kind]
                    state = row[3].strip()
                    if not state:
                        raise ValueError("estado vazio")
                    details = {"legacy": True}
                else:
                    sensor, state = "window", "changed"
                    title, program = ",".join(row[2:-1]).strip(), row[-1].strip()
                    if not title or not program:
                        raise ValueError("título ou programa vazio")
                    details = {"titulo": title, "programa": program,
                               "legacy": True}
                digest = hashlib.sha256(
                    (source_identity + "|" + str(number) + "|" + repr(row)).encode("utf-8")
                ).hexdigest()
                writer.emit(sensor, state, details, event_id=digest, at=at)
                accepted += 1
            except (ValueError, IndexError) as error:
                rejected.append({"line": number, "reason": str(error)})
        writer.flush()
    finally:
        writer.close()
    return {"rows_accepted": accepted, "rows_rejected": rejected,
            "note": "IDs determinísticos impedem duplicação ao importar novamente"}
