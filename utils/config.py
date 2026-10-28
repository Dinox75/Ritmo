"""Configuração validada e caminhos independentes do diretório atual."""

import json
import os
import re
import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "config.json"
FROZEN = bool(getattr(sys, "frozen", False))
DATA_DIR = ((Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Ritmo")
            if FROZEN else ROOT / "storage")
LOCAL_CONFIG = (DATA_DIR / "config.json") if FROZEN else ROOT / "config" / "local.json"
DEFAULT_DB = DATA_DIR / "ritmo.db"
LOG_FILE = DATA_DIR / "ritmo.log"
MIGRATION_DISABLED = DATA_DIR / ".migration_disabled"


def migrate_repo_data(source_root, destination=DATA_DIR):
    """Copia dados anteriores uma vez, sem tocar no original nem no destino existente."""
    source_root, destination = Path(source_root), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    migrated = []
    old_db = source_root / "storage" / "ritmo.db"
    new_db = destination / "ritmo.db"
    if old_db.is_file() and not new_db.exists():
        with closing(sqlite3.connect(old_db)) as source, closing(sqlite3.connect(new_db)) as target:
            source.backup(target)
        migrated.append("banco")
    old_config = source_root / "config" / "local.json"
    new_config = destination / "config.json"
    if old_config.is_file() and not new_config.exists():
        shutil.copy2(old_config, new_config)
        migrated.append("configuração")
    return migrated


def migrate_for_desktop():
    if not FROZEN or MIGRATION_DISABLED.exists():
        return []
    # Build antigo no checkout ou pacote instalado fora do OneDrive.
    checkout = Path(sys.executable).resolve().parents[2]
    if not (checkout / "main.py").is_file():
        pointer = Path(sys.executable).resolve().parent / "source_checkout.txt"
        if not pointer.is_file():
            return []
        checkout = Path(pointer.read_text(encoding="utf-8-sig").strip())
        if not (checkout / "main.py").is_file():
            return []
    return migrate_repo_data(checkout)


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("configuração deve ser um objeto")
    for sensor in ("window_tracker", "presence_detector", "idle_tracker"):
        item = config.get(sensor)
        if not isinstance(item, dict) or type(item.get("enabled")) is not bool:
            raise ValueError(f"{sensor}.enabled deve ser booleano")
        interval = item.get("interval_seconds")
        if type(interval) not in (int, float) or not 0.1 <= interval <= 3600:
            raise ValueError(f"{sensor}.interval_seconds deve estar entre 0.1 e 3600")
    camera_index = config["presence_detector"].get("camera_index", 0)
    if type(camera_index) is not int or not 0 <= camera_index <= 5:
        raise ValueError("presence_detector.camera_index deve estar entre 0 e 5")
    config["presence_detector"]["camera_index"] = camera_index
    threshold = config["idle_tracker"].get("threshold_seconds", 60)
    if type(threshold) not in (int, float) or not 1 <= threshold <= 86400:
        raise ValueError("idle_tracker.threshold_seconds deve estar entre 1 e 86400")
    config["idle_tracker"]["threshold_seconds"] = threshold
    multi = config.get("multitask_analyzer", {})
    if type(multi.get("enabled", False)) is not bool:
        raise ValueError("multitask_analyzer.enabled deve ser booleano")
    for name, default, maximum in (("observation_seconds", 60, 3600), ("alert_switches", 4, 100)):
        value = multi.get(name, default)
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError(f"multitask_analyzer.{name} deve ser inteiro entre 1 e {maximum}")
        multi[name] = value
    config["multitask_analyzer"] = multi
    title = config["window_tracker"].get("capture_titles", False)
    if type(title) is not bool:
        raise ValueError("window_tracker.capture_titles deve ser booleano")
    config["window_tracker"]["capture_titles"] = title
    tutor = config.get("tutor", {})
    if not isinstance(tutor, dict):
        raise ValueError("configuração do tutor inválida")
    # Configurações OpenAI antigas são aceitas para preservar sensores e preferências,
    # mas nunca dão origem a uma chamada remota.
    model = tutor.get("model") if tutor.get("provider") == "local" else None
    if model not in {"qwen3-4b-q4_k_m", "qwen3-1.7b-q8_0"}:
        model = "qwen3-4b-q4_k_m"
    from local_ai.installer import default_root, validate_root
    model_root = str(validate_root(tutor.get("model_root") or default_root()))
    config["tutor"] = {"provider": "local", "model": model, "model_root": model_root}
    experience = config.get("experience", {})
    if not isinstance(experience, dict):
        raise ValueError("configuração da experiência inválida")
    defaults = {"theme": "dark", "brightness": 100, "soundscape": "off", "volume": 35,
                "reminders_enabled": False, "break_minutes": 25, "excess_minutes": 15,
                "completion_sound": False}
    if set(experience) - set(defaults):
        raise ValueError("opção desconhecida da experiência")
    experience = defaults | experience
    if experience["theme"] not in {"light", "dark", "system"}:
        raise ValueError("tema inválido")
    if experience["soundscape"] not in {"off", "rain", "brown"}:
        raise ValueError("som ambiente inválido")
    for name, minimum, maximum in (("brightness", 85, 100), ("volume", 0, 100),
                                    ("break_minutes", 5, 180), ("excess_minutes", 5, 120)):
        value = experience[name]
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"{name} deve estar entre {minimum} e {maximum}")
    for name in ("reminders_enabled", "completion_sound"):
        if type(experience[name]) is not bool:
            raise ValueError(f"{name} deve ser booleano")
    config["experience"] = experience
    return config


def load_config(path=None):
    path = path or (LOCAL_CONFIG if LOCAL_CONFIG.exists() else DEFAULT_CONFIG)
    with Path(path).open(encoding="utf-8") as file:
        return validate_config(json.load(file))


def save_config(config, path=LOCAL_CONFIG):
    config = validate_config(json.loads(json.dumps(config)))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".tmp")
    pending.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(path)
    return config
