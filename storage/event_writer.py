"""Único gravador de telemetria, serializado por fila em SQLite."""

import json
import queue
import threading
import uuid
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class EventWriter:
    def __init__(self, database):
        self.database = database
        self.items = queue.Queue()
        self.thread = None
        self.failure = None

    def start(self):
        if self.thread is not None:
            raise RuntimeError("gravador já iniciado")
        self.thread = threading.Thread(target=self._run, name="event_writer")
        self.thread.start()

    def emit(self, sensor, state, details=None, *, event_id=None, at=None):
        self.items.put(("event", event_id or str(uuid.uuid4()), at or utc_now(),
                        sensor, state, json.dumps(details or {}, ensure_ascii=False)))

    def health(self, sensor, status, detail=""):
        self.items.put(("health", sensor, status, detail, utc_now()))

    def flush(self):
        marker = threading.Event()
        self.items.put(("flush", marker))
        marker.wait(timeout=10)
        if self.failure:
            raise RuntimeError("gravador de eventos falhou") from self.failure
        if not marker.is_set():
            raise TimeoutError("gravador de eventos não respondeu")

    def close(self):
        if self.thread is None:
            return
        self.items.put(("stop",))
        self.thread.join(timeout=10)
        if self.thread.is_alive():
            raise TimeoutError("gravador de eventos não encerrou")
        self.thread = None
        if self.failure:
            raise RuntimeError("gravador de eventos falhou") from self.failure

    def _run(self):
        try:
            with self.database.connect() as connection:
                while True:
                    item = self.items.get()
                    if item[0] == "stop":
                        return
                    if item[0] == "flush":
                        connection.commit()
                        item[1].set()
                        continue
                    if item[0] == "event":
                        connection.execute(
                            "INSERT OR IGNORE INTO events (id, at, sensor, state, details) VALUES (?, ?, ?, ?, ?)",
                            item[1:])
                    else:
                        connection.execute(
                            "INSERT INTO sensor_health (sensor, status, detail, updated_at) VALUES (?, ?, ?, ?) "
                            "ON CONFLICT(sensor) DO UPDATE SET status=excluded.status, "
                            "detail=excluded.detail, updated_at=excluded.updated_at", item[1:])
                    connection.commit()
        except Exception as error:
            self.failure = error
            while not self.items.empty():
                item = self.items.get_nowait()
                if item[0] == "flush":
                    item[1].set()
