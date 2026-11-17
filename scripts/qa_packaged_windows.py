"""Exercita a instalação real com um banco temporário, sem dados pessoais."""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import closing
from pathlib import Path

import psutil
from playwright.sync_api import expect, sync_playwright


EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def launch(executable, folder):
    environment = os.environ.copy()
    environment["LOCALAPPDATA"] = str(folder)
    # QA-only CDP lets the test reuse the credential already granted to the
    # real native window, in memory. Never expose an unauthenticated API bypass.
    existing_debug = environment.get('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', '')
    import re
    match = re.search(r'--remote-debugging-port=(\d+)', existing_debug)
    if match:
        debug_port = int(match.group(1))
    else:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); debug_port = sock.getsockname()[1]
        environment['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = existing_debug + f' --remote-debugging-port={debug_port} --remote-debugging-address=127.0.0.1'
    process = subprocess.Popen([str(executable)], env=environment)
    process.qa_debug_port = debug_port
    process.qa_data_dir = Path(folder) / 'Ritmo'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 90
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Ritmo encerrou durante a inicialização: {process.returncode}")
            for connection in psutil.net_connections(kind="tcp"):
                # Some Windows/psutil combinations report a listening socket as NONE.
                # The HTTP readiness probe below confirms the endpoint itself.
                if connection.pid != process.pid or not connection.laddr:
                    continue
                port = connection.laddr.port
                try:
                    with opener.open(f"http://127.0.0.1:{port}/api/app/status", timeout=1) as response:
                        if response.status == 200:
                            time.sleep(4)
                            if process.poll() is None:
                                return process, port
                except (OSError, TimeoutError):
                    pass
            time.sleep(0.3)
        raise TimeoutError("Ritmo não abriu o servidor local em 90 segundos")
    except Exception:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
        raise


def authorize(page, process, port):
    """Copy native-window session to QA browser; secrets stay in process memory."""
    deadline = time.monotonic() + 30
    native = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('O executável encerrou antes de autorizar a janela nativa')
        try:
            native = page.context.browser.browser_type.connect_over_cdp(f'http://127.0.0.1:{process.qa_debug_port}', timeout=2000)
            break
        except Exception:
            time.sleep(.2)
    if native is None:
        log = process.qa_data_dir / 'ritmo.log'
        if log.is_file():
            import re
            tail = log.read_text(encoding='utf8',errors='replace')[-6000:]
            print('Diagnóstico sintético de WebView2:', re.sub(r'[A-Za-z0-9_-]{24,}', '<redacted>', tail), flush=True)
        raise RuntimeError('WebView2 não disponibilizou CDP para o QA nesta máquina. Verifique WebView2/.NET e o diagnóstico da instância temporária.')
    while time.monotonic() < deadline:
        cookies = []
        for context in native.contexts:
            for window in context.pages:
                if not window.url.startswith(f'http://127.0.0.1:{port}/'):
                    continue
                # WebView2 can return an empty Storage.getCookies response for
                # its private profile. Network.getCookies is scoped to the page.
                cdp = context.new_cdp_session(window)
                try:
                    actual = cdp.send('Network.getCookies', {'urls':[f'http://127.0.0.1:{port}/']})['cookies']
                    cookies.extend({k:v for k,v in cookie.items() if k in ('name','value','domain','path','expires','httpOnly','secure','sameSite')}
                                   for cookie in actual if cookie['name']=='ritmo_session')
                finally:
                    cdp.detach()
        if cookies:
            page.context.add_cookies(cookies)
            return
        time.sleep(.1)
    raise RuntimeError('A janela nativa não autorizou a sessão de QA')


def quit_and_verify(page, process, port):
    page.locator("#quit-btn").click()
    process.wait(timeout=30)
    if process.returncode != 0:
        raise RuntimeError(f"Ritmo encerrou com código {process.returncode}")
    # Windows may leave pid=0 LISTEN/TIME_WAIT entries after close. An exclusive
    # bind distinguishes those stale records from a port still owned by a process.
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind(("127.0.0.1", port))
        except OSError as error:
            raise RuntimeError(f"Porta {port} continuou ocupada após Sair") from error


def main():
    executable = Path(sys.argv[1]).resolve()
    if not executable.is_file() or not EDGE.is_file():
        raise RuntimeError("Executável instalado ou Microsoft Edge indisponível")
    with tempfile.TemporaryDirectory(prefix="ritmo-package-qa-", ignore_cleanup_errors=True) as folder_name:
        folder = Path(folder_name)
        data = folder / "Ritmo"
        data.mkdir()
        (data / ".migration_disabled").write_text("1\n", encoding="ascii")
        config = json.loads((Path(__file__).resolve().parents[1] / "config" / "config.json").read_text(encoding="utf-8"))
        config["tutor"]["model_root"] = str(folder / "uninstalled-models")
        (data / "config.json").write_text(json.dumps(config), encoding="utf-8")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=str(EDGE), headless=True)
            process = None
            try:
                process, port = launch(executable, folder)
                page = browser.new_page(viewport={"width": 1366, "height": 800})
                page.set_default_timeout(10000)
                authorize(page, process, port)
                page.goto(f"http://127.0.0.1:{port}/")
                try:
                    expect(page.locator("#view-inicio")).to_be_visible(timeout=4000)
                except AssertionError:
                    retry = page.locator("#app-loading button")
                    if not retry.is_visible():
                        raise
                    retry.click()
                expect(page.locator("#view-inicio")).to_be_visible()
                page.locator('nav a[data-view-target="plano"]').click()
                page.locator("#subject-name").fill("Materia do teste instalado")
                page.locator("#subject-submit").click()
                try:
                    expect(page.locator("#subjects-list")).to_contain_text("Materia do teste instalado")
                except AssertionError:
                    print("Falha ao criar matéria:", page.locator("#subject-error").inner_text(),
                          page.locator("#message").inner_text(), flush=True)
                    raise
                page.locator('nav a[data-view-target="estudar"]').click()
                page.locator("#subject-select").select_option(index=1)
                page.locator("#start-btn").click()
                expect(page.locator("#session-panel")).to_be_visible()
                try:
                    page.wait_for_function("""async () => {
                      const id = document.querySelector('#tutor-thread').value;
                      if (!id) return false;
                      const sessions = await (await fetch('/api/sessions')).json();
                      const active = sessions.find(item => item.status !== 'complete');
                      const thread = await (await fetch('/api/tutor/threads/' + id)).json();
                      return active && thread.session_id === active.id;
                    }""", polling=250)
                except Exception:
                    print("Tutor no pacote:", page.locator("#tutor-error").inner_text(),
                          page.locator("#tutor-context").inner_text(),
                          page.locator("#tutor-subject").input_value(),
                          page.locator("#tutor-thread").inner_text(), flush=True)
                    raise
                session_thread = page.evaluate("""async () => {
                  const sessions = await (await fetch('/api/sessions')).json();
                  const id = document.querySelector('#tutor-thread').value;
                  const thread = await (await fetch('/api/tutor/threads/' + id)).json();
                  return {session: sessions.find(item => item.status !== 'complete')?.id,
                          linked: thread.session_id};
                }""")
                if session_thread["session"] != session_thread["linked"]:
                    raise RuntimeError(f"Conversa não vinculada à sessão ativa: {session_thread}")
                expect(page.locator("#tutor-availability")).to_contain_text("não instalado")
                page.locator("#tutor-draft").fill("Pergunta sem modelo no pacote")
                page.locator("#tutor-send").click()
                expect(page.locator("#tutor-error")).to_contain_text("Instale o modelo")
                expect(page.locator("#tutor-draft")).to_have_value("Pergunta sem modelo no pacote")
                expect(page.locator("#tutor-retry")).to_be_visible()
                page.locator("#memory-topic").fill("Condição E")
                page.locator("#memory-evidence").fill("Preciso comparar saldo")
                page.locator("#memory-save").click()
                expect(page.locator("#memory-list")).to_contain_text("Condição E")
                page.locator("#quick-note-body").fill("Nota criada no pacote")
                page.locator("#quick-note-save").click()
                expect(page.locator("#quick-note-body")).to_have_value("")
                page.locator('nav a[data-view-target="materiais"]').click()
                page.locator("#material-subject").select_option(index=1)
                page.locator("#material-file").set_input_files({
                    "name": "leitura.txt", "mimeType": "text/plain",
                    "buffer": "Trecho importante do pacote instalado.".encode("utf-8")})
                page.locator("#material-import").click()
                expect(page.locator("#material-chunks")).to_contain_text("Trecho importante")
                page.locator("#material-search").fill("importante")
                expect(page.locator("#material-search-count")).to_contain_text("1 trecho encontrado")
                page.locator("#material-chunks button").first.click()
                page.locator("#material-note-body").fill("Nota vinculada do pacote")
                page.locator("#material-note-save").click()
                expect(page.locator("#material-note-form")).to_be_hidden()
                original = page.evaluate("async () => (await (await fetch(document.getElementById('material-original').href)).text())")
                if original != "Trecho importante do pacote instalado.":
                    raise RuntimeError("Download do material original não preservou os bytes")
                page.locator('nav a[data-view-target="estudar"]').click()
                page.locator("#pause-btn").click()
                expect(page.locator("#session-status")).to_have_text("Em pausa")
                expect(page.locator("#pause-btn")).to_have_text("Retomar")
                page.wait_for_function("async () => (await (await fetch('/api/ui-state')).json()).view === 'estudar'")
                quit_and_verify(page, process, port)
                page.close()
                process = None

                process, reopened_port = launch(executable, folder)
                page = browser.new_page()
                authorize(page, process, reopened_port)
                page.goto(f"http://127.0.0.1:{reopened_port}/")
                expect(page.locator("#view-estudar")).to_be_visible()
                expect(page.locator("#session-status")).to_have_text("Em pausa")
                expect(page.locator("#pause-btn")).to_have_text("Retomar")
                page.locator("#pause-btn").click()
                expect(page.locator("#session-status")).to_have_text("Em foco")
                page.locator("#pause-btn").click()
                expect(page.locator("#pause-btn")).to_have_text("Retomar")
                page.locator("#finish-btn").click()
                expect(page.locator("#session-summary")).to_be_visible()
                page.locator('nav a[data-view-target="anotacoes"]').click()
                expect(page.locator("#notes-list")).to_contain_text("Nota criada no pacote")
                expect(page.locator("#notes-list")).to_contain_text("Nota vinculada do pacote")
                page.locator('nav a[data-view-target="materiais"]').click()
                expect(page.locator("#materials-list")).to_contain_text("leitura")
                page.locator('nav a[data-view-target="evolucao"]').click()
                expect(page.locator("#sessions-list")).to_contain_text("Materia do teste instalado")
                page.locator('nav a[data-view-target="configuracoes"]').click()
                page.locator("#backup-btn").click()
                expect(page.locator("#backup-report")).to_contain_text("Backup criado")
                quit_and_verify(page, process, reopened_port)
                page.close()
                process = None
                with closing(sqlite3.connect(data / "ritmo.db")) as connection:
                    intervals = connection.execute("SELECT kind FROM session_intervals ORDER BY started_at").fetchall()
                    if [row[0] for row in intervals] != ["focus", "pause", "focus", "pause"]:
                        raise RuntimeError(f"Intervalos inesperados após reabertura: {intervals}")
                if len(list((data / "backups").glob("*.zip"))) != 1:
                    raise RuntimeError("Backup ZIP do pacote não foi criado")
                print("Pacote instalado: pausa na reabertura, materiais, notas, backup e porta liberada.")
            finally:
                browser.close()
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


if __name__ == "__main__":
    main()
