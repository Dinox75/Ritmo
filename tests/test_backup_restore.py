"""Recovery rehearsals use only synthetic data in separate temporary folders."""

import base64
import hashlib
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from storage.database import Database
from storage.materials import import_material, original_path
from utils.config import load_config, save_config


class BackupRestoreCase(unittest.TestCase):
    def test_explicit_development_and_frozen_config_restore_complete_paused_session(self):
        for layout in ("development", "frozen"):
            with self.subTest(layout=layout), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                source = root / "source"
                db = Database(source / "storage" / "ritmo.db")
                db.initialize()
                config_path = (source / "config" / "local.json" if layout == "development"
                               else db.path.parent / "config.json")
                config = load_config()
                config["idle_tracker"]["threshold_seconds"] = 137
                save_config(config, config_path)
                subject = db.create_subject("Synthetic recovery")
                db.set_weekly_goal(731)
                content = b"Synthetic original\nReference for isolated recovery."
                material = import_material(db, subject["id"], "Recovery", "recovery.txt",
                                           base64.b64encode(content).decode("ascii"))
                note = db.create_note(subject["id"], "Synthetic annotation",
                                      material_id=material["id"], chunk_id=material["chunks"][0]["id"])
                start = datetime(2026, 11, 17, tzinfo=timezone.utc)
                at = lambda seconds: (start + timedelta(seconds=seconds)).isoformat()
                session = db.start_session(subject["id"], at=at(0))
                db.pause_session(session["id"], at=at(60))
                backup = db.create_backup(config_path=config_path)

                restored = root / "restored"
                with zipfile.ZipFile(backup["path"]) as archive:
                    self.assertIsNone(archive.testzip())
                    archive.extractall(restored)
                    self.assertEqual(archive.read("config/config.json"), config_path.read_bytes())
                (restored / "ritmo.db").write_bytes((restored / "database" / "ritmo.db").read_bytes())
                copy = Database(restored / "ritmo.db")
                copy.initialize()
                with copy.connect() as connection:
                    self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(copy.preferences()["weekly_goal_minutes"], 731)
                self.assertEqual(load_config(restored / "config" / "config.json")["idle_tracker"]["threshold_seconds"], 137)
                self.assertEqual(copy.list_notes()[0]["id"], note["id"])
                self.assertEqual(copy.get_material(material["id"])["chunks"][0]["body"], content.decode())
                original = restored / "materials" / material["stored_name"]
                self.assertEqual(original_path(copy, material["id"])[1], original)
                self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), material["sha256"])
                self.assertEqual(copy.get_session(session["id"], at=at(70))["status"], "pause")
                copy.resume_session(session["id"], at=at(90))
                finished = copy.finish_session(session["id"], at=at(150))
                self.assertEqual((finished["focus_seconds"], finished["pause_seconds"]), (120, 30))
                self.assertEqual(db.get_session(session["id"], at=at(150))["status"], "pause")

    def test_default_uses_effective_local_config_instead_of_adjacent_decoy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = Database(root / "storage" / "ritmo.db")
            db.initialize()
            effective = root / "config" / "local.json"
            effective.parent.mkdir()
            effective.write_bytes(b'{"synthetic": "effective"}')
            (db.path.parent / "config.json").write_bytes(b'{"synthetic": "decoy"}')
            with patch("utils.config.LOCAL_CONFIG", effective):
                backup = db.create_backup()
            with zipfile.ZipFile(backup["path"]) as archive:
                self.assertEqual(archive.read("config/config.json"), effective.read_bytes())


if __name__ == "__main__":
    unittest.main()
