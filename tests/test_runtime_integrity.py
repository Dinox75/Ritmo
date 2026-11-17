"""Runtime integrity uses synthetic bytes; untrusted binaries are never executed."""

import hashlib
import json
import os
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from local_ai import installer, integrity
from local_ai.runtime import LocalRuntime, ModelUnavailable


class RuntimeIntegrityCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ritmo-integrity-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / "runtime" / "synthetic"
        self.runtime.mkdir(parents=True)
        (self.runtime / "llama-server.exe").write_bytes(b"MZtrusted-launcher")
        (self.runtime / "engine.dll").write_bytes(b"MZtrusted-library")
        (self.root / "models").mkdir()
        (self.root / "models" / "test.gguf").write_bytes(b"synthetic model")
        self.catalog = {"runtime": {"id": "synthetic", "version": "synthetic", "assets": []},
                        "models": {"test": {"filename": "test.gguf", "bytes": 15,
                                              "sha256": hashlib.sha256(b"synthetic model").hexdigest()}}}
        for target in ("local_ai.installer.manifest", "local_ai.runtime.manifest"):
            mocker = patch(target, return_value=self.catalog)
            mocker.start()
            self.addCleanup(mocker.stop)

    def assert_refused_before_launch(self):
        with patch("local_ai.runtime.subprocess.Popen", side_effect=AssertionError("unsafe execution")) as launch:
            with self.assertRaisesRegex(ModelUnavailable, "[Rr]einstal"):
                LocalRuntime(self.root).start("test", timeout=0)
            launch.assert_not_called()

    def test_untrusted_legacy_executable_is_refused_before_launch(self):
        self.assert_refused_before_launch()

    def test_nested_launcher_is_not_selected(self):
        (self.runtime / "llama-server.exe").unlink()
        nested = self.runtime / "other"
        nested.mkdir()
        (nested / "llama-server.exe").write_bytes(b"MZsubstitute")
        self.assert_refused_before_launch()

    def test_installer_does_not_accept_preexisting_unverified_launcher(self):
        with self.assertRaisesRegex(RuntimeError, "[Rr]einstal|integridade"):
            installer._extract_assets([], self.runtime)

    def pin_synthetic_catalog(self):
        """An app resource fixture; never stored alongside the runtime."""
        resource = self.root / "app-catalog.json"
        resource.write_text(json.dumps({"runtime_id": "synthetic", "version": "synthetic", "assets": [],
            "files": {"llama-server.exe": {"bytes": 18, "sha256": hashlib.sha256(b"MZtrusted-launcher").hexdigest()},
                      "engine.dll": {"bytes": 17, "sha256": hashlib.sha256(b"MZtrusted-library").hexdigest()}}}), encoding="utf-8")
        mocker = patch.object(integrity, "CATALOG_PATH", resource)
        mocker.start()
        self.addCleanup(mocker.stop)

    def test_mutation_during_model_hash_is_refused_as_model_unavailable(self):
        self.pin_synthetic_catalog()
        original_hash = installer.sha256
        def hash_then_mutate(path):
            digest = original_hash(path)
            (self.runtime / "engine.dll").write_bytes(b"MZaltered-library")
            return digest
        with patch("local_ai.runtime.sha256", side_effect=hash_then_mutate):
            self.assert_refused_before_launch()

    def test_catalog_must_match_pinned_archive_identity(self):
        self.pin_synthetic_catalog()
        self.catalog["runtime"]["assets"] = [{"name": "changed.zip", "bytes": 1, "sha256": "0" * 64}]
        self.assert_refused_before_launch()

    def test_installer_verifies_archive_and_extracted_inventory(self):
        self.pin_synthetic_catalog()
        archive = self.root / "runtime.zip"
        with zipfile.ZipFile(archive, "w") as stream:
            stream.writestr("llama-server.exe", b"MZtrusted-launcher")
            stream.writestr("engine.dll", b"MZtrusted-library")
        asset = {"name": archive.name, "bytes": archive.stat().st_size, "sha256": installer.sha256(archive)}
        self.catalog["runtime"]["assets"] = [asset]
        resource = self.root / "app-catalog.json"
        pinned = json.loads(resource.read_text(encoding="utf-8"))
        pinned["assets"] = [asset]
        resource.write_text(json.dumps(pinned), encoding="utf-8")
        target = self.root / "new-runtime"
        installer._extract_assets([archive], target)
        self.assertEqual(integrity.verify_runtime(target, self.catalog["runtime"]), target / "llama-server.exe")
        archive.write_bytes(b"untrusted download")
        rejected_target = self.root / "must-not-extract"
        with self.assertRaises(integrity.RuntimeIntegrityError):
            installer._extract_assets([archive], rejected_target)
        self.assertFalse(rejected_target.exists())

    def test_archive_catalog_legacy_install_starts_exact_root_launcher(self):
        self.pin_synthetic_catalog()
        class Child:
            stdout = io.StringIO("")
            exited = False
            def poll(self): return 0 if self.exited else None
            def terminate(self): self.exited = True
            def wait(self, timeout): return 0
        child = Child()
        with patch("local_ai.runtime.subprocess.Popen", return_value=child) as launch, \
             patch.object(LocalRuntime, "_urlopen", return_value=io.StringIO('{"status":"ok"}')):
            engine = LocalRuntime(self.root)
            try:
                engine.start("test")
                self.assertIs(engine.process, child)
                self.assertEqual(launch.call_args.args[0][0], str(self.runtime / "llama-server.exe"))
                self.assertEqual(launch.call_args.kwargs["cwd"], self.runtime)
            finally:
                engine.stop()
            self.assertTrue(child.exited)

    def test_modified_missing_unexpected_and_nested_files_refused(self):
        self.pin_synthetic_catalog()
        cases = ("changed_exe", "changed_dll", "missing_dll", "unexpected_dll", "unexpected_exe",
                 "disguised_pe", "nested_exe", "forged_receipt")
        for case in cases:
            with self.subTest(case=case):
                (self.runtime / "llama-server.exe").write_bytes(b"MZtrusted-launcher")
                (self.runtime / "engine.dll").write_bytes(b"MZtrusted-library")
                extra = None
                if case == "changed_exe": (self.runtime / "llama-server.exe").write_bytes(b"MZaltered-launcher")
                elif case in ("changed_dll", "forged_receipt"):
                    (self.runtime / "engine.dll").write_bytes(b"MZaltered-library")
                    (self.root / "installation.json").write_text('{"trusted": true}')
                elif case == "missing_dll": (self.runtime / "engine.dll").unlink()
                else:
                    extra = self.runtime / {"unexpected_dll": "extra.dll", "unexpected_exe": "extra.exe",
                                            "disguised_pe": "payload.dat", "nested_exe": "sub"}[case]
                    if case == "nested_exe":
                        extra.mkdir()
                        (extra / "llama-server.exe").write_bytes(b"MZsubstitute")
                    else: extra.write_bytes(b"MZsubstitute")
                self.assert_refused_before_launch()
                if extra:
                    if extra.is_dir():
                        (extra / "llama-server.exe").unlink()
                        extra.rmdir()
                    else: extra.unlink()

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_windows_junction_runtime_and_root_are_refused(self):
        import subprocess
        self.pin_synthetic_catalog()
        for target in (self.root / "redirected-runtime", self.root / "redirected-root"):
            subprocess.run(["cmd", "/c", "mklink", "/J", str(target), str(self.runtime)],
                           check=True, capture_output=True)
            try:
                with self.assertRaises(integrity.RuntimeIntegrityError):
                    integrity.verify_runtime(target, self.catalog["runtime"])
                with self.assertRaises(integrity.RuntimeIntegrityError):
                    installer.validate_root(target)
            finally:
                target.rmdir()
        original = self.root / "original-runtime"
        self.runtime.rename(original)
        subprocess.run(["cmd", "/c", "mklink", "/J", str(self.runtime), str(original)],
                       check=True, capture_output=True)
        try:
            self.assert_refused_before_launch()
        finally:
            self.runtime.rmdir()
            original.rename(self.runtime)


if __name__ == "__main__":
    unittest.main()
