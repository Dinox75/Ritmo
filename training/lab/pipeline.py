"""One command: collect -> prepare -> validate -> diagnose -> train -> evaluate -> report."""
import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from collections import Counter
from pathlib import Path

from .prepare import prepare
from .proof import freeze
from .sources import collect
from .state import Run, digest, write
from .validation import deficits
from .checkpoints import training_resume

HERE = Path(__file__).parent


def diagnostics():
    try:
        gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,driver_version', '--format=csv,noheader'], capture_output=True, text=True, timeout=8).stdout.strip()
    except (OSError, subprocess.TimeoutExpired): gpu = 'nvidia-smi indisponível'
    deps = {name: importlib.util.find_spec(name) is not None for name in ('torch', 'transformers', 'peft', 'bitsandbytes', 'accelerate')}
    return {'gpu': gpu, 'dependencies': deps, 'cuda_training_tested': False,
            'note': 'nvidia-smi não comprova compatibilidade de treino. Diagnóstico não baixa pesos.'}


def endpoint(url, model):
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost'} or parsed.username or parsed.query:
        raise ValueError('endpoint deve ser HTTP de loopback; nenhum envio externo é permitido')
    def call(system, prompt):
        payload = {'model': model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}],
                   'max_tokens': 700, 'temperature': .2, 'seed': 42, 'chat_template_kwargs': {'enable_thinking': False}}
        req = urllib.request.Request(url.rstrip('/') + '/v1/chat/completions', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=180) as response:
            result = json.load(response)
        return result['choices'][0]['message']['content']
    return call


def report(run):
    state = run.snapshot
    state['phases']['report'] = 'completed'
    write(run.root / 'state.json', state)
    write(run.root / 'report.json', state)
    counts = state.get('counts', {})
    text = f"# Laboratório Ritmo\n\nEstado: **{state['status']}**. Fase: {state['phase']}.\n\n{state.get('message', '')}\n\n"
    text += f"Contagens: `{json.dumps(counts, ensure_ascii=False)}`\n\nTreino real: {state.get('training_real', False)}. Aprovação: {state.get('approval', 'inconclusivo')}.\n\n"
    text += 'Juízo pedagógico por outro modelo é uma estimativa. Regras determinísticas não comprovam sustentação semântica.\n'
    (run.root / 'report.md').write_text(text, encoding='utf-8')


