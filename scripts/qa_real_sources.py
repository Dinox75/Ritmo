"""Ensaio sintético de comparação com o Qwen3 local; nenhum dado pessoal."""

import base64
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from local_ai.runtime import LocalRuntime
from storage.database import Database
from storage.materials import import_material
from storage.tutor_store import TutorStore
from tutor.external import ExternalSearch
from tutor.service import TutorService
from utils.config import load_config, save_config


def main(model_root, report_path):
    with tempfile.TemporaryDirectory(prefix="ritmo-real-sources-") as folder:
        root = Path(folder)
        db = Database(root / "ritmo.db"); db.initialize()
        subject = db.create_subject("Lógica sintética")
        material = import_material(db, subject["id"], "", "regra.txt",
                                   base64.b64encode("Retirada permitida se quantidade > 0 E quantidade <= saldo. Com saldo 15, retirada 18 é recusada.".encode()).decode())
        store = TutorStore(db); thread = store.create_thread(subject["id"])
        store.set_materials(thread["id"], [material["id"]])
        fake = ExternalSearch(lambda query: [{"title": "Fonte A (simulada)",
            "url": "https://pt.wikipedia.org/wiki/Conjun%C3%A7%C3%A3o_l%C3%B3gica",
            "excerpt": "Afirmação sintética para teste: retirada 18 com saldo 15 é permitida.",
            "provider": "Fonte simulada, não verificada", "accessed_at": "2026-10-28T00:00:00+00:00",
            "license": "texto sintético"}])
        source_ids = [item["id"] for item in fake.search("consulta sintética", True)["results"]]
        config_path = root / "config.json"
        config = load_config(); config["tutor"]["model"] = "qwen3-4b-q4_k_m"
        config["tutor"]["model_root"] = str(model_root)
        save_config(config, config_path)
        runtime = LocalRuntime(model_root)
        try:
            start = time.monotonic()
            answer = TutorService(db, config_path=config_path, runtime=runtime, external=fake).send(
                thread["id"], "real-sources-synthetic-1",
                "Com saldo 15, posso retirar 18? Compare a regra do material com a fonte externa selecionada.",
                source_ids)["messages"][-1]
            duration = round(time.monotonic() - start, 2)
            report = {"model": "qwen3-4b-q4_k_m", "duration_seconds": duration,
                      "answer": answer["body"], "basis": answer["basis"],
                      "material_source_count": len(answer["sources"]),
                      "external_source_count": len(answer["external_sources"])}
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False))
        finally:
            runtime.stop()


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
