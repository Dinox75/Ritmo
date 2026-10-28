"""Persistência SQLite local do Ritmo. Migração inicial idempotente."""

import json
import re
import sqlite3
import time
import uuid
import zipfile
from urllib.parse import urlparse
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from utils.config import DEFAULT_DB


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return str(uuid.uuid4())


def seconds_between(start, end):
    return max(0, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())


class ConflictError(ValueError):
    pass


class Database:
    def __init__(self, path=DEFAULT_DB):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 8:
                raise RuntimeError("banco criado por versão mais recente")
            if version == 0:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS events (
                        id TEXT PRIMARY KEY, at TEXT NOT NULL, sensor TEXT NOT NULL,
                        state TEXT NOT NULL, details TEXT NOT NULL);
                    CREATE INDEX IF NOT EXISTS events_at ON events(at);
                    CREATE TABLE IF NOT EXISTS sensor_health (
                        sensor TEXT PRIMARY KEY, status TEXT NOT NULL,
                        detail TEXT NOT NULL, updated_at TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS subjects (
                        id TEXT PRIMARY KEY, name TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES subjects(id),
                        status TEXT NOT NULL CHECK(status IN ('focus','pause','complete')),
                        started_at TEXT NOT NULL, ended_at TEXT);
                    CREATE UNIQUE INDEX IF NOT EXISTS one_open_session ON sessions(status)
                        WHERE status IN ('focus','pause');
                    CREATE TABLE IF NOT EXISTS session_intervals (
                        id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                        kind TEXT NOT NULL CHECK(kind IN ('focus','pause')),
                        started_at TEXT NOT NULL, ended_at TEXT);
                    CREATE TABLE IF NOT EXISTS session_adjustments (
                        id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                        delta_seconds INTEGER NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS notes (
                        id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES subjects(id),
                        session_id TEXT REFERENCES sessions(id), body TEXT NOT NULL,
                        version INTEGER NOT NULL DEFAULT 1, deleted INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                    PRAGMA user_version=1;
                """)
            if version < 2:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS preferences (
                        key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    INSERT OR IGNORE INTO preferences(key, value) VALUES ('weekly_goal_minutes', '480');
                    PRAGMA user_version=2;
                """)
            if version < 3:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS ui_state (
                        key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    PRAGMA user_version=3;
                """)
            if version < 4:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS materials (
                        id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES subjects(id),
                        name TEXT NOT NULL, source_name TEXT NOT NULL, file_type TEXT NOT NULL,
                        stored_name TEXT NOT NULL UNIQUE, size_bytes INTEGER NOT NULL,
                        imported_at TEXT NOT NULL, status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
                        sha256 TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS material_chunks (
                        id TEXT PRIMARY KEY, material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
                        ordinal INTEGER NOT NULL, locator TEXT NOT NULL, body TEXT NOT NULL,
                        UNIQUE(material_id, ordinal));
                    CREATE TABLE IF NOT EXISTS material_note_links (
                        note_id TEXT PRIMARY KEY REFERENCES notes(id) ON DELETE CASCADE,
                        material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
                        chunk_id TEXT NOT NULL REFERENCES material_chunks(id) ON DELETE CASCADE,
                        quote TEXT NOT NULL);
                    CREATE INDEX IF NOT EXISTS materials_subject ON materials(subject_id, imported_at);
                    PRAGMA user_version=4;
                """)
            if version < 5:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS note_selections (
                        note_id TEXT PRIMARY KEY REFERENCES notes(id) ON DELETE CASCADE,
                        start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL);
                    CREATE VIRTUAL TABLE IF NOT EXISTS material_chunks_fts USING fts5(
                        body, content='material_chunks', content_rowid='rowid',
                        tokenize='unicode61 remove_diacritics 2');
                    CREATE TABLE IF NOT EXISTS tutor_threads (
                        id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES subjects(id),
                        session_id TEXT REFERENCES sessions(id), mode TEXT NOT NULL DEFAULT 'duvida',
                        created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                    CREATE UNIQUE INDEX IF NOT EXISTS tutor_session_thread ON tutor_threads(session_id)
                        WHERE session_id IS NOT NULL;
                    CREATE UNIQUE INDEX IF NOT EXISTS tutor_subject_thread ON tutor_threads(subject_id)
                        WHERE session_id IS NULL;
                    CREATE TABLE IF NOT EXISTS tutor_thread_materials (
                        thread_id TEXT NOT NULL REFERENCES tutor_threads(id) ON DELETE CASCADE,
                        material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
                        PRIMARY KEY(thread_id, material_id));
                    CREATE TABLE IF NOT EXISTS tutor_messages (
                        id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES tutor_threads(id) ON DELETE CASCADE,
                        role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                        kind TEXT NOT NULL, body TEXT NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('pending','failed','complete')),
                        request_id TEXT UNIQUE, in_reply_to TEXT REFERENCES tutor_messages(id),
                        basis TEXT, created_at TEXT NOT NULL);
                    CREATE INDEX IF NOT EXISTS tutor_messages_thread ON tutor_messages(thread_id, created_at);
                    CREATE UNIQUE INDEX IF NOT EXISTS tutor_one_reply ON tutor_messages(in_reply_to)
                        WHERE in_reply_to IS NOT NULL;
                    CREATE TABLE IF NOT EXISTS tutor_message_sources (
                        message_id TEXT NOT NULL REFERENCES tutor_messages(id) ON DELETE CASCADE,
                        ordinal INTEGER NOT NULL, material_id TEXT REFERENCES materials(id) ON DELETE SET NULL,
                        chunk_id TEXT REFERENCES material_chunks(id) ON DELETE SET NULL,
                        material_name TEXT NOT NULL, locator TEXT NOT NULL, excerpt TEXT NOT NULL,
                        PRIMARY KEY(message_id, ordinal));
                """)
                # Em uma tentativa anterior interrompida, remova gatilhos antes de reindexar.
                db.executescript("""
                    DROP TRIGGER IF EXISTS chunks_fts_insert;
                    DROP TRIGGER IF EXISTS chunks_fts_delete;
                    DROP TRIGGER IF EXISTS chunks_fts_update;
                """)
                # Reconstitui quebras do TXT antigo quando a comparação com o original é exata.
                for row in db.execute("SELECT m.stored_name, c.id, c.locator, c.body FROM materials m "
                                      "JOIN material_chunks c ON c.material_id=m.id WHERE m.file_type='TXT'"):
                    match = re.match(r"Linhas (\d+)[–-](\d+) · trecho 1$", row["locator"])
                    original = self.path.parent / "materials" / row["stored_name"]
                    if not match or not original.is_file():
                        continue
                    content = original.read_bytes()
                    try:
                        lines = content.decode("utf-8-sig").splitlines()
                    except UnicodeDecodeError:
                        lines = content.decode("cp1252").splitlines()
                    restored = "\n".join(lines[int(match[1]) - 1:int(match[2])])
                    if " ".join(restored.split()) == " ".join(row["body"].split()):
                        db.execute("UPDATE material_chunks SET body=? WHERE id=?", (restored, row["id"]))
                db.execute("INSERT INTO material_chunks_fts(material_chunks_fts) VALUES ('rebuild')")
                db.executescript("""
                    CREATE TRIGGER IF NOT EXISTS chunks_fts_insert AFTER INSERT ON material_chunks BEGIN
                        INSERT INTO material_chunks_fts(rowid, body) VALUES (new.rowid, new.body);
                    END;
                    CREATE TRIGGER IF NOT EXISTS chunks_fts_delete AFTER DELETE ON material_chunks BEGIN
                        INSERT INTO material_chunks_fts(material_chunks_fts, rowid, body)
                            VALUES ('delete', old.rowid, old.body);
                    END;
                    CREATE TRIGGER IF NOT EXISTS chunks_fts_update AFTER UPDATE OF body ON material_chunks BEGIN
                        INSERT INTO material_chunks_fts(material_chunks_fts, rowid, body)
                            VALUES ('delete', old.rowid, old.body);
                        INSERT INTO material_chunks_fts(rowid, body) VALUES (new.rowid, new.body);
                    END;
                """)
                db.execute("PRAGMA user_version=5")
            if version < 6:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS study_memory (
                        id TEXT PRIMARY KEY,
                        subject_id TEXT NOT NULL REFERENCES subjects(id),
                        topic TEXT NOT NULL,
                        exercise TEXT NOT NULL DEFAULT '',
                        attempt TEXT NOT NULL DEFAULT '',
                        feedback TEXT NOT NULL DEFAULT '',
                        evidence TEXT NOT NULL DEFAULT '',
                        outcome TEXT NOT NULL CHECK(outcome IN ('dificil','parcial','confortavel')),
                        progress_observed TEXT NOT NULL DEFAULT '',
                        reviewed_at TEXT NOT NULL,
                        next_review_at TEXT NOT NULL,
                        version INTEGER NOT NULL DEFAULT 1);
                    CREATE INDEX IF NOT EXISTS study_memory_subject_due
                        ON study_memory(subject_id, next_review_at);
                    PRAGMA user_version=6;
                """)
            if version < 7:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS knowledge_updates (
                        version INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT NOT NULL CHECK(category IN ('academic','labor')),
                        kind TEXT NOT NULL CHECK(kind IN ('observed','trend','forecast','advice')),
                        source_name TEXT NOT NULL,
                        source_url TEXT NOT NULL,
                        published_at TEXT NOT NULL,
                        observed_until TEXT NOT NULL,
                        license TEXT NOT NULL,
                        scope TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        added_at TEXT NOT NULL);
                    PRAGMA user_version=7;
                """)
            if version < 8:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS tutor_external_sources (
                        message_id TEXT NOT NULL REFERENCES tutor_messages(id) ON DELETE CASCADE,
                        ordinal INTEGER NOT NULL,
                        title TEXT NOT NULL, url TEXT NOT NULL, excerpt TEXT NOT NULL,
                        provider TEXT NOT NULL, accessed_at TEXT NOT NULL, license TEXT NOT NULL,
                        PRIMARY KEY(message_id, ordinal));
                    PRAGMA user_version=8;
                """)
            # Após reiniciar, nenhuma chamada de provedor antiga continua ativa.
            db.execute("UPDATE tutor_messages SET status='failed' WHERE status='pending'")

    def health(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM sensor_health ORDER BY sensor")]

    def list_study_memory(self, subject_id=None):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM study_memory WHERE (? IS NULL OR subject_id=?) "
                "ORDER BY next_review_at, reviewed_at DESC", (subject_id, subject_id))]

    def list_knowledge_updates(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM knowledge_updates ORDER BY version DESC")]

    def add_knowledge_update(self, data):
        if data.get("category") not in {"academic", "labor"} or data.get("kind") not in {
                "observed", "trend", "forecast", "advice"}:
            raise ValueError("categoria ou tipo de dado inválido")
        values = {key: str(data.get(key, "")).strip() for key in (
            "source_name", "source_url", "published_at", "observed_until", "license", "scope", "summary")}
        if (any(not value for value in values.values()) or
                len(values["source_name"]) > 160 or len(values["source_url"]) > 500 or
                len(values["license"]) > 160 or len(values["scope"]) > 500 or len(values["summary"]) > 1500):
            raise ValueError("preencha fonte, datas, licença, escopo e resumo dentro dos limites")
        parsed = urlparse(values["source_url"])
        if parsed.scheme != "https" or not (parsed.hostname == "gov.br" or
                                            (parsed.hostname or "").endswith(".gov.br")):
            raise ValueError("use um endereço HTTPS de fonte oficial gov.br")
        for key in ("published_at", "observed_until"):
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", values[key]):
                    raise ValueError("formato inválido")
                parsed_date = datetime.strptime(values[key], "%Y-%m-%d").date()
            except ValueError as error:
                raise ValueError(f"{key} deve ser AAAA-MM-DD") from error
            if parsed_date > datetime.now(timezone.utc).date():
                raise ValueError("data futura não pode ser tratada como observada")
        if values["observed_until"] > values["published_at"]:
            raise ValueError("período observado não pode ser posterior à publicação")
        with self.connect() as db:
            db.execute("INSERT INTO knowledge_updates(category,kind,source_name,source_url,published_at,"
                       "observed_until,license,scope,summary,added_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (data["category"], data["kind"], *(values[key] for key in (
                           "source_name", "source_url", "published_at", "observed_until",
                           "license", "scope", "summary")), utc_now()))
            return dict(db.execute("SELECT * FROM knowledge_updates WHERE version=last_insert_rowid()").fetchone())

    def delete_knowledge_update(self, version):
        if not str(version).isdigit():
            raise ValueError("versão inválida")
        with self.connect() as db:
            if not db.execute("DELETE FROM knowledge_updates WHERE version=?", (int(version),)).rowcount:
                raise ValueError("atualização não encontrada")

    def save_study_memory(self, subject_id, topic, evidence, outcome, *, exercise="", attempt="",
                          feedback="", progress_observed="", memory_id=None, version=None):
        topic, evidence = str(topic).strip(), str(evidence).strip()
        exercise, attempt = str(exercise).strip(), str(attempt).strip()
        feedback, progress_observed = str(feedback).strip(), str(progress_observed).strip()
        if not 1 <= len(topic) <= 120 or len(evidence) > 1000:
            raise ValueError("tópico deve ter 1 a 120 caracteres e evidência até 1000")
        if any(len(text) > 2000 for text in (exercise, attempt, feedback, progress_observed)):
            raise ValueError("campos da revisão devem ter até 2000 caracteres")
        if outcome not in {"dificil", "parcial", "confortavel"}:
            raise ValueError("escolha como foi a sua tentativa")
        now = datetime.now(timezone.utc)
        days = {"dificil": 1, "parcial": 3, "confortavel": 7}[outcome]
        due = (now + timedelta(days=days)).isoformat()
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM subjects WHERE id=?", (subject_id,)).fetchone():
                raise ValueError("matéria não encontrada")
            if memory_id:
                if type(version) is not int:
                    raise ValueError("versão da revisão necessária")
                row = db.execute("UPDATE study_memory SET topic=?, exercise=?, attempt=?, feedback=?, "
                                 "evidence=?, outcome=?, progress_observed=?, reviewed_at=?, next_review_at=?, version=version+1 "
                                 "WHERE id=? AND subject_id=? AND version=?",
                                 (topic, exercise, attempt, feedback, evidence, outcome, progress_observed,
                                  now.isoformat(), due, memory_id, subject_id, version))
                if not row.rowcount:
                    raise ConflictError("revisão alterada ou removida; recarregue")
            else:
                memory_id = new_id()
                db.execute("INSERT INTO study_memory VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                           (memory_id, subject_id, topic, exercise, attempt, feedback, evidence, outcome,
                            progress_observed, now.isoformat(), due))
            return dict(db.execute("SELECT * FROM study_memory WHERE id=?", (memory_id,)).fetchone())

    def delete_study_memory(self, memory_id, version):
        if type(version) is not int:
            raise ValueError("versão da revisão necessária")
        with self.connect() as db:
            if not db.execute("DELETE FROM study_memory WHERE id=? AND version=?",
                              (memory_id, version)).rowcount:
                raise ConflictError("revisão alterada ou removida; recarregue")

    def list_events(self, limit=100):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM events ORDER BY at DESC LIMIT ?", (limit,))
            return [{**dict(row), "details": json.loads(row["details"])} for row in rows]

    def create_subject(self, name, *, at=None):
        name = str(name).strip()
        if not name or len(name) > 120:
            raise ValueError("nome da matéria deve ter 1 a 120 caracteres")
        subject = {"id": new_id(), "name": name, "archived": False,
                   "created_at": at or utc_now()}
        with self.connect() as db:
            db.execute("INSERT INTO subjects VALUES (?, ?, ?, ?)",
                       (subject["id"], name, 0, subject["created_at"]))
        return subject

    def list_subjects(self, include_archived=False):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM subjects WHERE archived=0 OR ? ORDER BY name",
                              (int(include_archived),))
            return [{**dict(row), "archived": bool(row["archived"])} for row in rows]

    def archive_subject(self, subject_id):
        with self.connect() as db:
            row = db.execute("UPDATE subjects SET archived=1 WHERE id=?", (subject_id,))
            if not row.rowcount:
                raise ValueError("matéria não encontrada")

    def update_subject(self, subject_id, *, name=None, archived=None):
        if name is None and archived is None:
            raise ValueError("nenhuma alteração informada")
        if name is not None:
            name = str(name).strip()
            if not name or len(name) > 120:
                raise ValueError("nome da matéria deve ter 1 a 120 caracteres")
        if archived is not None and type(archived) is not bool:
            raise ValueError("archived deve ser booleano")
        with self.connect() as db:
            current = db.execute("SELECT * FROM subjects WHERE id=?", (subject_id,)).fetchone()
            if current is None:
                raise ValueError("matéria não encontrada")
            db.execute("UPDATE subjects SET name=?, archived=? WHERE id=?",
                       (name if name is not None else current["name"],
                        int(archived) if archived is not None else current["archived"], subject_id))
            row = dict(db.execute("SELECT * FROM subjects WHERE id=?", (subject_id,)).fetchone())
            row["archived"] = bool(row["archived"])
            return row

    def start_session(self, subject_id, *, at=None):
        at = at or utc_now()
        session_id, interval_id = new_id(), new_id()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            subject = db.execute("SELECT archived FROM subjects WHERE id=?", (subject_id,)).fetchone()
            if subject is None or subject["archived"]:
                raise ValueError("matéria inexistente ou arquivada")
            if db.execute("SELECT 1 FROM sessions WHERE status IN ('focus','pause')").fetchone():
                raise ConflictError("já existe uma sessão em andamento")
            db.execute("INSERT INTO sessions VALUES (?, ?, 'focus', ?, NULL)",
                       (session_id, subject_id, at))
            db.execute("INSERT INTO session_intervals VALUES (?, ?, 'focus', ?, NULL)",
                       (interval_id, session_id, at))
        return self.get_session(session_id, at=at)

    def _transition(self, session_id, expected, next_status, *, at=None):
        at = at or utc_now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            session = db.execute("SELECT status FROM sessions WHERE id=?", (session_id,)).fetchone()
            if session is None:
                raise ValueError("sessão não encontrada")
            if session["status"] != expected:
                raise ConflictError(f"transição inválida: {session['status']} → {next_status}")
            interval = db.execute("SELECT id, started_at FROM session_intervals "
                                  "WHERE session_id=? AND ended_at IS NULL", (session_id,)).fetchone()
            if interval is None:
                raise RuntimeError("intervalo ativo inválido")
            if datetime.fromisoformat(at) < datetime.fromisoformat(interval["started_at"]):
                raise ValueError("horário anterior ao início do intervalo")
            db.execute("UPDATE session_intervals SET ended_at=? WHERE id=?", (at, interval["id"]))
            db.execute("UPDATE sessions SET status=?, ended_at=? WHERE id=?",
                       (next_status, at if next_status == "complete" else None, session_id))
            if next_status != "complete":
                db.execute("INSERT INTO session_intervals VALUES (?, ?, ?, ?, NULL)",
                           (new_id(), session_id, next_status, at))
        return self.get_session(session_id, at=at)

    def pause_session(self, session_id, *, at=None):
        return self._transition(session_id, "focus", "pause", at=at)

    def resume_session(self, session_id, *, at=None):
        return self._transition(session_id, "pause", "focus", at=at)

    def finish_session(self, session_id, *, at=None):
        with self.connect() as db:
            row = db.execute("SELECT status FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None or row["status"] == "complete":
            raise ConflictError("sessão inexistente ou concluída")
        return self._transition(session_id, row["status"], "complete", at=at)

    def get_session(self, session_id, *, at=None):
        at = at or utc_now()
        with self.connect() as db:
            row = db.execute("SELECT s.*, b.name AS subject_name FROM sessions s "
                             "JOIN subjects b ON b.id=s.subject_id WHERE s.id=?", (session_id,)).fetchone()
            if row is None:
                raise ValueError("sessão não encontrada")
            result = dict(row)
            intervals = [dict(item) for item in db.execute(
                "SELECT * FROM session_intervals WHERE session_id=? ORDER BY started_at", (session_id,))]
            adjustments = [dict(item) for item in db.execute(
                "SELECT * FROM session_adjustments WHERE session_id=? ORDER BY created_at", (session_id,))]
        totals = {"focus": 0, "pause": 0}
        for item in intervals:
            totals[item["kind"]] += seconds_between(item["started_at"], item["ended_at"] or at)
        result["focus_seconds"] = max(0, round(totals["focus"] + sum(a["delta_seconds"] for a in adjustments)))
        result["pause_seconds"] = round(totals["pause"])
        result["intervals"] = intervals
        result["adjustments"] = adjustments
        return result

    def list_sessions(self, limit=50):
        with self.connect() as db:
            ids = [row[0] for row in db.execute(
                "SELECT id FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,))]
        return [self.get_session(item) for item in ids]

    def adjust_session(self, session_id, delta_seconds, reason, *, at=None):
        if type(delta_seconds) is not int or not reason or not reason.strip():
            raise ValueError("ajuste inteiro e motivo são obrigatórios")
        session = self.get_session(session_id)
        if session["status"] != "complete":
            raise ConflictError("conclua a sessão antes de corrigir o tempo")
        with self.connect() as db:
            db.execute("INSERT INTO session_adjustments VALUES (?, ?, ?, ?, ?)",
                       (new_id(), session_id, delta_seconds, reason.strip(), at or utc_now()))
        return self.get_session(session_id)

    def preferences(self):
        with self.connect() as db:
            return {row["key"]: int(row["value"]) for row in db.execute(
                "SELECT key, value FROM preferences")}

    def set_weekly_goal(self, minutes):
        if type(minutes) is not int or not 1 <= minutes <= 10080:
            raise ValueError("meta semanal deve estar entre 1 e 10080 minutos")
        with self.connect() as db:
            db.execute("INSERT INTO preferences(key, value) VALUES ('weekly_goal_minutes', ?) "
                       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(minutes),))
        return self.preferences()

    def get_ui_state(self):
        with self.connect() as db:
            values = {row["key"]: row["value"] for row in db.execute("SELECT key, value FROM ui_state")}
        view = values.get("view", "inicio")
        if view not in {"inicio", "estudar", "plano", "materiais", "anotacoes", "evolucao", "configuracoes"}:
            view = "inicio"
        return {"view": view, "subject_id": values.get("subject_id") or None,
                "revision": int(values.get("revision", "0"))}

    def set_ui_state(self, view, subject_id=None, revision=None):
        if view not in {"inicio", "estudar", "plano", "materiais", "anotacoes", "evolucao", "configuracoes"}:
            raise ValueError("tela desconhecida")
        if revision is not None and (type(revision) is not int or revision < 0):
            raise ValueError("revisão de navegação inválida")
        if subject_id is not None:
            if not isinstance(subject_id, str):
                raise ValueError("matéria inválida")
            with self.connect() as db:
                if not db.execute("SELECT 1 FROM subjects WHERE id=? AND archived=0", (subject_id,)).fetchone():
                    raise ValueError("matéria inexistente ou arquivada")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM ui_state WHERE key='revision'").fetchone()
            previous = int(row[0]) if row else 0
            revision = revision if revision is not None else max(int(time.time() * 1000), previous + 1)
            if revision >= previous:
                db.executemany("INSERT INTO ui_state(key, value) VALUES (?, ?) "
                               "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                               (("view", view), ("subject_id", subject_id or ""),
                                ("revision", str(revision))))
        return self.get_ui_state()

    def progress(self, *, at=None):
        end = datetime.fromisoformat(at) if at else datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        return self.progress_between(start, end)

    def progress_between(self, since, until):
        start = datetime.fromisoformat(since) if isinstance(since, str) else since
        end = datetime.fromisoformat(until) if isinstance(until, str) else until
        if (start.tzinfo is None or end.tzinfo is None or end <= start
                or end - start > timedelta(days=8)):
            raise ValueError("intervalo de progresso inválido")
        start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
        totals = {"focus": 0.0, "pause": 0.0}
        with self.connect() as db:
            rows = db.execute("SELECT kind, started_at, COALESCE(ended_at, ?) AS ended_at "
                              "FROM session_intervals WHERE started_at < ? "
                              "AND (ended_at IS NULL OR ended_at > ?)",
                              (end.isoformat(), end.isoformat(), start.isoformat()))
            for row in rows:
                first = max(start, datetime.fromisoformat(row["started_at"]))
                last = min(end, datetime.fromisoformat(row["ended_at"]))
                totals[row["kind"]] += max(0, (last - first).total_seconds())
            adjustments = db.execute(
                "SELECT COALESCE(SUM(a.delta_seconds), 0) FROM session_adjustments a "
                "JOIN sessions s ON s.id=a.session_id "
                "WHERE s.ended_at >= ? AND s.ended_at < ?", (start.isoformat(), end.isoformat())
            ).fetchone()[0]
            completed = db.execute("SELECT COUNT(*) FROM sessions WHERE status='complete' "
                                   "AND ended_at >= ? AND ended_at < ?",
                                   (start.isoformat(), end.isoformat())).fetchone()[0]
        focus = max(0, round(totals["focus"] + adjustments))
        return {"since": start.isoformat(), "until": end.isoformat(),
                "focus_seconds": focus, "pause_seconds": round(totals["pause"]),
                "completed_sessions": completed,
                "weekly_goal_minutes": self.preferences()["weekly_goal_minutes"]}

    def create_backup(self):
        folder = self.path.parent / "backups"
        folder.mkdir(parents=True, exist_ok=True)
        name = datetime.now(timezone.utc).strftime("Ritmo-%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6] + ".zip"
        target = folder / name
        pending = folder / (name + ".db.tmp")
        try:
            with closing(sqlite3.connect(self.path, timeout=10)) as source, \
                 closing(sqlite3.connect(pending, timeout=10)) as destination:
                source.backup(destination)
            with closing(sqlite3.connect(pending)) as snapshot:
                files = [row[0] for row in snapshot.execute("SELECT stored_name FROM materials")]
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(pending, "database/ritmo.db")
                for stored_name in files:
                    if Path(stored_name).name != stored_name:
                        raise RuntimeError("nome de material inválido no banco")
                    original = self.path.parent / "materials" / stored_name
                    if not original.is_file():
                        raise RuntimeError(f"original ausente: {stored_name}")
                    archive.write(original, "materials/" + stored_name)
                config = self.path.parent / "config.json"
                if config.is_file():
                    archive.write(config, "config/config.json")
                archive.writestr("LEIA-ME.txt", "Backup local do Ritmo. Feche o aplicativo antes de restaurar. "
                                 "O banco fica em database/ritmo.db; os originais em materials/. "
                                 "Copie ambos para a pasta de dados do Ritmo após guardar uma cópia atual.\n")
        except BaseException:
            if target.exists():
                target.unlink()
            raise
        finally:
            if pending.exists():
                pending.unlink()
        return {"name": name, "path": str(target), "bytes": target.stat().st_size}

    def add_material(self, subject_id, name, source_name, file_type, stored_name,
                     size_bytes, sha256, chunks, status, error=""):
        name = str(name).strip()
        if not name or len(name) > 160:
            raise ValueError("nome do material deve ter 1 a 160 caracteres")
        if status not in {"ready", "no_text", "error"}:
            raise ValueError("estado do material inválido")
        material_id = stored_name.split(".", 1)[0]
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM subjects WHERE id=? AND archived=0", (subject_id,)).fetchone():
                raise ValueError("matéria inexistente ou arquivada")
            db.execute("INSERT INTO materials VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (material_id, subject_id, name, source_name, file_type, stored_name,
                        size_bytes, utc_now(), status, error, sha256))
            db.executemany("INSERT INTO material_chunks VALUES (?, ?, ?, ?, ?)",
                           ((new_id(), material_id, number, locator, body)
                            for number, (locator, body) in enumerate(chunks)))
        return self.get_material(material_id)

    def list_materials(self, subject_id=None):
        with self.connect() as db:
            rows = db.execute("SELECT m.*, s.name AS subject_name, "
                              "(SELECT COUNT(*) FROM material_chunks c WHERE c.material_id=m.id) AS chunk_count "
                              "FROM materials m JOIN subjects s ON s.id=m.subject_id "
                              "WHERE (? IS NULL OR m.subject_id=?) ORDER BY m.imported_at DESC",
                              (subject_id, subject_id))
            return [dict(row) for row in rows]

    def get_material(self, material_id):
        with self.connect() as db:
            row = db.execute("SELECT m.*, s.name AS subject_name FROM materials m "
                             "JOIN subjects s ON s.id=m.subject_id WHERE m.id=?", (material_id,)).fetchone()
            if row is None:
                raise ValueError("material não encontrado")
            result = dict(row)
            result["chunks"] = [dict(item) for item in db.execute(
                "SELECT id, ordinal, locator, body FROM material_chunks "
                "WHERE material_id=? ORDER BY ordinal", (material_id,))]
            return result

    def rename_material(self, material_id, name):
        name = str(name).strip()
        if not name or len(name) > 160:
            raise ValueError("nome do material deve ter 1 a 160 caracteres")
        with self.connect() as db:
            if not db.execute("UPDATE materials SET name=? WHERE id=?", (name, material_id)).rowcount:
                raise ValueError("material não encontrado")
        return self.get_material(material_id)

    def delete_material_record(self, material_id):
        with self.connect() as db:
            if not db.execute("DELETE FROM materials WHERE id=?", (material_id,)).rowcount:
                raise ValueError("material não encontrado")

    def create_note(self, subject_id, body, *, session_id=None, material_id=None, chunk_id=None,
                    selection_start=None, selection_end=None, at=None):
        body = str(body).strip()
        if not body:
            raise ValueError("anotação vazia")
        at = at or utc_now()
        note = {"id": new_id(), "subject_id": subject_id, "session_id": session_id,
                "body": body, "version": 1, "deleted": False,
                "created_at": at, "updated_at": at}
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM subjects WHERE id=?", (subject_id,)).fetchone():
                raise ValueError("matéria não encontrada")
            if session_id and not db.execute("SELECT 1 FROM sessions WHERE id=? AND subject_id=?",
                                             (session_id, subject_id)).fetchone():
                raise ValueError("sessão não pertence à matéria")
            db.execute("INSERT INTO notes VALUES (?, ?, ?, ?, 1, 0, ?, ?)",
                       (note["id"], subject_id, session_id, body, at, at))
            if material_id or chunk_id:
                if not material_id or not chunk_id:
                    raise ValueError("material e trecho são obrigatórios juntos")
                chunk = db.execute("SELECT c.body, m.subject_id FROM material_chunks c "
                                   "JOIN materials m ON m.id=c.material_id "
                                   "WHERE c.id=? AND m.id=?", (chunk_id, material_id)).fetchone()
                if chunk is None or chunk["subject_id"] != subject_id:
                    raise ValueError("trecho não pertence à matéria")
                if selection_start is None and selection_end is None:
                    quote = chunk["body"][:360]
                elif (type(selection_start) is int and type(selection_end) is int
                      and 0 <= selection_start < selection_end <= len(chunk["body"])
                      and selection_end - selection_start <= 500):
                    quote = chunk["body"][selection_start:selection_end]
                    if not quote.strip():
                        raise ValueError("selecione texto para anotar")
                else:
                    raise ValueError("seleção deve ter até 500 caracteres do trecho")
                db.execute("INSERT INTO material_note_links VALUES (?, ?, ?, ?)",
                           (note["id"], material_id, chunk_id, quote))
                if selection_start is not None:
                    db.execute("INSERT INTO note_selections VALUES (?, ?, ?)",
                               (note["id"], selection_start, selection_end))
            elif selection_start is not None or selection_end is not None:
                raise ValueError("seleção exige material e trecho")
        return note

    def list_notes(self, subject_id=None):
        with self.connect() as db:
            rows = db.execute("SELECT n.*, l.material_id, l.chunk_id, l.quote, "
                              "x.start_offset AS selection_start, x.end_offset AS selection_end, "
                              "m.name AS material_name, c.locator FROM notes n "
                              "LEFT JOIN material_note_links l ON l.note_id=n.id "
                              "LEFT JOIN note_selections x ON x.note_id=n.id "
                              "LEFT JOIN materials m ON m.id=l.material_id "
                              "LEFT JOIN material_chunks c ON c.id=l.chunk_id "
                              "WHERE n.deleted=0 AND (? IS NULL OR n.subject_id=?) "
                              "ORDER BY n.updated_at DESC", (subject_id, subject_id))
            return [dict(row) for row in rows]

    def update_note(self, note_id, body, version, *, at=None):
        body = str(body).strip()
        if not body or type(version) is not int:
            raise ValueError("texto e versão são obrigatórios")
        at = at or utc_now()
        with self.connect() as db:
            row = db.execute("UPDATE notes SET body=?, version=version+1, updated_at=? "
                             "WHERE id=? AND version=? AND deleted=0",
                             (body, at, note_id, version))
            if not row.rowcount:
                raise ConflictError("anotação alterada ou removida; recarregue antes de salvar")
            return dict(db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone())

    def delete_note(self, note_id, version):
        with self.connect() as db:
            row = db.execute("UPDATE notes SET deleted=1, version=version+1, updated_at=? "
                             "WHERE id=? AND version=? AND deleted=0", (utc_now(), note_id, version))
            if not row.rowcount:
                raise ConflictError("anotação alterada ou removida")
