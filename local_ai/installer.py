"""Instalação explícita e verificável de pesos e runtime fora do aplicativo."""

import hashlib
import json
import os
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path


MANIFEST_PATH = Path(__file__).with_name("models.json")


def manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def default_root():
    configured = os.environ.get("RITMO_MODEL_DIR")
    if configured:
        return Path(configured)
    local = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "RitmoModels"
    if sys.platform == "win32":
        try:
            if shutil.disk_usage(local.anchor).free >= 8 * 1024 ** 3:
                return local
            import ctypes
            candidates = []
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{letter}:\\"
                if ctypes.windll.kernel32.GetDriveTypeW(drive) == 3:
                    free = shutil.disk_usage(drive).free
                    if free >= 8 * 1024 ** 3:
                        candidates.append((free, Path(drive) / "RitmoModels"))
            if candidates:
                return max(candidates)[1]
        except OSError:
            pass
    return local


def validate_root(path):
    expanded = Path(path).expanduser()
    if not expanded.is_absolute():
        raise ValueError("Escolha uma pasta absoluta para os modelos.")
    root = expanded.resolve()
    from utils.config import DATA_DIR, ROOT
    if root == DATA_DIR.resolve() or DATA_DIR.resolve() in root.parents:
        raise ValueError("Os pesos devem ficar fora da pasta de dados pessoais do Ritmo.")
    if root == ROOT.resolve() or ROOT.resolve() in root.parents:
        raise ValueError("Os pesos devem ficar fora do repositório e do pacote.")
    return root


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def installed(root, model_key):
    info = manifest()["models"][model_key]
    file = validate_root(root) / "models" / info["filename"]
    runtime = validate_root(root) / "runtime" / manifest()["runtime"]["version"]
    return file.is_file() and file.stat().st_size == info["bytes"] and bool(list(runtime.rglob("llama-server.exe")))


def download(item, destination, progress=None):
    """Retoma arquivo parcial; a substituição só ocorre após tamanho e SHA-256 corretos."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size == item["bytes"] and sha256(destination) == item["sha256"]:
        if progress:
            progress(item["name"] if "name" in item else item["filename"], item["bytes"], item["bytes"])
        return destination
    partial = destination.with_name(destination.name + ".part")
    for attempt in range(3):
        offset = partial.stat().st_size if partial.is_file() else 0
        if offset > item["bytes"]:
            partial.unlink()
            offset = 0
        request = urllib.request.Request(item["url"], headers={
            "User-Agent": "Ritmo-local-model-installer/1.0",
            **({"Range": f"bytes={offset}-"} if offset else {})})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                if offset and response.status != 206:
                    partial.unlink(missing_ok=True)
                    offset = 0
                with partial.open("ab" if offset else "wb") as output:
                    done = offset
                    while block := response.read(4 * 1024 * 1024):
                        output.write(block)
                        done += len(block)
                        if progress:
                            progress(item.get("name", item.get("filename")), done, item["bytes"])
            if partial.stat().st_size != item["bytes"]:
                raise IOError("download incompleto")
            if sha256(partial) != item["sha256"]:
                partial.unlink()
                raise IOError("SHA-256 não confere com o catálogo versionado")
            partial.replace(destination)
            return destination
        except (OSError, IOError):
            if attempt == 2:
                raise
    raise RuntimeError("download não concluído")


def _extract_assets(paths, target):
    target = Path(target)
    if list(target.rglob("llama-server.exe")):
        return
    staging = target.with_name(target.name + ".stage")
    if staging.exists():
        resolved = staging.resolve()
        if resolved.parent != target.parent.resolve() or resolved.name != staging.name:
            raise RuntimeError("pasta temporária fora do diretório de modelos")
        shutil.rmtree(resolved)
    staging.mkdir(parents=True)
    try:
        for asset in paths:
            with zipfile.ZipFile(asset) as archive:
                for info in archive.infolist():
                    name = Path(info.filename.replace("\\", "/"))
                    if name.is_absolute() or ".." in name.parts or ":" in info.filename:
                        raise RuntimeError("pacote de runtime contém caminho inválido")
                    destination = (staging / name).resolve()
                    if destination != staging.resolve() and staging.resolve() not in destination.parents:
                        raise RuntimeError("pacote de runtime sai da pasta escolhida")
                archive.extractall(staging)
        if not list(staging.rglob("llama-server.exe")):
            raise RuntimeError("pacote de runtime não contém llama-server.exe")
        if target.exists():
            resolved = target.resolve()
            if resolved.parent != target.parent.resolve() or resolved.name != target.name:
                raise RuntimeError("pasta de runtime fora do diretório de modelos")
            shutil.rmtree(resolved)
        staging.replace(target)
    except BaseException:
        if staging.exists() and staging.resolve().parent == target.parent.resolve():
            shutil.rmtree(staging)
        raise


def install(model_key, root=None, progress=None):
    catalog = manifest()
    if model_key not in catalog["models"]:
        raise ValueError("modelo fora do catálogo")
    root = validate_root(root or default_root())
    root.mkdir(parents=True, exist_ok=True)
    model = catalog["models"][model_key]
    runtime = catalog["runtime"]
    runtime_target = root / "runtime" / runtime["version"]
    needed = 0 if list(runtime_target.rglob("llama-server.exe")) else runtime["extracted_bytes"]
    model_file = root / "models" / model["filename"]
    if not (model_file.is_file() and model_file.stat().st_size == model["bytes"] and
            sha256(model_file) == model["sha256"]):
        needed += model["bytes"]
    needed += sum(asset["bytes"] for asset in runtime["assets"]
                  if not ((root / "downloads" / asset["name"]).is_file() and
                          (root / "downloads" / asset["name"]).stat().st_size == asset["bytes"] and
                          sha256(root / "downloads" / asset["name"]) == asset["sha256"]))
    if shutil.disk_usage(root).free < needed + 1024 ** 3:
        raise OSError("Espaço insuficiente: reserve modelo, arquivos do motor e mais 1 GB livre. Escolha outra unidade.")
    downloaded = [download(asset, root / "downloads" / asset["name"], progress)
                  for asset in runtime["assets"]]
    _extract_assets(downloaded, root / "runtime" / runtime["version"])
    file = download(model, root / "models" / model["filename"], progress)
    receipt = {"model": model_key, "model_sha256": model["sha256"],
               "runtime": runtime["id"], "root": str(root)}
    (root / "installation.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return receipt
