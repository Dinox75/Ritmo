"""Referências e pesquisa opcional no executável, usando dados descartáveis."""

import argparse
import base64
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import expect, sync_playwright

from qa_packaged_windows import EDGE, launch, quit_and_verify
from storage.database import Database
from storage.materials import import_material
from storage.tutor_store import TutorStore


def run(executable):
    report = {"checks": [], "external": {}}
    with tempfile.TemporaryDirectory(prefix="ritmo-sources-package-", ignore_cleanup_errors=True) as name:
        root = Path(name)
        data = root / "Ritmo"; data.mkdir()
        (data / ".migration_disabled").write_text("1\n", encoding="ascii")
        config = json.loads((Path(__file__).resolve().parents[1] / "config" / "config.json").read_text(encoding="utf-8"))
        config["tutor"]["model_root"] = str(root / "models-not-installed")
        (data / "config.json").write_text(json.dumps(config), encoding="utf-8")
        db = Database(data / "ritmo.db"); db.initialize()
        subject = db.create_subject("Matéria sintética")
        content = "Saldo 15.\nA retirada 18 excede o saldo.\nSaldo 15 aparece outra vez."
        material = import_material(db, subject["id"], "", "regra.txt",
                                   base64.b64encode(content.encode()).decode())
        session = db.start_session(subject["id"])
        store = TutorStore(db)
        thread = store.create_thread(subject["id"], session["id"])
        store.set_materials(thread["id"], [material["id"]])
        message = store.begin_message(thread["id"], "package-citation-1", "Explique retirada 18")
        source = {"material_id": material["id"], "chunk_id": material["chunks"][0]["id"],
                  "material_name": "regra", "locator": material["chunks"][0]["locator"],
                  "excerpt": "A retirada 18 excede o saldo."}
        store.complete_message(message, "A retirada 18 excede o saldo [1].", "materials", [source], "duvida")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=str(EDGE), headless=True)
            process = None
            try:
                process, port = launch(executable, root)
                page = browser.new_page(viewport={"width": 1366, "height": 850})
                page.goto(f"http://127.0.0.1:{port}/")
                page.locator('nav a[data-view-target="estudar"]').click()
                pause = page.locator("#pause-btn")
                expect(pause).to_have_attribute("aria-label", "Pausar sessão")
                pause.focus(); page.keyboard.press("Enter")
                expect(pause).to_have_attribute("aria-label", "Retomar sessão")
                expect(page.locator("#session-status")).to_have_text("Em pausa")
                pause.focus(); page.keyboard.press("Enter")
                expect(pause).to_have_attribute("aria-label", "Pausar sessão")
                report["checks"].append("pausa e retomada por teclado com rótulos acessíveis")
                expect(page.locator("#tutor-history .tutor-sources a")).to_be_visible()
                page.locator("#tutor-history .tutor-sources a").focus(); page.keyboard.press("Enter")
                expect(page.locator("#material-chunks mark.citation-highlight")).to_contain_text("retirada 18")
                report["checks"].append("referência abre e destaca excerto único")
                page.evaluate("() => openMaterial(currentMaterial.id, currentMaterial.chunks[0].id, 'Saldo 15')")
                expect(page.locator("#reader-error")).to_contain_text("Não foi possível identificar")
                assert page.locator("#material-chunks mark.citation-highlight").count() == 0
                report["checks"].append("trecho ambíguo abre bloco com aviso, sem destaque enganoso")
                page.evaluate("() => openMaterial(currentMaterial.id, currentMaterial.chunks[0].id, 'trecho ausente')")
                expect(page.locator("#reader-error")).to_contain_text("Não foi possível identificar")
                page.locator("#material-search").fill("retirada")
                expect(page.locator("#material-chunks mark.current-match")).to_be_visible()
                page.locator("#material-search").fill("")
                page.evaluate("""() => {
                    const node = document.querySelector('#material-chunks .material-chunk p').firstChild;
                    const start = node.textContent.indexOf('retirada 18');
                    const range = document.createRange(); range.setStart(node, start); range.setEnd(node, start + 11);
                    const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
                }""")
                page.locator("#material-chunks .material-chunk button").first.click()
                expect(page.locator("#material-quote")).to_contain_text("retirada 18")
                page.locator("#material-note-body").fill("Nota sintética")
                page.locator("#material-note-save").click()
                assert any(item["body"] == "Nota sintética" for item in db.list_notes())
                report["checks"].append("busca, seleção e nota funcionam depois da referência")
                page.locator('nav a[data-view-target="estudar"]').click()
                page.locator("#external-research summary").click()
                outgoing = []
                page.on("request", lambda req: outgoing.append(req.post_data_json) if req.url.endswith("/api/external/search") else None)
                page.locator("#external-query").fill("consulta ainda não enviada")
                expect(page.locator("#external-preview")).to_have_text("consulta ainda não enviada")
                assert not outgoing
                page.locator("#external-query").fill("lógica matemática")
                assert not outgoing
                page.locator("#external-submit").click()
                page.wait_for_function("document.querySelector('#external-submit').disabled === false")
                assert outgoing == [{"query": "lógica matemática", "confirmed": True}], outgoing
                report["checks"].append("pesquisa envia somente consulta revisada após clique")
                report["external"]["status"] = page.locator("#external-status").inner_text()
                results = page.locator("#external-results label").count()
                report["external"]["results"] = results
                if results:
                    assert page.locator("#external-results a[href^='https://pt.wikipedia.org/wiki/']").count() == results
                    assert "acesso:" in page.locator("#external-results small").first.inner_text()
                    report["checks"].append("fontes reais exibem link, identificação e acesso")
                else:
                    assert "indisponível" in report["external"]["status"].lower() or "Nenhum resultado" in report["external"]["status"]
                    report["checks"].append("falha/ausência externa explicada sem interromper estudo local")
                quit_and_verify(page, process, port)
                process = None
                report["checks"].append("fechamento libera a porta")
            finally:
                if process and process.poll() is None:
                    process.terminate(); process.wait(timeout=15)
                browser.close()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    result = run(args.executable.resolve())
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
