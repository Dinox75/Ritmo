"""Inicia o executável com dados temporários, sem tocar no banco instalado."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    executable, report = map(Path, sys.argv[1:3])
    with tempfile.TemporaryDirectory(prefix="ritmo-smoke-") as folder:
        data = Path(folder) / "Ritmo"
        data.mkdir()
        (data / ".migration_disabled").write_text("1\n", encoding="ascii")
        environment = os.environ.copy()
        environment["LOCALAPPDATA"] = folder
        result = subprocess.run([str(executable), "--smoke-test", "--smoke-report", str(report)],
                                env=environment, timeout=120, check=False)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
