"""Fluxo real do frontend em Edge quando Playwright está disponível para QA local."""

import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from dashboard.app import make_server
from storage.database import Database
from utils.config import load_config, save_config

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:
    expect = sync_playwright = None


EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


@unittest.skipUnless(sync_playwright and EDGE.exists(), "QA visual requer Playwright e Microsoft Edge")
class BrowserFlowCase(unittest.TestCase):
    def test_study_flow_navigation_reopen_and_note_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Database(Path(folder) / "ritmo.db")
            database.initialize()
            config_path = Path(folder) / "config.json"
            save_config(load_config(), config_path)

            def start_server():
                server = make_server(database, 0, config_path=config_path)
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                return server, thread

            server, thread = start_server()
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(executable_path=str(EDGE), headless=True)
                    page = browser.new_page(viewport={"width": 1366, "height": 800})
                    page.set_default_timeout(8000)
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(f"http://127.0.0.1:{server.server_port}/")
                    expect(page.locator("#view-inicio")).to_be_visible()
                    expect(page.locator("#home-primary")).to_be_hidden()
                    page.locator("#home-create").click()
                    expect(page.locator("#view-plano")).to_be_visible()
                    expect(page.locator("#subject-name")).to_be_focused()
                    page.locator("#subject-name").fill("  Python QA  ")
                    page.locator("#subject-submit").click()
                    expect(page.locator("#subjects-list")).to_contain_text("Python QA")
                    subject_id = database.list_subjects()[0]["id"]

                    page.locator('nav a[data-view-target="estudar"]').click()
                    page.locator("#subject-select").select_option(subject_id)
                    posts = []
                    page.on("request", lambda request: posts.append(request) if request.method == "POST" and request.url.endswith("/api/sessions") else None)
                    page.evaluate("document.getElementById('start-btn').click(); document.getElementById('start-btn').click()")
                    expect(page.locator("#session-panel")).to_be_visible()
                    self.assertEqual(len(posts), 1)
                    self.assertEqual(len(database.list_sessions()), 1)
                    page.locator('nav a[data-view-target="plano"]').click()
                    expect(page.locator("#session-ribbon")).to_be_visible()
                    page.locator("#session-ribbon a").click()
                    expect(page.locator("#session-panel")).to_be_visible()
                    self.assertEqual(len(database.list_sessions()), 1)

                    page.locator("#quick-note-body").fill("Texto que deve permanecer")
                    def fail_note(route):
                        if route.request.method == "POST":
                            route.fulfill(status=500, content_type="application/json", body='{"error":"falha simulada"}')
                        else:
                            route.continue_()
                    page.route("**/api/notes", fail_note)
                    page.locator("#quick-note-save").click()
                    expect(page.locator("#quick-note-error")).to_contain_text("falha simulada")
                    self.assertEqual(page.locator("#quick-note-body").input_value(), "Texto que deve permanecer")
                    page.unroute("**/api/notes", fail_note)
                    page.locator("#quick-note-save").click()
                    expect(page.locator("#quick-note-body")).to_have_value("")
                    self.assertEqual(len(database.list_notes()), 1)

                    page.evaluate("document.getElementById('pause-btn').click(); document.getElementById('pause-btn').click()")
                    expect(page.locator("#session-status")).to_have_text("Em pausa")
                    expect(page.locator("#pause-btn")).to_have_text("Retomar")
                    page.locator('nav a[data-view-target="inicio"]').click()
                    expect(page.locator("#home-primary")).to_have_text("Voltar à sessão")
                    page.locator("#home-primary").click()
                    expect(page.locator("#pause-btn")).to_have_text("Retomar")
                    page.reload()
                    expect(page.locator("#pause-btn")).to_have_text("Retomar")
                    reopened_page = browser.new_page(viewport={"width": 1366, "height": 800})
                    reopened_page.goto(f"http://127.0.0.1:{server.server_port}/")
                    expect(reopened_page.locator("#pause-btn")).to_have_text("Retomar")
                    page.close(); page = reopened_page
                    page.locator("#pause-btn").click()
                    expect(page.locator("#session-status")).to_have_text("Em foco")
                    expect(page.locator("#pause-btn")).to_have_text("Pausar")
                    page.locator("#pause-btn").click()
                    expect(page.locator("#pause-btn")).to_have_text("Retomar")
                    page.locator("#finish-btn").click()
                    expect(page.locator("#session-summary")).to_be_visible()
                    completed = database.list_sessions()[0]
                    self.assertEqual(len(completed["intervals"]), 4)
                    def clock(seconds):
                        return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"
                    expect(page.locator("#summary-focus")).to_have_text(clock(completed["focus_seconds"]))
                    expect(page.locator("#summary-pause")).to_have_text(clock(completed["pause_seconds"]))
                    first_id = completed["id"]
                    page.locator('nav a[data-view-target="inicio"]').click()
                    page.locator("#home-subject").select_option(subject_id)
                    page.locator("#home-primary").click()
                    expect(page.locator("#session-panel")).to_be_visible()
                    self.assertNotEqual(database.list_sessions()[0]["id"], first_id)
                    page.locator("#finish-btn").click()
                    expect(page.locator("#session-summary")).to_be_visible()
                    page.locator('nav a[data-view-target="anotacoes"]').click()
                    page.locator("#note-subject").select_option(subject_id)
                    page.locator("#note-body").fill("Segunda anotação")
                    page.locator("#note-submit").click()
                    expect(page.locator("#notes-list")).to_contain_text("Segunda anotação")
                    page.locator("#note-search").fill("Segunda")
                    self.assertEqual(page.locator("#notes-list li").count(), 1)
                    page.locator("#note-search").fill("")
                    page.locator("#notes-list li").first.get_by_role("button", name="Editar").click()
                    page.locator(".note-edit textarea").fill("Segunda anotação revista")
                    page.locator(".note-edit button.primary").click()
                    expect(page.locator("#notes-list")).to_contain_text("Segunda anotação revista")
                    page.locator('nav a[data-view-target="materiais"]').click()
                    page.locator("#material-subject").select_option(subject_id)
                    page.locator("#material-file").set_input_files({"name": "leitura.txt", "mimeType": "text/plain",
                        "buffer": "Trecho importante para revisar.".encode()})
                    page.locator("#material-import").click()
                    expect(page.locator("#reader-title")).to_have_text("leitura")
                    expect(page.locator("#material-chunks")).to_contain_text("Trecho importante")
                    page.locator("#material-search").fill("importante")
                    expect(page.locator("#material-search-count")).to_contain_text("1 trecho encontrado")
                    page.locator("#material-chunks button").first.click()
                    page.locator("#material-note-body").fill("Nota do trecho")
                    page.locator("#material-note-save").click()
                    expect(page.locator("#material-note-form")).to_be_hidden()
                    self.assertEqual(database.list_notes()[0]["material_name"], "leitura")
                    page.locator('nav a[data-view-target="configuracoes"]').click()
                    with patch("dashboard.app.test_camera", return_value={"status": "not_found", "detail": "Nenhuma câmera encontrada."}):
                        page.locator("#camera-index").select_option("3")
                        page.locator("#camera-test").click()
                        expect(page.locator("#camera-status")).to_contain_text("Nenhuma câmera encontrada")
                    page.locator("#sensor-form details summary").click()
                    page.locator("#idle-threshold").fill("90")
                    page.locator("#save-sensors").click()
                    expect(page.locator("#message")).to_contain_text("Sensores atualizados")
                    self.assertEqual(load_config(config_path)["idle_tracker"]["threshold_seconds"], 90)
                    self.assertEqual(load_config(config_path)["presence_detector"]["camera_index"], 3)
                    page.locator("#backup-btn").click()
                    expect(page.locator("#backup-report")).to_contain_text("Backup criado")
                    self.assertEqual(len(list((Path(folder) / "backups").glob("*.zip"))), 1)
                    page.on("dialog", lambda dialog: dialog.accept())
                    page.locator("#legacy-file").set_input_files({"name": "old.csv", "mimeType": "text/csv",
                        "buffer": b"2025-11-16,11:11:40,Uma janela,code.exe\n"})
                    page.locator("#import-btn").click()
                    expect(page.locator("#import-report")).to_contain_text("1 linhas aceitas")
                    page.locator('nav a[data-view-target="evolucao"]').click()
                    expect(page.locator("#sessions-list")).to_contain_text("Python QA")
                    self.assertFalse(errors, errors)

                    shots = os.environ.get("RITMO_QA_SCREENSHOTS")
                    for width, height, label in ((1366, 800, "notebook"), (1920, 1080, "wide"), (390, 844, "mobile")):
                        page.set_viewport_size({"width": width, "height": height})
                        for view in ("inicio", "estudar", "plano", "materiais", "anotacoes", "evolucao", "configuracoes"):
                            page.locator(f'nav a[data-view-target="{view}"]').click()
                            expect(page.locator("#view-" + view)).to_be_visible()
                            self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= innerWidth"),
                                            f"rolagem horizontal em {view} / {width}px")
                            if shots:
                                Path(shots).mkdir(parents=True, exist_ok=True)
                                page.screenshot(path=str(Path(shots) / f"ritmo-{label}-{view}.png"), full_page=True)
                    page.locator('nav a[data-view-target="materiais"]').click()
                    page.locator("#material-remove").click()
                    expect(page.locator("#reader-title")).to_have_text("Escolha um material")
                    self.assertEqual(len(database.list_materials()), 0)
                    self.assertEqual(len(database.list_notes()), 3)
                    page.locator('nav a[data-view-target="plano"]').click()
                    page.locator("#subjects-list li").first.get_by_role("button", name="Renomear").click()
                    page.locator(".row-edit input").fill("Python QA revisada")
                    page.locator(".row-edit button.primary").click()
                    expect(page.locator("#subjects-list")).to_contain_text("Python QA revisada")
                    page.locator("#subjects-list li").first.get_by_role("button", name="Arquivar").click()
                    expect(page.locator("#subjects-list")).not_to_contain_text("Python QA revisada")
                    page.locator("details.archive summary").click()
                    page.locator("#archived-list li").first.get_by_role("button", name="Restaurar").click()
                    expect(page.locator("#subjects-list")).to_contain_text("Python QA revisada")
                    page.locator('nav a[data-view-target="evolucao"]').click()
                    expect(page.locator("#view-evolucao")).to_be_visible()
                    page.evaluate("async () => { await uiSave; }")
                    self.assertEqual(database.get_ui_state()["view"], "evolucao")
                    self.assertFalse(errors, errors)
                    browser.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

            server, thread = start_server()
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(executable_path=str(EDGE), headless=True)
                    page = browser.new_page()
                    page.goto(f"http://127.0.0.1:{server.server_port}/")
                    expect(page.locator("#view-evolucao")).to_be_visible()
                    self.assertEqual(len(database.list_notes()), 3)
                    self.assertEqual(database.list_sessions()[0]["status"], "complete")
                    browser.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