def execute(args, generator=None, judge=None):
    if args.run.resolve().is_relative_to(HERE.parent.parent):
        raise ValueError('use --run fora do repositório; originais/corpus/pesos não devem entrar no Git')
    catalog_path = args.catalog.resolve()
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    local = {str(Path(folder).resolve()): {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(folder).iterdir()) if p.is_file()} for folder in args.local_dir}
    code_files = [*sorted(HERE.glob('*.py')), HERE.parent / 'train_qlora.py']
    code_hash = digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in code_files})
    config = {'catalog': digest(catalog), 'local_inputs': local, 'mode': args.mode, 'limit': args.limit,
              'seed': 42, 'generator': 'qwen3-1.7b', 'judge': 'qwen3-4b', 'code': code_hash,
              'model_root': str(args.model_root.resolve()) if args.model_root else None,
              'generator_url': args.generator_url, 'judge_url': args.judge_url,
              'base_revision': '70d244cc86ccca08cf5af4e1e306ecf908b1ad5e', 'max_hours': args.max_hours,
              'pilot_proof': str(args.pilot_proof.resolve()) if args.pilot_proof else None}
    config['generation'] = {'temperature': .2, 'seed': 42, 'max_tokens': 700, 'enable_thinking': False}
    if args.model_root:
        from local_ai.installer import manifest
        config['model_files'] = {key: value for key, value in manifest()['models'].items() if key in {'qwen3-1.7b-q8_0', 'qwen3-4b-q4_k_m'}}
    root = args.run.resolve(); root.mkdir(parents=True, exist_ok=True)
    lock_path = root / '.worker.lock'
    try: descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError('execução travada por .worker.lock; confira PID e processo antes de remover um lock abandonado')
    os.write(descriptor, str(os.getpid()).encode()); os.close(descriptor)
    runtime = None; finished = threading.Event(); run = None
    try:
        run = Run(root, config, args.resume)
        artifact_lock = root / 'preparation-lock.json'
        if args.resume and artifact_lock.exists():
            saved = json.loads(artifact_lock.read_text(encoding='utf-8'))
            current = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in saved}
            if current != saved: raise ValueError('corpus/candidatos incompatíveis na retomada')
        absolute_deadline = run.snapshot['started'] + args.max_hours * 3600
        def expired(): return time.time() >= absolute_deadline - 600
        if expired(): raise TimeoutError('orçamento de tempo esgotado; retomada não reinicia o relógio')
        def heartbeat():
            while not finished.wait(10):
                try: run.beat(resources=diagnostics())
                except OSError: pass
        worker = threading.Thread(target=heartbeat, daemon=True); worker.start()
        proof_path = root / 'proof.json'
        if proof_path.exists():
            proof = json.loads(proof_path.read_text(encoding='utf-8'))
            stored = proof.pop('sha256')
            if digest(proof) != stored or stored != run.snapshot.get('proof_sha256'):
                raise ValueError('prova selada foi alterada; execução recusada')
        else:
            stored = freeze(proof_path)
        run.event('collect', proof_sha256=stored, message='Prova fixada antes de qualquer geração.')
        sources, refused = collect(catalog, root / 'originals', args.local_dir,
                                   lambda name, status: run.event('collect', message=f'{name}: {status}'))
        source_hash = digest([{k: v for k, v in s.items() if k != 'text'} for s in sources])
        if args.resume and run.snapshot.get('source_hash') not in {None, source_hash}: raise ValueError('fontes incompatíveis na retomada')
        run.event('collect', 'completed', f'{len(sources)} fontes lidas; {len(refused)} recusadas.', source_hash=source_hash)
        if generator is None:
            if args.generator_url or args.judge_url:
                if not args.generator_url or not args.judge_url or args.generator_url == args.judge_url:
                    raise ValueError('configure dois endpoints locais distintos: gerador 1.7B e juiz 4B')
                generator = endpoint(args.generator_url, 'qwen3-1.7b'); judge = endpoint(args.judge_url, 'qwen3-4b')
            else:
                if not args.model_root: raise ValueError('informe --model-root ou dois endpoints de modelos locais')
                from local_ai.runtime import LocalRuntime
                runtime = LocalRuntime(args.model_root)
                def call(model):
                    def complete(system, prompt):
                        runtime.start(model)
                        payload = {'model': model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}],
                                   'max_tokens': 700, 'temperature': .2, 'seed': 42, 'stream': False,
                                   'chat_template_kwargs': {'enable_thinking': False}}
                        with runtime._urlopen('/v1/chat/completions', json.dumps(payload).encode(), timeout=180) as response:
                            result = json.load(response)
                        with (root / 'model-metrics.jsonl').open('a', encoding='utf-8') as file:
                            file.write(json.dumps({'model': model, 'usage': result.get('usage'), 'timings': result.get('timings'), 'finish_reason': result['choices'][0].get('finish_reason')}) + '\n')
                        return result['choices'][0]['message']['content']
                    return complete
                generator, judge = call('qwen3-1.7b-q8_0'), call('qwen3-4b-q4_k_m')
        def progress(**fields):
            if expired(): raise TimeoutError('prazo da preparação esgotado')
            detail = fields.pop('detail', '')
            run.event('prepare', message=detail, counts={**run.snapshot.get('counts', {}), **fields})
        run.event('prepare', message='Candidatos locais; documentos como dados; juiz distinto.')
        rows, candidates = prepare(sources, root, generator, judge, args.limit, progress,
                                   stop=expired)
        if runtime: runtime.stop()
        run.event('prepare', 'completed', message='Candidatos e decisões persistidos.')
        missing = deficits(rows, 30)
        reasons = Counter(reason for item in candidates for reason in item.get('reasons', []))
        counts = {'sources_read': len(sources), 'sources_refused': len(refused), 'generated': len(candidates),
                  'approved': len(rows), 'rejected': len(candidates) - len(rows), 'missing': missing,
                  'reasons': dict(reasons), 'splits': dict(Counter(row['split'] for row in rows))}
        run.event('validate', 'completed', message='Triagem independente encerrada.', counts=counts)
        write(artifact_lock, {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ('corpus.jsonl', 'candidates.json')})
        write(root / 'corpus-lock.json', {'sha256': hashlib.sha256((root / 'corpus.jsonl').read_bytes()).hexdigest(), 'source_hash': source_hash, 'proof_sha256': stored})
        diagnostic = diagnostics(); write(root / 'diagnostics.json', diagnostic)
        run.event('diagnose', 'completed', message=diagnostic['gpu'], resources=diagnostic)
        if any(missing.values()):
            run.event('train', 'blocked', 'Corpus insuficiente. Não duplicar candidatos para preencher a meta; ampliar famílias/fontes e qualidade.', action='Veja faltantes e motivos da triagem. Nenhum peso baixado ou treinado.')
            return run
        if args.mode == 'prepare':
            run.event('train', 'waiting', 'Preparação concluída; treino não solicitado.', action='Executar piloto com o corpus fixado em uma nova execução.')
            return run
        if not all(diagnostic['dependencies'].values()):
            run.event('train', 'blocked', 'Dependências CUDA/QLoRA ausentes.', action='Criar ambiente Linux isolado conforme training/lab/REMOTE.md.')
            return run
        if args.mode == 'long':
            pilot = json.loads(args.pilot_proof.read_text(encoding='utf-8')) if args.pilot_proof else {}
            corpus_hash = hashlib.sha256((root / 'corpus.jsonl').read_bytes()).hexdigest()
            if pilot.get('resume_exercised') is not True or pilot.get('dataset_sha256') != corpus_hash or pilot.get('base_revision') != config['base_revision']:
                run.event('train', 'blocked', 'Execução longa exige piloto com retomada CUDA comprovada e corpus idêntico.', action='Interromper e retomar piloto10; fornecer provenance.json em --pilot-proof.')
                return run
        command = [sys.executable, '-m', 'training.train_qlora', '--dataset', str(root / 'corpus.jsonl'), '--output', str(root / 'training'),
                   '--screening', str(root / 'candidates.json'),
                   '--proof', str(proof_path), '--max-steps', str(10 if args.mode == 'pilot' else 10000),
                   '--max-seconds', str(int(args.max_hours * 3600) - 600), '--deadline', str(absolute_deadline), '--evaluate']
        if training_resume(root / 'training', args.resume): command.append('--resume')
        if args.judge_url: command.extend(['--judge-url', args.judge_url])
        elif args.model_root: command.extend(['--model-root', str(args.model_root)])
        run.event('train', message='Treino real solicitado; consulte checkpoints e métricas.')
        with (root / 'training.log').open('a', encoding='utf-8') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            try:
                if child.wait(timeout=max(1, absolute_deadline - time.time())) != 0: raise RuntimeError('treinador falhou; consulte training.log e o último checkpoint')
            except BaseException:
                child.terminate()
                try: child.wait(timeout=30)
                except subprocess.TimeoutExpired: child.kill(); child.wait()
                raise
        run.event('evaluate', 'completed', 'Pares base/adaptador gerados no mesmo processo de inferência.', training_real=True)
        evaluation = json.loads((root / 'training' / 'comparison.json').read_text(encoding='utf-8'))
        run.event('report', 'completed', evaluation['conclusion'], approval=evaluation['conclusion'])
        return run
    except KeyboardInterrupt:
        if run: run.event(run.snapshot['phase'], 'interrupted', 'Interrompido; candidatos persistidos. Reexecute com --resume.', action='Checkpoint CUDA só existe se o treinador conseguiu salvá-lo.')
        return run
    except Exception as error:
        if run: run.event(run.snapshot['phase'], 'failed', str(error), action='Consulte diagnóstico; corrija a causa e retome com entradas idênticas.')
        else: raise
        return run
    finally:
        finished.set()
        if 'worker' in locals(): worker.join(timeout=12)
        if runtime: runtime.stop()
        lock_path.unlink(missing_ok=True)
        if run: report(run)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--catalog', type=Path, default=HERE / 'catalog.json')
    p.add_argument('--local-dir', type=Path, action='append', default=[])
    p.add_argument('--mode', choices=['prepare', 'pilot', 'long'], default='prepare')
    p.add_argument('--limit', type=int, default=12)
    p.add_argument('--max-hours', type=float, default=8)
    p.add_argument('--model-root', type=Path)
    p.add_argument('--generator-url'); p.add_argument('--judge-url')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--pilot-proof', type=Path)
    return p


def main():
    args = parser().parse_args()
    if not 1 <= args.limit <= 2000 or not 0.2 <= args.max_hours <= 8: raise ValueError('limites: 1..2000 candidatos e 0.2..8 horas')
    run = execute(args)
    if run: print(json.dumps({'status': run.snapshot['status'], 'message': run.snapshot.get('message'), 'report': str(run.root / 'report.md')}, ensure_ascii=False))
    if run and run.snapshot['status'] in {'failed', 'interrupted', 'blocked'}:
        raise SystemExit({'failed': 1, 'blocked': 2, 'interrupted': 130}[run.snapshot['status']])


if __name__ == '__main__': main()
