"""Runtime trust anchored in the app catalog, never in a writable install receipt."""

import hashlib
import json
import stat
from pathlib import Path

CATALOG_PATH = Path(__file__).with_name("runtime-integrity.json")
REINSTALL = "O motor local falhou na verificação de integridade. Reinstale em Configurações escolhendo uma pasta nova de modelos. Preserve a pasta antiga para diagnóstico; não execute seus arquivos."


class RuntimeIntegrityError(RuntimeError):
    pass


def reject_redirects(path):
    """Inspect lexical ancestors before resolve(), including Windows junctions."""
    path = Path(path).absolute()
    for component in (*reversed(path.parents), path):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(metadata.st_mode) or
                getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise RuntimeIntegrityError(REINSTALL)
    return path


def trusted_catalog(runtime):
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assets = [{key: asset[key] for key in ("name", "bytes", "sha256")}
              for asset in runtime["assets"]]
    if (catalog["runtime_id"] != runtime["id"] or catalog["version"] != runtime["version"] or
            catalog["assets"] != assets or "llama-server.exe" not in catalog["files"]):
        raise RuntimeIntegrityError(REINSTALL)
    # This release's verified archives contain only root-level files.
    if any(Path(name).name != name or ":" in name or "\\" in name for name in catalog["files"]):
        raise RuntimeIntegrityError(REINSTALL)
    return catalog["files"]


def verify_runtime(target, runtime):
    """Verify the complete pinned archive inventory before using its root launcher.

    Legacy installations pass the same check. A local installation.json cannot
    supply or update hashes, and no unverified directory is auto-enrolled.
    """
    try:
        target = reject_redirects(target)
        expected = trusted_catalog(runtime)
        if not target.is_dir():
            raise RuntimeIntegrityError(REINSTALL)
        entries = list(target.iterdir())
        if {entry.name for entry in entries} != set(expected):
            raise RuntimeIntegrityError(REINSTALL)
        for entry in entries:
            reject_redirects(entry)
            if not stat.S_ISREG(entry.lstat().st_mode):
                raise RuntimeIntegrityError(REINSTALL)
            item = expected[entry.name]
            if entry.stat().st_size != item["bytes"]:
                raise RuntimeIntegrityError(REINSTALL)
            with entry.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != item["sha256"]:
                raise RuntimeIntegrityError(REINSTALL)
        return target / "llama-server.exe"
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RuntimeIntegrityError(REINSTALL) from error
