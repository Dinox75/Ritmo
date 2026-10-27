"""Entrada local do Ritmo: agente Windows, diagnóstico, importação e interface."""

import argparse
import json
import logging
import platform
import shutil
import threading

from storage.database import Database
from storage.event_writer import EventWriter
from utils.config import DATA_DIR, LOCAL_CONFIG, LOG_FILE, MIGRATION_DISABLED, ROOT, load_config


def run_sensor(name, target, writer, stop_event, *args, **kwargs):
    writer.health(name, "running")
    has_multitask = name == "window_tracker" and kwargs.get("multitask_enabled", False)
    if has_multitask:
        writer.health("multitask_analyzer", "running")
    def emit(sensor, state, details):
        writer.emit(sensor, state, details)
        if sensor == "presence":
            writer.health(name, "unavailable" if state == "unavailable" else "running")
    try:
        target(stop_event, *args, emit, **kwargs)
    except Exception as error:
        detail = f"{type(error).__name__}: {error}"[:300]
        logging.exception("Sensor %s falhou", name)
        writer.health(name, "failed", detail)
        if has_multitask:
            writer.health("multitask_analyzer", "failed", "depende do window_tracker")
    else:
        writer.health(name, "stopped")
        if has_multitask:
            writer.health("multitask_analyzer", "stopped")


class SensorAgent:
    """Gerencia todos os sensores no processo da interface ou no modo CLI."""

    def __init__(self, database):
        self.database = database
        self.writer = None
        self.stop_event = None
        self.threads = []
        self.lock = threading.RLock()

    def start(self, config):
        from monitor.idle_tracker import monitorar_inatividade
        from monitor.presence_detector import monitorar_presenca
        from monitor.window_tracker import iniciar_monitoramento

        with self.lock:
            if self.writer is not None:
                raise RuntimeError("agente já iniciado")
            self.writer = EventWriter(self.database)
            self.writer.start()
            self.stop_event = threading.Event()
            writer, stop_event = self.writer, self.stop_event
            writer.health("multitask_analyzer", "waiting" if config["window_tracker"]["enabled"]
                          and config["multitask_analyzer"]["enabled"] else "disabled")
            specs = (
                ("window_tracker", iniciar_monitoramento,
                 (config["window_tracker"]["interval_seconds"],),
                 {"include_title": config["window_tracker"]["capture_titles"],
                  "multitask_enabled": config["multitask_analyzer"]["enabled"],
                  "observation_seconds": config["multitask_analyzer"]["observation_seconds"],
                  "alert_switches": config["multitask_analyzer"]["alert_switches"]}),
                ("presence_detector", monitorar_presenca,
                 (config["presence_detector"]["interval_seconds"],
                  config["presence_detector"]["camera_index"]), {}),
                ("idle_tracker", monitorar_inatividade,
                 (config["idle_tracker"]["interval_seconds"],
                  config["idle_tracker"]["threshold_seconds"]), {}),
            )
            for name, target, args, kwargs in specs:
                if config[name]["enabled"]:
                    thread = threading.Thread(target=run_sensor,
                                              args=(name, target, writer, stop_event, *args),
                                              kwargs=kwargs, name=name, daemon=True)
                    thread.start()
                    self.threads.append(thread)
                else:
                    writer.health(name, "disabled")
            writer.flush()
            return len(self.threads)

    def stop(self):
        with self.lock:
            if self.writer is None:
                return
            self.stop_event.set()
            for thread in self.threads:
                thread.join(timeout=10)
                if thread.is_alive():
                    logging.error("Sensor %s não encerrou em 10 s", thread.name)
                    self.writer.health(thread.name, "stopping_timeout")
            try:
                self.writer.close()
            finally:
                self.writer = None
                self.stop_event = None
                self.threads = []

    def restart(self, config):
        with self.lock:
            self.stop()
            try:
                return self.start(config)
            except BaseException:
                self.stop()
                raise


def run_monitor(database, config):
    agent = SensorAgent(database)
    count = agent.start(config)
    if not count:
        print("Nenhum sensor habilitado. Edite config/local.json para ativar o agente.")
        agent.stop()
        return
    print("Agente Ritmo ativo. Ctrl+C para encerrar.")
    try:
        while not agent.stop_event.wait(0.5):
            if agent.writer.failure:
                raise RuntimeError("gravador de eventos falhou") from agent.writer.failure
    except KeyboardInterrupt:
        pass
    finally:
        agent.stop()
        print("Agente encerrado.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ritmo: estudo local e sensores opcionais")
    parser.add_argument("command", nargs="?", default="serve",
                        choices=("serve", "monitor", "health", "import-legacy", "erase-local-data"))
    parser.add_argument("path", nargs="?", help="CSV antigo para import-legacy")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--confirm-erase", action="store_true",
                        help="necessário para apagar permanentemente dados locais")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    database = Database()
    if args.command == "erase-local-data":
        if not args.confirm_erase:
            parser.error("use --confirm-erase para apagar permanentemente os dados locais")
        paths = [database.path, database.path.with_name(database.path.name + "-wal"),
                 database.path.with_name(database.path.name + "-shm"),
                 ROOT / "storage" / "logs.csv", ROOT / "storage" / "usage_summary.csv",
                 LOCAL_CONFIG, LOG_FILE, MIGRATION_DISABLED]
        paths.append(DATA_DIR / "tutor-key.dpapi")
        for path in paths:
            if path.exists():
                path.unlink()
                print(f"Removido: {path}")
        for folder in (DATA_DIR / "backups", DATA_DIR / "materials"):
            if folder.exists():
                if folder.resolve().parent != DATA_DIR.resolve():
                    raise RuntimeError("pasta fora dos dados do Ritmo")
                shutil.rmtree(folder)
                print(f"Removido: {folder}")
        return
    database.initialize()
    if args.command == "serve":
        from dashboard.app import serve
        serve(database, args.port)
    elif args.command == "monitor":
        if platform.system() != "Windows":
            raise SystemExit("O agente de sensores requer Windows")
        run_monitor(database, load_config())
    elif args.command == "health":
        print(json.dumps(database.health(), ensure_ascii=False, indent=2))
    elif args.command == "import-legacy":
        if not args.path:
            parser.error("informe o caminho do CSV antigo")
        from storage.legacy_import import import_legacy
        print(json.dumps(import_legacy(database, args.path), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
