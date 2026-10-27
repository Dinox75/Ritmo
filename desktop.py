"""Janela Windows do Ritmo, com encerramento conjunto de HTTP e sensores."""

import argparse
import ctypes
import json
import logging
import os
import shutil
import threading
import urllib.request
import webbrowser
from pathlib import Path

from dashboard.app import make_server
from main import SensorAgent
from storage.database import Database
from utils.config import DATA_DIR, LOCAL_CONFIG, LOG_FILE, MIGRATION_DISABLED, load_config, migrate_for_desktop
from utils.logger import configure_logging


class DesktopApp:
    def __init__(self):
        self.database = Database()
        self.agent = SensorAgent(self.database)
        self.server = None
        self.server_thread = None
        self.window = None
        self.fallback_root = None
        self._closed = False
        self.erase_requested = False
        self._lock = threading.Lock()

    def start_backend(self):
        migrated = migrate_for_desktop()
        if migrated:
            logging.info("Dados anteriores copiados: %s", ", ".join(migrated))
        self.database.initialize()
        self.agent.start(load_config())
        try:
            self.server = make_server(self.database, 0, agent=self.agent,
                                      on_quit=self.request_close, on_erase=self.request_erase)
            self.server_thread = threading.Thread(target=self.server.serve_forever,
                                                  name="ritmo_http", daemon=True)
            self.server_thread.start()
            url = f"http://127.0.0.1:{self.server.server_port}"
            # Confirma que a página e a API estão disponíveis antes de mostrar a janela.
            with urllib.request.urlopen(url + "/api/app/status", timeout=5) as response:
                if not json.load(response)["ready"]:
                    raise RuntimeError("servidor local não respondeu")
            with urllib.request.urlopen(url + "/", timeout=5) as response:
                if response.status != 200:
                    raise RuntimeError("interface local não respondeu")
            for route in ("/app.js", "/tutor.js", "/desktop.css", "/ux.css", "/api/config",
                          "/api/diagnostics", "/api/materials", "/api/tutor/config"):
                with urllib.request.urlopen(url + route, timeout=5) as response:
                    if response.status != 200 or not response.read(1):
                        raise RuntimeError(f"recurso local indisponível: {route}")
            logging.info("Interface local pronta na porta %s", self.server.server_port)
            return url
        except BaseException:
            self.close()
            raise

    def request_close(self):
        if self.window is not None:
            try:
                self.window.destroy()
                return
            except Exception:
                logging.exception("Não foi possível fechar a janela")
        if self.fallback_root is not None:
            self.fallback_root.after(0, self.fallback_root.destroy)
        if self.server is not None:
            self.server.shutdown()

    def request_erase(self):
        self.erase_requested = True
        self.request_close()

    def show(self, url):
        try:
            import webview
            window = webview.create_window("Ritmo · estudo pessoal", url,
                                           width=1440, height=900, min_size=(760, 560),
                                           background_color="#f5f3eb")
            self.window = window
            webview.start(gui="edgechromium", private_mode=True,
                          storage_path=str(DATA_DIR / "webview"))
        except Exception:
            logging.exception("WebView2 indisponível; abrindo no navegador")
            self.window = None
            self._browser_fallback(url)
        finally:
            self.close()

    def _browser_fallback(self, url):
        import tkinter as tk
        from tkinter import ttk

        webbrowser.open(url)
        root = tk.Tk()
        self.fallback_root = root
        root.title("Ritmo · controle")
        root.geometry("430x220")
        root.resizable(False, False)
        root.configure(bg="#f5f3eb")
        ttk.Label(root, text="Ritmo está aberto no navegador.",
                  font=("Segoe UI", 13, "bold")).pack(pady=(26, 10))
        ttk.Label(root, text="Mantenha esta janela aberta durante o estudo.\n"
                  "Fechá-la encerra o servidor e os sensores.", justify="center").pack()
        buttons = ttk.Frame(root)
        buttons.pack(pady=19)
        ttk.Button(buttons, text="Abrir interface", command=lambda: webbrowser.open(url)).pack(side="left", padx=5)
        ttk.Button(buttons, text="Diagnóstico", command=lambda: os.startfile(LOG_FILE)).pack(side="left", padx=5)
        ttk.Button(buttons, text="Encerrar", command=root.destroy).pack(side="left", padx=5)
        root.mainloop()
        self.fallback_root = None

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            if self.server_thread and self.server_thread is not threading.current_thread():
                self.server_thread.join(timeout=5)
            self.server.tutor_runtime.stop()
        self.agent.stop()
        logging.info("Ritmo encerrado; porta e sensores liberados")

    def erase_data(self):
        """Remove os dados usados pelo app após fechar HTTP, sensores e WebView2."""
        self.close()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        MIGRATION_DISABLED.write_text("1\n", encoding="ascii")
        logging.shutdown()
        for path in (self.database.path, self.database.path.with_name(self.database.path.name + "-wal"),
                     self.database.path.with_name(self.database.path.name + "-shm"),
                     LOCAL_CONFIG, LOG_FILE, DATA_DIR / "tutor-key.dpapi"):
            if path.is_file():
                path.unlink()
        for folder in (DATA_DIR / "webview", DATA_DIR / "backups", DATA_DIR / "materials"):
            if folder.exists():
                resolved = folder.resolve()
                if resolved.parent != DATA_DIR.resolve():
                    raise RuntimeError("pasta fora dos dados do Ritmo")
                shutil.rmtree(folder)


