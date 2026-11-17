import hashlib
import json
import os
import time
import threading
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, path)


def view(snapshot, now=None):
    result = dict(snapshot)
    result['age_seconds'] = round((now or time.time()) - result.get('heartbeat', 0))
    if result.get('status') == 'running' and result['age_seconds'] > 120:
        result['status'] = 'stale'
    result['elapsed_seconds'] = round((now or time.time()) - result.get('started', time.time()))
    return result


class Run:
    def __init__(self, root, config, resume=False):
        self._lock = threading.RLock()
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / 'state.json'
        fingerprint = digest(config)
        if path.exists():
            if not resume:
                raise ValueError('execução já existe; use --resume ou outro --run')
            self.snapshot = json.loads(path.read_text(encoding='utf-8'))
            if self.snapshot['fingerprint'] != fingerprint:
                raise ValueError('retomada incompatível: configuração, código ou entradas mudaram')
        else:
            self.snapshot = {'fingerprint': fingerprint, 'config': config, 'started': time.time(),
                             'heartbeat': time.time(), 'status': 'waiting', 'phase': 'collect',
                             'counts': {}, 'phases': {}, 'training_real': False, 'approval': 'inconclusivo'}
            write(path, self.snapshot)

    def event(self, phase, status='running', message='', **fields):
        with self._lock:
            self.snapshot.update(phase=phase, status=status, message=message, heartbeat=time.time(), **fields)
            self.snapshot['phases'][phase] = status
            write(self.root / 'state.json', self.snapshot)
            with (self.root / 'events.jsonl').open('a', encoding='utf-8') as file:
                file.write(json.dumps({'time': time.time(), 'phase': phase, 'status': status,
                                       'message': message, **fields}, ensure_ascii=False) + '\n')

    def beat(self, **fields):
        with self._lock:
            self.snapshot.update(heartbeat=time.time(), **fields)
            write(self.root / 'state.json', self.snapshot)
