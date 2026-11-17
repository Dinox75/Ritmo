"""Inicia o executável com dados temporários, sem tocar no banco instalado."""

import os
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from native_windows_evidence import lifecycle_records


def main():
    executable, report = map(Path, sys.argv[1:3])
    with tempfile.TemporaryDirectory(prefix="ritmo-smoke-") as folder:
        data = Path(folder) / "Ritmo"
        data.mkdir()
        (data / ".migration_disabled").write_text("1\n", encoding="ascii")
        environment = os.environ.copy()
        environment["LOCALAPPDATA"] = folder
        environment['RITMO_MODEL_DIR'] = str(Path(folder)/'no-models')
        evidence={'ready':False,'phase':'executable','returncode':None}
        try:
            result = subprocess.run([str(executable), "--smoke-test", "--smoke-report", str(report)],
                                    env=environment, timeout=120, check=False)
            evidence['returncode']=result.returncode
            return result.returncode
        except (OSError,subprocess.TimeoutExpired) as error:
            evidence['error_type']=type(error).__name__
            return 1
        finally:
            evidence['lifecycle']=lifecycle_records(data/'ritmo.log')
            if not report.is_file() or evidence['returncode'] != 0:
                report.parent.mkdir(parents=True,exist_ok=True)
                report.write_text(json.dumps(evidence,indent=2),encoding='utf8')


if __name__ == "__main__":
    raise SystemExit(main())
