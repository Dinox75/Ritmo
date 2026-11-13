import json
from pathlib import Path
from .state import digest, write


def training_resume(root, requested):
    root = Path(root)
    if not requested or not (root / 'input-lock.json').exists(): return False
    if not list(root.glob('checkpoint-*/trainer_state.json')):
        raise ValueError('treino iniciado sem checkpoint completo; preservar diagnóstico e usar nova execução')
    return True


def bind_inputs(root, manifest, resume):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    path = root / 'input-lock.json'
    if path.exists():
        if not resume: raise ValueError('treino já existe; use --resume')
        if json.loads(path.read_text(encoding='utf-8')) != manifest:
            raise ValueError('checkpoint incompatível: corpus, prova, configuração, versões ou pesos mudaram')
    elif resume: raise ValueError('retomada sem manifesto original')
    else: write(path, manifest)
    return digest(manifest)
