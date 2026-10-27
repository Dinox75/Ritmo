"""Conversas locais do tutor; nenhuma chamada de modelo acontece sob transação SQLite."""

from storage.database import ConflictError, new_id, utc_now


class TutorStore:
    def __init__(self, database):
        self.database = database

    def create_thread(self, subject_id, session_id=None):
        with self.database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM subjects WHERE id=?", (subject_id,)).fetchone():
                raise ValueError("matéria não encontrada")
            if session_id and not db.execute("SELECT 1 FROM sessions WHERE id=? AND subject_id=?",
                                             (session_id, subject_id)).fetchone():
                raise ValueError("sessão não pertence à matéria")
            now = utc_now()
            db.execute("INSERT OR IGNORE INTO tutor_threads VALUES (?, ?, ?, 'duvida', ?, ?)",
                       (new_id(), subject_id, session_id, now, now))
            row = db.execute("SELECT id FROM tutor_threads WHERE subject_id=? AND session_id IS ?",
                             (subject_id, session_id)).fetchone()
        return self.get_thread(row["id"])

    def list_threads(self, subject_id):
        with self.database.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT t.*, s.started_at AS session_started_at, s.status AS session_status "
                "FROM tutor_threads t LEFT JOIN sessions s ON s.id=t.session_id "
                "WHERE t.subject_id=? ORDER BY t.updated_at DESC LIMIT 50", (subject_id,))]

    def get_thread(self, thread_id):
        with self.database.connect() as db:
            row = db.execute("SELECT t.*, s.started_at AS session_started_at, "
                             "s.status AS session_status FROM tutor_threads t "
                             "LEFT JOIN sessions s ON s.id=t.session_id WHERE t.id=?", (thread_id,)).fetchone()
            if row is None:
                raise ValueError("conversa não encontrada")
            result = dict(row)
            result["material_ids"] = [item[0] for item in db.execute(
                "SELECT material_id FROM tutor_thread_materials WHERE thread_id=? ORDER BY material_id", (thread_id,))]
        result["messages"] = self.list_messages(thread_id)
        return result

    def list_messages(self, thread_id, *, limit=100):
        with self.database.connect() as db:
            rows = [dict(row) for row in db.execute(
                "SELECT * FROM tutor_messages WHERE id IN (SELECT id FROM tutor_messages "
                "WHERE thread_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?) "
                "ORDER BY created_at, rowid", (thread_id, limit))]
            for message in rows:
                message["sources"] = [dict(item) for item in db.execute(
                    "SELECT ordinal, material_id, chunk_id, material_name, locator, excerpt "
                    "FROM tutor_message_sources WHERE message_id=? ORDER BY ordinal", (message["id"],))]
            return rows

    def set_mode(self, thread_id, mode):
        if mode not in {"duvida", "aula"}:
            raise ValueError("modo do tutor inválido")
        with self.database.connect() as db:
            if not db.execute("UPDATE tutor_threads SET mode=?, updated_at=? WHERE id=?",
                              (mode, utc_now(), thread_id)).rowcount:
                raise ValueError("conversa não encontrada")
        return self.get_thread(thread_id)

    def set_materials(self, thread_id, material_ids):
        if (not isinstance(material_ids, list) or len(material_ids) > 5
                or len(set(material_ids)) != len(material_ids)
                or any(not isinstance(item, str) for item in material_ids)):
            raise ValueError("escolha até cinco materiais diferentes")
        with self.database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            thread = db.execute("SELECT subject_id FROM tutor_threads WHERE id=?", (thread_id,)).fetchone()
            if thread is None:
                raise ValueError("conversa não encontrada")
            if material_ids:
                placeholders = ",".join("?" for _ in material_ids)
                count = db.execute(f"SELECT COUNT(*) FROM materials WHERE subject_id=? AND id IN ({placeholders})",
                                   (thread["subject_id"], *material_ids)).fetchone()[0]
                if count != len(material_ids):
                    raise ValueError("material não pertence à matéria da conversa")
            db.execute("DELETE FROM tutor_thread_materials WHERE thread_id=?", (thread_id,))
            db.executemany("INSERT INTO tutor_thread_materials VALUES (?, ?)",
                           ((thread_id, item) for item in material_ids))
            db.execute("UPDATE tutor_threads SET updated_at=? WHERE id=?", (utc_now(), thread_id))
        return self.get_thread(thread_id)

    def begin_message(self, thread_id, request_id, body):
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 100:
            raise ValueError("identificador da mensagem inválido")
        if not isinstance(body, str) or not body.strip() or len(body) > 4000:
            raise ValueError("mensagem deve ter até 4.000 caracteres")
        body = body.strip()
        with self.database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            thread = db.execute("SELECT * FROM tutor_threads WHERE id=?", (thread_id,)).fetchone()
            if thread is None:
                raise ValueError("conversa não encontrada")
            existing = db.execute("SELECT * FROM tutor_messages WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                if existing["thread_id"] != thread_id or existing["body"] != body:
                    raise ConflictError("identificador já usado para outra mensagem")
                if existing["status"] == "pending":
                    raise ConflictError("mensagem já está sendo enviada")
                if existing["status"] == "failed":
                    db.execute("UPDATE tutor_messages SET status='pending' WHERE id=?", (existing["id"],))
                return dict(existing) | {"status": "pending" if existing["status"] == "failed" else "complete"}
            last = db.execute("SELECT kind FROM tutor_messages WHERE thread_id=? AND role='assistant' "
                              "ORDER BY created_at DESC, rowid DESC LIMIT 1", (thread_id,)).fetchone()
            kind = "attempt" if thread["mode"] == "aula" and last and last["kind"] in {"lesson_prompt", "feedback"} else "question"
            message = {"id": new_id(), "thread_id": thread_id, "role": "user", "kind": kind,
                       "body": body, "status": "pending", "request_id": request_id,
                       "in_reply_to": None, "basis": None, "created_at": utc_now()}
            db.execute("INSERT INTO tutor_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(message.values()))
            db.execute("UPDATE tutor_threads SET updated_at=? WHERE id=?", (message["created_at"], thread_id))
            return message

    def complete_message(self, user_message, answer, basis, sources, mode):
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 12000:
            raise ValueError("resposta vazia ou longa demais")
        reply = {"id": new_id(), "thread_id": user_message["thread_id"], "role": "assistant",
                 "kind": ("feedback" if user_message["kind"] == "attempt" else "lesson_prompt") if mode == "aula" else "answer",
                 "body": answer.strip(), "status": "complete", "request_id": None,
                 "in_reply_to": user_message["id"], "basis": basis, "created_at": utc_now()}
        with self.database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            pending = db.execute("SELECT status FROM tutor_messages WHERE id=?", (user_message["id"],)).fetchone()
            if pending is None or pending["status"] != "pending":
                raise ConflictError("mensagem já foi respondida")
            db.execute("INSERT INTO tutor_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(reply.values()))
            db.executemany("INSERT INTO tutor_message_sources VALUES (?, ?, ?, ?, ?, ?, ?)",
                           ((reply["id"], index, source["material_id"], source["chunk_id"],
                             source["material_name"], source["locator"], source["excerpt"])
                            for index, source in enumerate(sources, 1)))
            db.execute("UPDATE tutor_messages SET status='complete' WHERE id=?", (user_message["id"],))
            db.execute("UPDATE tutor_threads SET updated_at=? WHERE id=?", (reply["created_at"], reply["thread_id"]))
        return reply

    def fail_message(self, user_message):
        with self.database.connect() as db:
            db.execute("UPDATE tutor_messages SET status='failed' WHERE id=? AND status='pending'", (user_message["id"],))
