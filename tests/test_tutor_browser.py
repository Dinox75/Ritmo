"""Leitor e chat reais no Edge com provedor controlado e dados temporários."""

import base64
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from dashboard.app import make_server
from storage.database import Database
from storage.materials import import_material
from storage.tutor_store import TutorStore
from local_ai.runtime import ModelUnavailable
from utils.config import load_config, save_config

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:
    expect = sync_playwright = None


EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


@unittest.skipUnless(sync_playwright and EDGE.exists(), "QA visual requer Edge e Playwright")
class TutorBrowserCase(unittest.TestCase):
    def test_search_across_chunks_and_escaped_file_text(self):
        with tempfile.TemporaryDirectory(prefix="ritmo-tutor-chunks-") as folder:
            root = Path(folder)
            db = Database(root / "ritmo.db")
            db.initialize()
            subject = db.create_subject("Leitura")
            text = ("saldo no início\n" + "linha explicativa entre trechos\n" * 80 +
                    "saldo no final\n<img src=x onerror=\"window.__ritmoInjected=true\">")
            import_material(db, subject["id"], "", "longo.txt", base64.b64encode(text.encode()).decode())
            config = root / "config.json"
            save_config(load_config(), config)
            server = make_server(db, 0, config_path=config)
            worker = threading.Thread(target=server.serve_forever)
            worker.start()
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(executable_path=str(EDGE), headless=True)
                    page = browser.new_page()
                    page.goto(f"http://127.0.0.1:{server.server_port}/")
                    page.locator('nav a[data-view-target="materiais"]').click()
                    page.locator("#materials-list button").first.click()
                    expect(page.locator("#material-chunks")).to_contain_text("saldo no final")
                    self.assertEqual(page.locator("#material-chunks img").count(), 0)
                    self.assertFalse(page.evaluate("window.__ritmoInjected === true"))
                    page.locator("#material-search").fill("SALDO")
                    expect(page.locator("#material-search-count")).to_contain_text(
                        "2 trechos encontrados · 2 ocorrências")
                    chunks = page.locator("#material-chunks .material-chunk")
                    self.assertEqual(chunks.count(), 2)
                    expect(page.locator("#material-position")).to_have_text("1 de 2")
                    first_id = page.locator("#material-chunks mark.current-match").evaluate(
                        "element => element.closest('.material-chunk').id")
                    page.locator("#material-next").click()
                    expect(page.locator("#material-position")).to_have_text("2 de 2")
                    second_id = page.locator("#material-chunks mark.current-match").evaluate(
                        "element => element.closest('.material-chunk').id")
                    self.assertNotEqual(first_id, second_id)
                    browser.close()
            finally:
                server.shutdown(); server.server_close(); worker.join()

    def test_new_session_receives_its_own_thread(self):
        with tempfile.TemporaryDirectory(prefix="ritmo-tutor-session-") as folder:
            root = Path(folder)
            db = Database(root / "ritmo.db")
            db.initialize()
            subject = db.create_subject("Lógica")
            config = root / "config.json"
            save_config(load_config(), config)
            server = make_server(db, 0, config_path=config)
            worker = threading.Thread(target=server.serve_forever)
            worker.start()
            subject_started, release_subject = threading.Event(), threading.Event()
            create_thread = TutorStore.create_thread
            def delayed_subject(store, subject_id, session_id=None):
                result = create_thread(store, subject_id, session_id)
                if session_id is None:
                    subject_started.set()
                    release_subject.wait(timeout=8)
                return result
            try:
                with patch.object(TutorStore, "create_thread", delayed_subject), sync_playwright() as playwright:
                    browser = playwright.chromium.launch(executable_path=str(EDGE), headless=True)
                    page = browser.new_page()
                    page.goto(f"http://127.0.0.1:{server.server_port}/")
                    page.locator('nav a[data-view-target="estudar"]').click()
                    expect(page.locator("#subject-select option")).to_have_count(2)
                    self.assertTrue(subject_started.wait(5))
                    page.locator("#subject-select").select_option(subject["id"])
                    page.locator("#start-btn").click()
                    expect(page.locator("#session-panel")).to_be_visible()
                    release_subject.set()
                    session_id = db.list_sessions()[0]["id"]
                    session_thread = None
                    deadline = time.monotonic() + 5
                    while not session_thread and time.monotonic() < deadline:
                        with db.connect() as connection:
                            row = connection.execute(
                                "SELECT id FROM tutor_threads WHERE session_id=?", (session_id,)).fetchone()
                        session_thread = row[0] if row else None
                        if not session_thread:
                            time.sleep(0.05)
                    self.assertIsNotNone(session_thread)
                    page.wait_for_function("id => document.querySelector('#tutor-thread').value === id",
                                           arg=session_thread)
                    page.wait_for_timeout(450)
                    self.assertEqual(page.locator("#tutor-thread").input_value(), session_thread)
                    browser.close()
            finally:
                release_subject.set()
                server.shutdown(); server.server_close(); worker.join()

    def test_material_occurrences_selection_chat_retry_and_reopen(self):
        with tempfile.TemporaryDirectory(prefix="ritmo-tutor-ui-") as folder:
            root = Path(folder)
            db = Database(root / "ritmo.db")
            db.initialize()
            subject = db.create_subject("Lógica")
            text = ("🙂 Saldo 15.\nA retirada 18 excede o saldo.\n"
                    "A ação depende do saldo.\nSaldo insuficiente impede a retirada.")
            material = import_material(db, subject["id"], "", "operadores.txt",
                                       base64.b64encode(text.encode()).decode())
            previous = db.start_session(subject["id"])
            db.create_note(subject["id"], "Nota de sessão anterior", session_id=previous["id"])
            db.finish_session(previous["id"])
            active = db.start_session(subject["id"])
            config = root / "config.json"
            save_config(load_config(), config)
            calls, fail_once = [], {"value": True}
            def controlled(model, instructions, messages):
                calls.append(messages)
                if "falha" in messages[-1]["content"] and fail_once["value"]:
                    fail_once["value"] = False
                    raise ModelUnavailable("indisponibilidade controlada")
                return ("Conceito: a retirada exige comparar o valor com o saldo. "
                        "Com 15, 18 excede o limite. Tente explicar a segunda condição. [1]")
            server = make_server(db, 0, config_path=config, tutor_provider=controlled)
            worker = threading.Thread(target=server.serve_forever)
            worker.start()
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(executable_path=str(EDGE), headless=True)
                    page = browser.new_page(viewport={"width": 1366, "height": 850})
                    page.set_default_timeout(10000)
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(f"http://127.0.0.1:{server.server_port}/")
                    expect(page.locator("#view-inicio")).to_be_visible()
                    page.locator('nav a[data-view-target="materiais"]').click()
                    page.locator("#materials-list button").first.click()
                    expect(page.locator("#material-chunks")).to_contain_text("A retirada 18")
                    self.assertIn("\n", db.get_material(material["id"])["chunks"][0]["body"])
                    page.locator("#material-search").fill("saldo")
                    expect(page.locator("#material-search-count")).to_contain_text("1 trecho encontrado · 4 ocorrências")
                    self.assertEqual(page.locator("#material-chunks mark").count(), 4)
                    expect(page.locator("#material-position")).to_have_text("1 de 4")
                    page.locator("#material-next").click()
                    expect(page.locator("#material-position")).to_have_text("2 de 4")
                    self.assertEqual(page.locator("#material-chunks mark.current-match").count(), 1)
                    page.locator("#material-prev").click()
                    expect(page.locator("#material-position")).to_have_text("1 de 4")
                    page.locator("#material-search").fill("ACAO")
                    expect(page.locator("#material-search-count")).to_contain_text("1 ocorrência")
                    expect(page.locator("#material-chunks mark")).to_have_text("ação")
                    page.locator("#material-search").fill("inexistente")
                    expect(page.locator("#material-search-count")).to_contain_text("0 ocorrências")
                    page.locator("#material-search").fill("")
                    page.evaluate("""() => {
                      const node = document.querySelector('#material-chunks .material-chunk p').firstChild;
                      const start = node.textContent.indexOf('retirada 18');
                      const range = document.createRange(); range.setStart(node, start); range.setEnd(node, start + 11);
                      const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
                    }""")
                    page.locator("#material-chunks .material-chunk button").first.click()
                    expect(page.locator("#material-quote")).to_contain_text("retirada 18")
                    self.assertNotIn("Saldo 15.", page.locator("#material-quote").inner_text())
                    page.locator("#material-note-body").fill("Nota da seleção")
                    page.locator("#material-note-save").click()
                    expect(page.locator("#material-note-form")).to_be_hidden()
                    self.assertEqual(db.list_notes()[0]["quote"], "retirada 18")
                    page.locator('nav a[data-view-target="estudar"]').click()
                    expect(page.locator("#previous-notes")).to_contain_text("Nota de sessão anterior")
                    expect(page.locator("#session-notes")).to_contain_text("Nota da seleção")
                    page.wait_for_function("document.querySelector('#tutor-thread').value.length > 0")
                    page.locator("#tutor-material-options input").first.check()
                    page.locator("#tutor-mode").select_option("aula")
                    page.locator("#tutor-draft").fill("Aula guiada: saldo 15 e retirada 18")
                    page.locator("#tutor-send").click()
                    expect(page.locator("#tutor-history .assistant")).to_contain_text("18 excede")
                    expect(page.locator("#tutor-history .tutor-sources a")).to_contain_text("operadores")
                    self.assertEqual(db.get_session(active["id"])["status"], "focus")
                    page.locator("#tutor-draft").fill("Minha tentativa: falha")
                    page.locator("#tutor-send").click()
                    expect(page.locator("#tutor-error")).to_contain_text("indisponibilidade controlada")
                    self.assertEqual(page.locator("#tutor-draft").input_value(), "Minha tentativa: falha")
                    page.locator("#tutor-retry").click()
                    expect(page.locator("#tutor-history .assistant")).to_have_count(2)
                    self.assertEqual(len(calls), 3)
                    page.locator("#tutor-history .tutor-sources a").first.click()
                    expect(page.locator("#view-materiais")).to_be_visible()
                    expect(page.locator("#material-chunks")).to_contain_text("retirada 18")
                    page.locator("#material-guided").click()
                    expect(page.locator("#view-estudar")).to_be_visible()
                    expect(page.locator("#tutor-mode")).to_have_value("aula")
                    expect(page.locator("#tutor-material-options input").first).to_be_checked()
                    expect(page.locator("#tutor-draft")).to_have_value("Quero uma aula guiada sobre operadores.")
                    shots = os.environ.get("RITMO_QA_SCREENSHOTS")
                    for width, height, label in ((1366, 850, "notebook"), (390, 844, "mobile")):
                        page.set_viewport_size({"width": width, "height": height})
                        for view in ("materiais", "estudar"):
                            page.locator(f'nav a[data-view-target="{view}"]').click()
                            expect(page.locator("#view-" + view)).to_be_visible()
                            self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= innerWidth"),
                                            f"rolagem horizontal em {view}/{width}px")
                            if shots:
                                Path(shots).mkdir(parents=True, exist_ok=True)
                                page.screenshot(path=str(Path(shots) / f"tutor-{label}-{view}.png"), full_page=True)
                    page.reload()
                    page.locator('nav a[data-view-target="estudar"]').click()
                    expect(page.locator("#tutor-history .assistant")).to_have_count(2)
                    self.assertFalse(errors, errors)
                    browser.close()
            finally:
                server.shutdown(); server.server_close(); worker.join()


if __name__ == "__main__":
    unittest.main()
