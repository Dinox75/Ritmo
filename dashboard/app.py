"""API HTTP local e arquivos estáticos da primeira interface Ritmo."""

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from monitor.cameras import camera_options, test_camera
from storage.database import ConflictError
from storage.legacy_import import import_legacy_text
from storage.materials import import_material, original_path, remove_material
from local_ai.manager import InstallManager
from local_ai.knowledge import catalog as knowledge_catalog
from local_ai.runtime import LocalRuntime, ModelUnavailable
from tutor.service import TutorService
from utils.config import DATA_DIR, FROZEN, LOCAL_CONFIG, LOG_FILE, load_config, save_config


WEB = Path(__file__).resolve().parents[1] / "web"
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/tutor.js": ("tutor.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/progress.css": ("progress.css", "text/css; charset=utf-8"),
    "/desktop.css": ("desktop.css", "text/css; charset=utf-8"),
    "/ux.css": ("ux.css", "text/css; charset=utf-8"),
    "/atmosphere.css": ("atmosphere.css", "text/css; charset=utf-8"),
    "/manifest.json": ("manifest.json", "application/manifest+json"),
    "/sw.js": ("sw.js", "text/javascript; charset=utf-8"),
    "/icon.svg": ("icon.svg", "image/svg+xml"),
}


def make_handler(database, agent=None, on_quit=None, on_erase=None, config_path=None,
                 tutor_provider=None, tutor_runtime=None, install_manager=None):
    tutor = TutorService(database, config_path=config_path, provider=tutor_provider, runtime=tutor_runtime)
    installer = install_manager or InstallManager()
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, data):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _body(self):
            size = int(self.headers.get("Content-Length", "0"))
            if size < 0 or size > 8_000_000:
                raise ValueError("corpo muito grande")
            data = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("objeto JSON esperado")
            return data

        def _dispatch(self):
            expected_host = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != expected_host:
                self._send(403, {"error": "acesso local inválido"})
                return
            origin = self.headers.get("Origin")
            if origin and origin != f"http://{expected_host}":
                self._send(403, {"error": "origem não permitida"})
                return
            path = urlparse(self.path).path
            parts = [part for part in path.split("/") if part]
            if self.command == "GET" and path in STATIC:
                filename, content_type = STATIC[path]
                content = (WEB / filename).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(content)
                return
            if self.command == "GET" and len(parts) == 4 and parts[:2] == ["api", "materials"] and parts[3] == "original":
                material, original = original_path(database, parts[2])
                content = original.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(material["source_name"], safe=""))
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(content)
                return
            if not parts or parts[0] != "api":
                self._send(404, {"error": "rota não encontrada"})
                return
            query = parse_qs(urlparse(self.path).query)
            if self.command == "GET":
                if parts == ["api", "subjects"]:
                    result = database.list_subjects(query.get("archived", ["0"])[0] == "1")
                elif parts == ["api", "sessions"]:
                    result = database.list_sessions()
                elif len(parts) == 3 and parts[:2] == ["api", "sessions"]:
                    result = database.get_session(parts[2])
                elif parts == ["api", "notes"]:
                    result = database.list_notes(query.get("subject_id", [None])[0])
                elif parts == ["api", "materials"]:
                    result = database.list_materials(query.get("subject_id", [None])[0])
                elif parts == ["api", "tutor", "config"]:
                    result = tutor.status()
                elif parts == ["api", "tutor", "install"]:
                    result = installer.status()
                elif parts == ["api", "tutor", "knowledge"]:
                    result = knowledge_catalog()
                elif parts == ["api", "tutor", "knowledge-updates"]:
                    result = database.list_knowledge_updates()
                elif parts == ["api", "study-memory"]:
                    result = database.list_study_memory(query.get("subject_id", [None])[0])
                elif parts == ["api", "tutor", "threads"]:
                    result = tutor.store.list_threads(query.get("subject_id", [""])[0])
                elif len(parts) == 4 and parts[:3] == ["api", "tutor", "threads"]:
                    result = tutor.store.get_thread(parts[3])
                elif len(parts) == 3 and parts[:2] == ["api", "materials"]:
                    result = database.get_material(parts[2])
                elif parts == ["api", "cameras"]:
                    result = camera_options()
                elif parts == ["api", "health"]:
                    result = database.health()
                elif parts == ["api", "progress"]:
                    result = database.progress()
                elif parts == ["api", "progress", "day"]:
                    since = query.get("since", [""])[0]
                    until = query.get("until", [""])[0]
                    start, end = datetime.fromisoformat(since), datetime.fromisoformat(until)
                    if end - start > timedelta(hours=26):
                        raise ValueError("dia informado é longo demais")
                    result = database.progress_between(start, end)
                elif parts == ["api", "ui-state"]:
                    result = database.get_ui_state()
                elif parts == ["api", "config"]:
                    result = load_config(config_path)
                elif parts == ["api", "experience"]:
                    result = load_config(config_path)["experience"]
                elif parts == ["api", "diagnostics"]:
                    events = database.list_events(20)
                    log_lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-50:] if LOG_FILE.exists() else []
                    result = {"sensors": database.health(),
                              "events": [{key: event[key] for key in ("at", "sensor", "state")}
                                         for event in events],
                              "log": log_lines, "data_dir": str(DATA_DIR),
                              "database": str(database.path), "packaged": FROZEN}
                elif parts == ["api", "app", "status"]:
                    result = {"name": "Ritmo", "ready": True, "packaged": FROZEN}
                else:
                    self._send(404, {"error": "rota não encontrada"})
                    return
                self._send(200, result)
                return
            data = self._body()
            if self.command == "POST":
                if parts == ["api", "subjects"]:
                    result = database.create_subject(data.get("name", ""))
                elif parts == ["api", "sessions"]:
                    result = database.start_session(data.get("subject_id"))
                elif len(parts) == 4 and parts[:2] == ["api", "sessions"]:
                    session_id, action = parts[2:]
                    if action == "pause":
                        result = database.pause_session(session_id)
                    elif action == "resume":
                        result = database.resume_session(session_id)
                    elif action == "finish":
                        result = database.finish_session(session_id)
                    elif action == "adjustments":
                        result = database.adjust_session(session_id, data.get("delta_seconds"),
                                                         data.get("reason", ""))
                    else:
                        self._send(404, {"error": "rota não encontrada"})
                        return
                elif parts == ["api", "notes"]:
                    result = database.create_note(data.get("subject_id"), data.get("body", ""),
                                                  session_id=data.get("session_id"),
                                                  material_id=data.get("material_id"),
                                                  chunk_id=data.get("chunk_id"),
                                                  selection_start=data.get("selection_start"),
                                                  selection_end=data.get("selection_end"))
                elif parts == ["api", "materials"]:
                    result = import_material(database, data.get("subject_id"), data.get("name", ""),
                                             data.get("filename"), data.get("content_base64"))
                elif parts == ["api", "tutor", "threads"]:
                    result = tutor.store.create_thread(data.get("subject_id"), data.get("session_id"))
                elif parts == ["api", "tutor", "install"]:
                    status = tutor.status()
                    result = installer.start(status["model"], status["model_root"])
                elif parts == ["api", "study-memory"]:
                    result = database.save_study_memory(data.get("subject_id"), data.get("topic", ""),
                                                        data.get("evidence", ""), data.get("outcome"),
                                                        exercise=data.get("exercise", ""), attempt=data.get("attempt", ""),
                                                        feedback=data.get("feedback", ""),
                                                        progress_observed=data.get("progress_observed", ""))
                elif parts == ["api", "tutor", "knowledge-updates"]:
                    result = database.add_knowledge_update(data)
                elif len(parts) == 5 and parts[:3] == ["api", "tutor", "threads"] and parts[4] == "messages":
                    result = tutor.send(parts[3], data.get("request_id"), data.get("body"))
                elif parts == ["api", "cameras", "test"]:
                    result = test_camera(data.get("index"))
                elif parts == ["api", "import-legacy"]:
                    result = import_legacy_text(database, data.get("content"), data.get("name", "arquivo.csv"))
                elif parts == ["api", "backup"]:
                    result = database.create_backup()
                elif parts == ["api", "app", "quit"]:
                    self._send(200, {"closing": True})
                    callback = on_quit or self.server.shutdown
                    threading.Thread(target=callback, name="app_quit", daemon=True).start()
                    return
                elif parts == ["api", "app", "erase"]:
                    if on_erase is None:
                        self._send(404, {"error": "apagamento disponível no aplicativo Windows"})
                        return
                    if data.get("confirmation") != "APAGAR":
                        raise ValueError("digite APAGAR para confirmar")
                    self._send(200, {"closing": True})
                    threading.Thread(target=on_erase, name="app_erase", daemon=True).start()
                    return
                elif parts == ["api", "app", "open-data-folder"]:
                    DATA_DIR.mkdir(parents=True, exist_ok=True)
                    os.startfile(DATA_DIR)
                    result = {"opened": True}
                elif parts == ["api", "app", "open-backups-folder"]:
                    folder = database.path.parent / "backups"
                    folder.mkdir(parents=True, exist_ok=True)
                    os.startfile(folder)
                    result = {"opened": True}
                else:
                    self._send(404, {"error": "rota não encontrada"})
                    return
                self._send(201, result)
                return
            if len(parts) == 3 and parts[:2] == ["api", "notes"]:
                if self.command == "PATCH":
                    self._send(200, database.update_note(parts[2], data.get("body", ""),
                                                         data.get("version")))
                    return
                if self.command == "DELETE":
                    database.delete_note(parts[2], data.get("version"))
                    self._send(200, {"deleted": True})
                    return
            if len(parts) == 3 and parts[:2] == ["api", "study-memory"]:
                if self.command == "PATCH":
                    self._send(200, database.save_study_memory(data.get("subject_id"), data.get("topic", ""),
                                                                data.get("evidence", ""), data.get("outcome"),
                                                                exercise=data.get("exercise", ""), attempt=data.get("attempt", ""),
                                                                feedback=data.get("feedback", ""),
                                                                progress_observed=data.get("progress_observed", ""),
                                                                memory_id=parts[2], version=data.get("version")))
                    return
                if self.command == "DELETE":
                    database.delete_study_memory(parts[2], data.get("version"))
                    self._send(200, {"deleted": True})
                    return
            if len(parts) == 4 and parts[:3] == ["api", "tutor", "knowledge-updates"] and self.command == "DELETE":
                database.delete_knowledge_update(parts[3])
                self._send(200, {"deleted": True})
                return
            if parts == ["api", "preferences"] and self.command == "PATCH":
                self._send(200, database.set_weekly_goal(data.get("weekly_goal_minutes")))
                return
            if parts == ["api", "ui-state"] and self.command == "PATCH":
                self._send(200, database.set_ui_state(data.get("view"), data.get("subject_id"),
                                                      data.get("revision")))
                return
            if parts == ["api", "config"] and self.command == "PATCH":
                config = save_config(data, config_path or LOCAL_CONFIG)
                if agent is not None:
                    agent.restart(config)
                self._send(200, config)
                return
            if parts == ["api", "experience"] and self.command == "PATCH":
                config = load_config(config_path)
                if set(data) - set(config["experience"]):
                    raise ValueError("opção desconhecida da experiência")
                config["experience"].update(data)
                self._send(200, save_config(config, config_path or LOCAL_CONFIG)["experience"])
                return
            if parts == ["api", "tutor", "config"] and self.command == "PATCH":
                self._send(200, tutor.configure(data))
                return
            if len(parts) == 4 and parts[:3] == ["api", "tutor", "threads"] and self.command == "PATCH":
                if "mode" in data:
                    tutor.store.set_mode(parts[3], data["mode"])
                if "material_ids" in data:
                    tutor.store.set_materials(parts[3], data["material_ids"])
                self._send(200, tutor.store.get_thread(parts[3]))
                return
            if len(parts) == 3 and parts[:2] == ["api", "subjects"] and self.command == "PATCH":
                self._send(200, database.update_subject(parts[2], name=data.get("name"),
                                                        archived=data.get("archived")))
                return
            if len(parts) == 3 and parts[:2] == ["api", "subjects"] and self.command == "DELETE":
                database.archive_subject(parts[2])
                self._send(200, {"archived": True})
                return
            if len(parts) == 3 and parts[:2] == ["api", "materials"]:
                if self.command == "PATCH":
                    self._send(200, database.rename_material(parts[2], data.get("name", "")))
                    return
                if self.command == "DELETE":
                    if data.get("confirmation") != "REMOVER":
                        raise ValueError("confirme a remoção do material")
                    self._send(200, remove_material(database, parts[2]))
                    return
            self._send(404, {"error": "rota não encontrada"})

        def do_GET(self):
            self._handle()

        def do_POST(self):
            self._handle()

        def do_PATCH(self):
            self._handle()

        def do_DELETE(self):
            self._handle()

        def _handle(self):
            try:
                self._dispatch()
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                # A janela pode fechar enquanto uma preferência pequena ainda é enviada.
                pass
            except ConflictError as error:
                self._send(409, {"error": str(error)})
            except ModelUnavailable as error:
                self._send(503, {"error": str(error)})
            except (ValueError, KeyError, TypeError, json.JSONDecodeError, sqlite3.IntegrityError) as error:
                self._send(400, {"error": str(error)})
            except Exception:
                logging.exception("Falha interna em requisição local")
                self._send(500, {"error": "falha interna; consulte Configurações → Diagnóstico"})

        def log_message(self, format, *args):
            # Evita colocar conteúdos de query string e caminhos privados no terminal.
            pass

    return Handler


def make_server(database, port=8765, *, agent=None, on_quit=None, on_erase=None, config_path=None,
                tutor_provider=None, tutor_runtime=None, install_manager=None):
    tutor_runtime = tutor_runtime or LocalRuntime(load_config(config_path)["tutor"]["model_root"])
    server = ThreadingHTTPServer(("127.0.0.1", port),
                                 make_handler(database, agent, on_quit, on_erase, config_path,
                                              tutor_provider, tutor_runtime, install_manager))
    server.tutor_runtime = tutor_runtime
    server.daemon_threads = True
    return server


def serve(database, port=8765):
    from main import SensorAgent
    agent = SensorAgent(database)
    agent.start(load_config())
    server = make_server(database, port, agent=agent)
    print(f"Ritmo disponível em http://127.0.0.1:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.tutor_runtime.stop()
        agent.stop()
