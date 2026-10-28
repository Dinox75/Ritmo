"""Confere backup SQLite e migração numa cópia temporária, sem imprimir dados pessoais."""

import sqlite3
import sys
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storage.database import Database


def inspect(path):
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE '%_fts%' ORDER BY name")]
        counts = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                  for table in tables}
        sessions = connection.execute("SELECT status, COUNT(*) FROM sessions GROUP BY status").fetchall()
        return counts, sessions, connection.execute("PRAGMA user_version").fetchone()[0]


def main(backup, current):
    before, sessions, version = inspect(current)
    with tempfile.TemporaryDirectory(prefix="ritmo-backup-migration-") as folder:
        restored = Path(folder) / "ritmo.db"
        with zipfile.ZipFile(backup) as archive:
            restored.write_bytes(archive.read("database/ritmo.db"))
        archived, archived_sessions, archived_version = inspect(restored)
        assert (before, sessions, version) == (archived, archived_sessions, archived_version)
        Database(restored).initialize()
        migrated, migrated_sessions, migrated_version = inspect(restored)
        assert migrated_version == 8 and migrated_sessions == sessions
        assert all(migrated.get(table) == count for table, count in before.items())
        print("Backup consistente; migracao 7 -> 8 preservou contagens e estados de sessao.")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
