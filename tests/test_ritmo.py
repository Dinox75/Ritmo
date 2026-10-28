import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from urllib.parse import urlencode
import socket
import types
import zipfile
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from main import run_sensor
from dashboard.app import make_server
from desktop import DesktopApp
from main import SensorAgent
from monitor.multitask_analyzer import WindowSwitchAnalyzer
from monitor.presence_detector import detectar_presenca, monitorar_presenca
from monitor.window_tracker import iniciar_monitoramento
from storage.database import ConflictError, Database
from storage.event_writer import EventWriter
from storage.legacy_import import import_legacy, import_legacy_text
from utils.config import load_config, migrate_for_desktop, migrate_repo_data, save_config


class DatabaseCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "test.db")
        self.db.initialize()

    def tearDown(self):
        self.temp.cleanup()

    def test_session_pause_midnight_adjustment_and_reopen(self):
        subject = self.db.create_subject("Python")
        base = datetime(2026, 10, 21, 23, 50, tzinfo=timezone.utc)
        stamp = lambda minutes: (base + timedelta(minutes=minutes)).isoformat()
        session = self.db.start_session(subject["id"], at=stamp(0))
        self.db.pause_session(session["id"], at=stamp(15))
        with self.assertRaises(ConflictError):
            self.db.pause_session(session["id"], at=stamp(16))
        self.db.resume_session(session["id"], at=stamp(20))
        finished = self.db.finish_session(session["id"], at=stamp(30))
        self.assertEqual((finished["focus_seconds"], finished["pause_seconds"]), (1500, 300))
        corrected = self.db.adjust_session(session["id"], -120, "Interrupção não registrada")
        self.assertEqual(corrected["focus_seconds"], 1380)
        self.assertEqual(len(corrected["adjustments"]), 1)
        reopened = Database(self.db.path)
        reopened.initialize()
        self.assertEqual(reopened.get_session(session["id"])["focus_seconds"], 1380)
        progress = reopened.progress(at=stamp(31))
        self.assertEqual((progress["focus_seconds"], progress["pause_seconds"]), (1380, 300))
        self.assertEqual(progress["weekly_goal_minutes"], 480)

    def test_pause_resume_pause_finish_has_contiguous_intervals_after_reopen(self):
        subject = self.db.create_subject("Ritmo")
        base = datetime(2026, 10, 24, 20, 0, tzinfo=timezone.utc)
        at = lambda seconds: (base + timedelta(seconds=seconds)).isoformat()
        session = self.db.start_session(subject["id"], at=at(0))
        self.db.pause_session(session["id"], at=at(76))
        reopened = Database(self.db.path)
        reopened.initialize()
        self.assertEqual(reopened.get_session(session["id"], at=at(100))["status"], "pause")
        with self.assertRaises(ConflictError):
            reopened.pause_session(session["id"], at=at(90))
        reopened.resume_session(session["id"], at=at(120))
        with self.assertRaises(ConflictError):
            reopened.resume_session(session["id"], at=at(121))
        reopened.pause_session(session["id"], at=at(150))
        finished = reopened.finish_session(session["id"], at=at(180))
        self.assertEqual((finished["focus_seconds"], finished["pause_seconds"]), (106, 74))
        self.assertEqual([item["kind"] for item in finished["intervals"]],
                         ["focus", "pause", "focus", "pause"])
        self.assertTrue(all(left["ended_at"] == right["started_at"]
                            for left, right in zip(finished["intervals"], finished["intervals"][1:])))
        self.assertFalse(any(item["ended_at"] is None for item in finished["intervals"]))

    def test_upgrade_from_first_schema_keeps_data(self):
        subject = self.db.create_subject("Sistemas")
        with self.db.connect() as db:
            db.execute("DROP TABLE preferences")
            db.execute("PRAGMA user_version=1")
        self.db.initialize()
        self.assertEqual(self.db.preferences()["weekly_goal_minutes"], 480)
        self.assertEqual(self.db.list_subjects()[0]["id"], subject["id"])

    def test_ui_state_daily_progress_and_backup_survive_reopen(self):
        subject = self.db.create_subject("Python")
        with self.db.connect() as db:
            db.execute("DROP TABLE ui_state")
            db.execute("PRAGMA user_version=2")
        self.db.initialize()
        self.assertEqual(self.db.get_ui_state()["view"], "inicio")
        self.db.set_ui_state("estudar", subject["id"])
        reopened = Database(self.db.path)
        reopened.initialize()
        state = reopened.get_ui_state()
        self.assertEqual((state["view"], state["subject_id"]), ("estudar", subject["id"]))
        reopened.set_ui_state("evolucao", revision=state["revision"] + 2)
        reopened.set_ui_state("plano", revision=state["revision"] + 1)
        self.assertEqual(reopened.get_ui_state()["view"], "evolucao")
        with self.assertRaises(ValueError):
            reopened.set_ui_state("desconhecida")
        base = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
        started = reopened.start_session(subject["id"], at=base.isoformat())
        reopened.finish_session(started["id"], at=(base + timedelta(minutes=20)).isoformat())
        day = reopened.progress_between((base - timedelta(hours=12)).isoformat(),
                                        (base + timedelta(hours=12)).isoformat())
        self.assertEqual(day["focus_seconds"], 1200)
        self.assertEqual(day["completed_sessions"], 1)
        backup = reopened.create_backup()
        with zipfile.ZipFile(backup["path"]) as archive:
            restored = Path(self.temp.name) / "restored.db"
            restored.write_bytes(archive.read("database/ritmo.db"))
        copy = Database(restored)
        self.assertEqual(copy.list_subjects()[0]["name"], "Python")
        self.assertEqual(copy.get_ui_state()["view"], "evolucao")
        self.assertEqual(copy.list_sessions()[0]["focus_seconds"], 1200)

    def test_one_active_session_and_note_conflict(self):
        subject = self.db.create_subject("Dados")
        session = self.db.start_session(subject["id"])
        with self.assertRaises(ConflictError):
            self.db.start_session(subject["id"])
        note = self.db.create_note(subject["id"], "Uma ideia", session_id=session["id"])
        updated = self.db.update_note(note["id"], "Outra ideia", 1)
        self.assertEqual(updated["version"], 2)
        with self.assertRaises(ConflictError):
            self.db.update_note(note["id"], "Versão antiga", 1)
        self.assertEqual(self.db.list_notes()[0]["body"], "Outra ideia")

    def test_concurrent_events_and_sensor_failure(self):
        writer = EventWriter(self.db)
        writer.start()
        def produce(index):
            for item in range(40):
                writer.emit("window", "changed", {"titulo": f"a,b\n{index}-{item}"})
        workers = [threading.Thread(target=produce, args=(i,)) for i in range(5)]
        for worker in workers: worker.start()
        for worker in workers: worker.join()
        writer.emit("test", "once", {}, event_id="same")
        writer.emit("test", "once", {}, event_id="same")
        def broken(stop, emit):
            raise OSError("câmera indisponível")
        with patch("main.logging.exception"):
            run_sensor("test_sensor", broken, writer, threading.Event())
        writer.close()
        rows = self.db.list_events(300)
        self.assertEqual(len(rows), 201)
        self.assertTrue(any("a,b\n" in row["details"].get("titulo", "") for row in rows))
        self.assertEqual(self.db.health()[0]["status"], "failed")

    def test_legacy_import_idempotent(self):
        source = Path(self.temp.name) / "old.csv"
        source.write_text("2025-11-16,11:11:40,Título, com vírgula,code.exe\n"
                          "2025-11-16,11:12:40,EVENTO_INATIVIDADE,INATIVO\n"
                          "ruim\n", encoding="utf-8")
        report = import_legacy(self.db, source)
        self.assertEqual(report["rows_accepted"], 2)
        self.assertEqual(len(report["rows_rejected"]), 1)
        import_legacy(self.db, source)
        self.assertEqual(len(self.db.list_events()), 2)
        self.assertEqual(self.db.list_events()[1]["details"]["titulo"], "Título, com vírgula")

    def test_legacy_import_rejects_ambiguous_dates_and_accepts_spaces(self):
        report = import_legacy_text(self.db,
            " 2025-11-16 , 11:11:40 , Título , code.exe \n"
            "16/11/2025,11:12:40,Título,code.exe\n"
            "2025-13-16,11:12:40,Título,code.exe\n", "old.csv")
        self.assertEqual(report["rows_accepted"], 1)
        self.assertEqual(len(report["rows_rejected"]), 2)
        self.assertEqual(self.db.list_events()[0]["details"]["programa"], "code.exe")

    def test_import_text_and_copy_existing_data_without_overwrite(self):
        text = "2025-11-16,11:11:40,Título,code.exe\n"
        import_legacy_text(self.db, text)
        import_legacy_text(self.db, text)
        self.assertEqual(len(self.db.list_events()), 1)
        source = Path(self.temp.name) / "source"
        destination = Path(self.temp.name) / "destination"
        (source / "storage").mkdir(parents=True)
        (source / "config").mkdir()
        original = Database(source / "storage" / "ritmo.db")
        original.initialize()
        original.create_subject("Original")
        (source / "config" / "local.json").write_text("{}", encoding="utf-8")
        self.assertEqual(migrate_repo_data(source, destination), ["banco", "configuração"])
        self.assertEqual(Database(destination / "ritmo.db").list_subjects()[0]["name"], "Original")
        original.create_subject("Novo")
        self.assertEqual(migrate_repo_data(source, destination), [])
        self.assertEqual(len(Database(destination / "ritmo.db").list_subjects()), 1)

    def test_desktop_backend_releases_port(self):
        app = DesktopApp()
        app.database = self.db
        app.agent = SensorAgent(self.db)
        with patch("desktop.migrate_for_desktop", return_value=[]):
            url = app.start_backend()
        port = app.server.server_port
        with urllib.request.urlopen(url + "/api/app/status") as response:
            self.assertTrue(json.load(response)["ready"])
        app.close()
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", port))

    def test_installed_package_finds_original_checkout(self):
        source = Path(self.temp.name) / "checkout"
        source.mkdir()
        (source / "main.py").touch()
        package = Path(self.temp.name) / "installed" / "Ritmo"
        package.mkdir(parents=True)
        (package / "source_checkout.txt").write_text(str(source), encoding="utf-8")
        with patch("utils.config.FROZEN", True), \
             patch("utils.config.MIGRATION_DISABLED", Path(self.temp.name) / "no-marker"), \
             patch("utils.config.sys.executable", str(package / "Ritmo.exe")), \
             patch("utils.config.migrate_repo_data", return_value=["banco"]) as migrate:
            self.assertEqual(migrate_for_desktop(), ["banco"])
            migrate.assert_called_once_with(source)

    def test_desktop_erase_removes_only_installed_data(self):
        folder = Path(self.temp.name) / "installed-data"
        folder.mkdir()
        db = Database(folder / "ritmo.db")
        db.initialize()
        db.create_subject("Apagar")
        config = folder / "config.json"
        log = folder / "ritmo.log"
        config.write_text("{}", encoding="utf-8")
        log.write_text("erro de teste", encoding="utf-8")
        cache = folder / "webview"
        cache.mkdir()
        (cache / "cache.txt").write_text("temporário", encoding="utf-8")
        backups = folder / "backups"
        backups.mkdir()
        (backups / "copy.db").write_text("backup de teste", encoding="utf-8")
        materials = folder / "materials"
        materials.mkdir()
        (materials / "sample.txt").write_text("material de teste", encoding="utf-8")
        app = DesktopApp()
        app.database = db
        app.agent = SensorAgent(db)
        marker = folder / ".migration_disabled"
        with patch("desktop.DATA_DIR", folder), patch("desktop.LOCAL_CONFIG", config), \
             patch("desktop.LOG_FILE", log), patch("desktop.MIGRATION_DISABLED", marker), \
             patch("desktop.logging.shutdown"):
            app.erase_data()
        self.assertTrue(marker.exists())
        self.assertFalse(db.path.exists())
        self.assertFalse(config.exists())
        self.assertFalse(log.exists())
        self.assertFalse(cache.exists())
        self.assertFalse(backups.exists())
        self.assertFalse(materials.exists())
        self.assertTrue(self.db.path.exists())

    def test_http_study_flow(self):
        config_path = Path(self.temp.name) / "config.json"
        save_config(load_config(), config_path)
        class FakeAgent:
            config = None
            def restart(self, config): self.config = config
        agent = FakeAgent()
        erased = threading.Event()
        server = make_server(self.db, 0, agent=agent, on_erase=erased.set, config_path=config_path)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        def call(path, method="GET", body=None):
            payload = json.dumps(body).encode() if body is not None else None
            request = urllib.request.Request(base + path, data=payload, method=method,
                                             headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request) as response:
                return json.load(response)
        try:
            with urllib.request.urlopen(base + "/") as response:
                self.assertIn("Sua sessão", response.read().decode("utf-8"))
            with urllib.request.urlopen(base + "/app.js") as response:
                self.assertIn("renderProgress", response.read().decode("utf-8"))
            subject = call("/api/subjects", "POST", {"name": "Automação"})
            session = call("/api/sessions", "POST", {"subject_id": subject["id"]})
            note = call("/api/notes", "POST", {"subject_id": subject["id"],
                                                 "session_id": session["id"], "body": "Teste"})
            call(f"/api/sessions/{session['id']}/pause", "POST", {})
            call(f"/api/sessions/{session['id']}/resume", "POST", {})
            finished = call(f"/api/sessions/{session['id']}/finish", "POST", {})
            self.assertEqual(finished["status"], "complete")
            self.assertEqual(call("/api/notes")[0]["id"], note["id"])
            # Uma janela explícita evita depender de ajustes do relógio do Windows durante o teste.
            completed_at = datetime.fromisoformat(finished["ended_at"])
            window = urlencode({"since": (completed_at - timedelta(hours=1)).isoformat(),
                                "until": (completed_at + timedelta(hours=1)).isoformat()})
            self.assertEqual(call("/api/progress/day?" + window)["completed_sessions"], 1)
            self.assertEqual(call("/api/ui-state")["view"], "inicio")
            self.assertEqual(call("/api/ui-state", "PATCH", {"view": "evolucao", "subject_id": subject["id"],
                                                          "revision": 10})["view"], "evolucao")
            backup = call("/api/backup", "POST", {})
            self.assertTrue(Path(backup["path"]).is_file())
            self.assertEqual(call("/api/preferences", "PATCH", {"weekly_goal_minutes": 600})
                             ["weekly_goal_minutes"], 600)
            renamed = call(f"/api/subjects/{subject['id']}", "PATCH", {"name": "Python"})
            self.assertEqual(renamed["name"], "Python")
            call(f"/api/subjects/{subject['id']}", "PATCH", {"archived": True})
            self.assertEqual(call("/api/subjects"), [])
            self.assertTrue(call("/api/subjects?archived=1")[0]["archived"])
            config = call("/api/config")
            config["idle_tracker"]["threshold_seconds"] = 90
            self.assertEqual(call("/api/config", "PATCH", config)["idle_tracker"]["threshold_seconds"], 90)
            self.assertEqual(agent.config["idle_tracker"]["threshold_seconds"], 90)
            report = call("/api/import-legacy", "POST", {"name": "old.csv", "content":
                          "2025-11-16,11:11:40,Uma janela,code.exe\n"})
            self.assertEqual(report["rows_accepted"], 1)
            self.assertIn("sensors", call("/api/diagnostics"))
            with self.assertRaises(urllib.error.HTTPError) as error:
                call("/api/app/erase", "POST", {"confirmation": "não"})
            self.assertEqual(error.exception.code, 400)
            self.assertFalse(erased.is_set())
            self.assertTrue(call("/api/app/erase", "POST", {"confirmation": "APAGAR"})["closing"])
            self.assertTrue(erased.wait(2))
            request = urllib.request.Request(base + "/api/subjects", method="GET",
                                             headers={"Origin": "http://evil.example"})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            self.assertEqual(error.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class SensorRulesCase(unittest.TestCase):
    def test_switches_are_real_and_alerts_suppressed(self):
        analyzer = WindowSwitchAnalyzer(observation_seconds=60, alert_switches=3)
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertIsNone(analyzer.observe("A", base))
        self.assertIsNone(analyzer.observe("A", base + timedelta(seconds=1)))
        self.assertIsNone(analyzer.observe("B", base + timedelta(seconds=2)))
        self.assertIsNone(analyzer.observe("A", base + timedelta(seconds=3)))
        self.assertEqual(analyzer.observe("B", base + timedelta(seconds=4))["switches"], 3)
        self.assertIsNone(analyzer.observe("C", base + timedelta(seconds=5)))
        self.assertIsNone(analyzer.observe("D", base + timedelta(seconds=100)))

    def test_presence_uses_interval_and_unavailable_state(self):
        class Stop:
            def __init__(self): self.waits = []
            def is_set(self): return len(self.waits) >= 2
            def wait(self, seconds): self.waits.append(seconds)
        stop = Stop()
        events = []
        with patch("monitor.presence_detector.detectar_presenca", side_effect=["unavailable", "absent"]):
            monitorar_presenca(stop, 7, lambda *args: events.append(args))
        self.assertEqual(stop.waits, [7, 7])
        self.assertEqual([item[1] for item in events], ["unavailable", "absent"])

    def test_camera_is_released_after_failed_read(self):
        class Camera:
            released = False
            def isOpened(self): return True
            def read(self): return False, None
            def release(self): self.released = True
        camera = Camera()
        cv2 = types.ModuleType("cv2")
        cv2.CAP_DSHOW = 1
        cv2.VideoCapture = lambda *args: camera
        cvzone = types.ModuleType("cvzone")
        cvzone.__path__ = []
        faces = types.ModuleType("cvzone.FaceDetectionModule")
        faces.FaceDetector = object
        with patch.dict(sys.modules, {"cv2": cv2, "cvzone": cvzone,
                                      "cvzone.FaceDetectionModule": faces}):
            self.assertEqual(detectar_presenca(), "unavailable")
        self.assertTrue(camera.released)


if __name__ == "__main__":
    unittest.main()
