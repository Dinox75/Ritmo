"""Preview capabilities are explicit and never probe camera hardware in tests."""

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from main import SensorAgent
from monitor.cameras import camera_options, test_camera as capture_camera
from storage.database import Database
from utils.config import DEFAULT_CONFIG, validate_config


class CameraCapabilitiesCase(unittest.TestCase):
    def config(self, folder):
        config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
        config["tutor"]["model_root"] = str(Path(folder) / "synthetic-models")
        return validate_config(config)

    def test_frozen_preview_disables_camera_even_with_runtime_environment_override(self):
        from utils import capabilities
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config").mkdir()
            (root / "config" / "capabilities.json").write_text(
                json.dumps({"profile": "preview", "camera": False}), encoding="utf-8")
            with patch.object(capabilities, "ROOT", root), patch.object(capabilities.sys, "frozen", True, create=True), \
                 patch.dict("os.environ", {"RITMO_BUILD_PROFILE": "full"}):
                self.assertFalse(capabilities.camera_available())
                self.assertEqual(capabilities.camera_capability()["profile"], "preview")
            with patch.object(capabilities, "ROOT", root), patch.object(capabilities.sys, "frozen", True, create=True):
                (root / "config" / "capabilities.json").unlink()
                self.assertFalse(capabilities.camera_available())

    def test_source_and_explicit_full_manifest_keep_camera_capability(self):
        from utils import capabilities
        with patch.object(capabilities.sys, "frozen", False, create=True):
            self.assertTrue(capabilities.camera_available())
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config").mkdir()
            (root / "config" / "capabilities.json").write_text(
                json.dumps({"profile": "full", "camera": True}), encoding="utf-8")
            with patch.object(capabilities, "ROOT", root), patch.object(capabilities.sys, "frozen", True, create=True):
                self.assertTrue(capabilities.camera_available())

    def test_disabled_options_and_capture_never_enumerate_or_probe_devices(self):
        with patch("utils.capabilities.camera_available", return_value=False), \
             patch("monitor.cameras._directshow_devices", side_effect=AssertionError("device enumeration")), \
             patch("monitor.cameras.windows_devices", side_effect=AssertionError("PowerShell enumeration")), \
             patch("monitor.cameras._privacy_denied", side_effect=AssertionError("registry probe")):
            options = camera_options()
            self.assertFalse(options["available"])
            self.assertEqual(options["devices"], [])
            self.assertEqual(options["indices"], [])
            with self.assertRaisesRegex(ValueError, "câmera"):
                capture_camera(0)

    def test_sensor_agent_skips_disabled_capability_and_keeps_other_sensors(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "ritmo.db")
            db.initialize()
            config = self.config(folder)
            for name in ("window_tracker", "idle_tracker", "presence_detector"):
                config[name]["enabled"] = True
            called = []
            def sensor(stop, *args, **kwargs):
                called.append(threading.current_thread().name)
                stop.wait(2)
            agent = SensorAgent(db)
            with patch("utils.capabilities.camera_available", return_value=False), \
                 patch("monitor.presence_detector.monitorar_presenca", side_effect=AssertionError("camera sensor")), \
                 patch("monitor.window_tracker.iniciar_monitoramento", side_effect=sensor), \
                 patch("monitor.idle_tracker.monitorar_inatividade", side_effect=sensor):
                try:
                    self.assertEqual(agent.start(config), 2)
                finally:
                    agent.stop()
            self.assertCountEqual(called, ["window_tracker", "idle_tracker"])
            with db.connect() as connection:
                health = connection.execute("SELECT status, detail FROM sensor_health WHERE sensor='presence_detector'").fetchone()
                self.assertEqual(health["status"], "unavailable")
                self.assertIn("câmera", health["detail"])

    def test_enabled_agent_runs_controlled_camera_provider(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "ritmo.db")
            db.initialize()
            config = self.config(folder)
            config["window_tracker"]["enabled"] = config["idle_tracker"]["enabled"] = False
            config["presence_detector"]["enabled"] = True
            config["presence_detector"]["camera_index"] = 3
            called = threading.Event()
            def sensor(stop, interval, emit, *, camera_index=0):
                called.set()
                emit("presence", "present", {"camera_index": camera_index})
                stop.wait(2)
            agent = SensorAgent(db)
            with patch("utils.capabilities.camera_available", return_value=True), \
                 patch("monitor.presence_detector.monitorar_presenca", side_effect=sensor):
                try:
                    self.assertEqual(agent.start(config), 1)
                    self.assertTrue(called.wait(1))
                finally:
                    agent.stop()
            with db.connect() as connection:
                event = connection.execute("SELECT state, details FROM events WHERE sensor='presence'").fetchone()
                self.assertEqual(event["state"], "present")
                self.assertEqual(json.loads(event["details"])["camera_index"], 3)

    def test_preview_settings_explain_camera_absence_and_keep_other_controls(self):
        try:
            from playwright.sync_api import expect, sync_playwright
        except ImportError:
            self.skipTest("Browser QA requires Playwright")
        from tests.browser_target import BROWSER
        if not BROWSER:
            self.skipTest("Browser QA requires Edge")
        from dashboard.app import make_server
        from utils.config import save_config
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "ritmo.db")
            db.initialize()
            config_path = Path(folder) / "config.json"
            save_config(self.config(folder), config_path)
            with patch("utils.capabilities.camera_available", return_value=False), \
                 patch("monitor.cameras._directshow_devices", side_effect=AssertionError("hardware enumeration")):
                server = make_server(db, 0, config_path=config_path)
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                try:
                    with sync_playwright() as playwright:
                        browser = playwright.chromium.launch(executable_path=str(BROWSER), headless=True)
                        try:
                            page = browser.new_page()
                            errors = []
                            page.on("pageerror", lambda error: errors.append(str(error)))
                            server.session.authorize_browser(page, server.server_port)
                            page.goto(f"http://127.0.0.1:{server.server_port}/")
                            page.locator('nav a[data-view-target="configuracoes"]').click()
                            expect(page.locator("#camera-capability")).to_be_visible()
                            expect(page.locator("#camera-capability")).to_contain_text("não inclui câmera")
                            for selector in ("#presence-enabled", "#camera-index", "#camera-test", "#presence-interval"):
                                expect(page.locator(selector)).to_be_disabled()
                            expect(page.locator("#window-enabled")).to_be_enabled()
                            expect(page.locator("#idle-enabled")).to_be_enabled()
                            # Re-rendering config must not re-enable a saved camera preference.
                            page.evaluate("renderConfig({...sensorConfig, presence_detector: {...sensorConfig.presence_detector, enabled: true}})")
                            expect(page.locator("#presence-enabled")).not_to_be_checked()
                            self.assertFalse(page.evaluate("collectConfig().presence_detector.enabled"))
                            self.assertEqual(errors, [])
                        finally:
                            browser.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join()

    def test_preview_camera_http_action_refuses_before_hardware_access(self):
        from dashboard.app import make_server
        from utils.config import save_config
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "ritmo.db")
            db.initialize()
            config_path = Path(folder) / "config.json"
            save_config(self.config(folder), config_path)
            with patch("utils.capabilities.camera_available", return_value=False), \
                 patch("monitor.cameras._privacy_denied", side_effect=AssertionError("hardware probe")):
                server = make_server(db, 0, config_path=config_path)
                thread = threading.Thread(target=server.serve_forever)
                thread.start()
                try:
                    request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/api/cameras/test",
                        data=b'{"index":0}', headers={"Content-Type": "application/json",
                            "Authorization": "Bearer " + server.session.token})
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(request, timeout=5)
                    self.assertEqual(error.exception.code, 400)
                    self.assertIn("não inclui câmera", json.load(error.exception)["error"])
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join()