def _single_instance():
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, "Local\\RitmoDesktopUi")
    if not handle:
        raise OSError("não foi possível criar controle de instância")
    if kernel32.GetLastError() == 183:
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        return None
    return handle


def _show_startup_error(error):
    text = (f"O Ritmo não conseguiu iniciar.\n\n{type(error).__name__}: {error}\n\n"
            f"Diagnóstico: {LOG_FILE}\n\nDeseja abrir o arquivo de diagnóstico?")
    choice = ctypes.windll.user32.MessageBoxW(None, text, "Ritmo · erro de inicialização", 0x24)
    if choice == 6 and LOG_FILE.exists():
        os.startfile(LOG_FILE)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--smoke-report", type=Path)
    args = parser.parse_args(argv)
    configure_logging()
    mutex = None
    app = None
    try:
        mutex = _single_instance()
        if mutex is None:
            ctypes.windll.user32.MessageBoxW(None, "O Ritmo já está aberto.", "Ritmo", 0x40)
            return 0
        app = DesktopApp()
        url = app.start_backend()
        if args.smoke_test:
            # Carregamento tardio dos sensores deve funcionar no pacote instalado.
            import cv2
            import mediapipe
            import pygetwindow
            import psutil
            import win32process
            import pypdf
            import comtypes
            from pygrabber.dshow_graph import FilterGraph
            from monitor.cameras import camera_options
            from cvzone.FaceDetectionModule import FaceDetector
            from tutor.service import GUIDE
            from local_ai.installer import manifest
            from local_ai.knowledge import catalog
            if not GUIDE.is_file() or not GUIDE.read_text(encoding="utf-8").strip():
                raise RuntimeError("guia pedagógico não incluído no pacote")
            if not manifest()["models"] or not catalog()["pedagogy"]:
                raise RuntimeError("catálogo local do tutor não incluído no pacote")
            camera_options()
            report = {"ready": True, "port": app.server.server_port,
                      "data_dir": str(DATA_DIR), "pid": os.getpid()}
            app.close()
            if args.smoke_report:
                args.smoke_report.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
            return 0
        app.show(url)
        if app.erase_requested:
            app.erase_data()
            ctypes.windll.user32.MessageBoxW(None,
                "Dados do aplicativo removidos. Uma cópia antiga no checkout WorkWatch, se existir, foi preservada.",
                "Ritmo · dados removidos", 0x40)
        return 0
    except Exception as error:
        logging.exception("Falha de inicialização do Ritmo")
        if app is not None:
            app.close()
        if args.smoke_report:
            args.smoke_report.write_text(json.dumps({"ready": False, "error": str(error)},
                                                   ensure_ascii=False), encoding="utf-8")
        else:
            _show_startup_error(error)
        return 1
    finally:
        if mutex is not None:
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(mutex))


if __name__ == "__main__":
    raise SystemExit(main())
