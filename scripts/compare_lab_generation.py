"""Local generation pilot only. Never imports/calls Trainer, downloads weights or trains."""
import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from training.lab.exercises import build_tasks
from training.lab.generation_results import summarize, split_legacy
from training.lab.prepare import SYSTEM, parse, select_sources, private_context, candidate_from_output, judge_candidate
from training.lab.sources import collect
from training.lab.state import Run, write, digest
from training.lab.validation import screen, deficits
from training.lab.pipeline import diagnostics, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True); p.add_argument('--model-root', type=Path, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--limit', type=int, default=30)
    p.add_argument('--catalog', type=Path, help='catálogo arquivado para reprodução exata; padrão training/lab/catalog.json')
    p.add_argument('--replay-from', type=Path, help='reusar bruto real já recebido; julgar novamente sem selecionar respostas')
    p.add_argument('--judge-gpu-layers', type=int, default=24)
    args = p.parse_args()
    repo = Path(__file__).resolve().parents[1]; root = args.run.resolve()
    if root.is_relative_to(repo): raise ValueError('execução deve ficar fora do Git')
    baseline_sha = subprocess.check_output(['git', '-C', str(args.baseline), 'rev-parse', 'HEAD'], text=True).strip()
    if not baseline_sha.startswith('8d02ce1'): raise ValueError('base de comparação deve ser 8d02ce1')
    old_file = args.baseline / 'training/lab/prepare.py'
    legacy_system = next(ast.literal_eval(n.value) for n in ast.parse(old_file.read_text(encoding='utf8')).body
                         if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SYSTEM' for t in n.targets))
    preserved = [repo / 'docs/training-lab-results/validated.json', repo / 'docs/training-lab-results/proof.json']
    preserved_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved}
    tasks = build_tasks(args.limit)
    from local_ai.runtime import LocalRuntime
    from local_ai.installer import manifest
    catalog = json.loads((args.catalog or repo / 'training/lab/catalog.json').read_text(encoding='utf8'))
    config = {'mode': 'generation_comparison_only', 'training_allowed': False, 'baseline': baseline_sha,
              'legacy_prompt': hashlib.sha256(legacy_system.encode()).hexdigest(),
              'new_prompt': hashlib.sha256(SYSTEM.encode()).hexdigest(), 'tasks_sha256': digest(tasks),
              'catalog_sha256': digest(catalog), 'preserved': preserved_hashes, 'limit': args.limit,
              'parameters': {'temperature': .2, 'seed': 42, 'max_tokens': 700, 'thinking': False},
              'models': manifest()['models']}
    config['rubric_sha256'] = digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                      [repo / 'training/lab/validation.py', repo / 'training/lab/pedagogy.py']})
    config['gpu_layers'] = {'generator': 99, 'judge': args.judge_gpu_layers}
    replay = None
    if args.replay_from:
        replay_file = args.replay_from / 'generation-comparison.json'
        replay = json.loads(replay_file.read_text(encoding='utf8'))
        for field in ('legacy_prompt', 'new_prompt', 'tasks_sha256', 'catalog_sha256', 'parameters', 'models'):
            if replay['config'][field] != config[field]: raise ValueError('bruto de replay incompatível: ' + field)
        if len(replay['pairs']) != len(tasks): raise ValueError('replay deve incluir todos os casos, sem seleção')
        config['replay_sha256'] = hashlib.sha256(replay_file.read_bytes()).hexdigest()
    run = Run(root, config)
    write(root / 'catalog-used.json', catalog)
    shutil.copyfile(preserved[1], root / 'proof.json')
    run.snapshot['proof_sha256'] = json.loads(preserved[1].read_text(encoding='utf8'))['sha256']
    runtime = LocalRuntime(args.model_root); finished = threading.Event()
    def beat():
        while not finished.wait(8): run.beat(resources=diagnostics())
    worker = threading.Thread(target=beat, daemon=True); worker.start()
    result = {'config': config, 'criteria': 'mesma triagem de campos/lógica/fontes e juiz independente para ambas as abordagens',
              'training_real': False, 'pairs': [], 'summaries': {}}
    groups = {'legacy': [], 'two_stage': []}
    def call(model, system, content, task, strategy, phase):
        runtime.start(model)
        payload = {'model': model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': content}],
                   'temperature': .2, 'seed': 42, 'max_tokens': 700, 'stream': False,
                   'chat_template_kwargs': {'enable_thinking': False}}
        start = time.perf_counter()
        with runtime._urlopen('/v1/chat/completions', json.dumps(payload, ensure_ascii=False).encode(), timeout=180) as response: data = json.load(response)
        raw = data['choices'][0]['message']['content']
        with (root / 'model-metrics.jsonl').open('a', encoding='utf8') as f:
            f.write(json.dumps({'family': task['family'], 'kind': task['kind'], 'strategy': strategy, 'phase': phase,
                                'model': model, 'seconds': time.perf_counter() - start, 'raw': raw,
                                'usage': data.get('usage'), 'timings': data.get('timings'),
                                'finish_reason': data['choices'][0].get('finish_reason')}, ensure_ascii=False) + '\n')
        return raw
    def save():
        for strategy in groups: result['summaries'][strategy] = summarize(groups[strategy])
        write(root / 'generation-comparison.json', result)
        write(root / 'candidates.json', groups['two_stage'])
        write(root / 'legacy-candidates.json', groups['legacy'])
    try:
        run.event('collect', message='Piloto local sem treino; referência0/12 e prova preservadas.')
        sources, refused = collect(catalog, root / 'originals')
        run.event('collect', 'completed', f'{len(sources)} fontes lidas, {len(refused)} recusadas.')
        for task in tasks:
            matter, pedagogy = select_sources(sources, task)
            pair = {'id': digest(task)[:16], 'family': task['family'], 'kind': task['kind'], 'task': task}
            # Generate both responses before changing to the judge: identical sampling and evidence.
            for strategy in ('legacy', 'two_stage'):
                item = {'index': task['index'], 'task': task, 'strategy': strategy}
                started = time.perf_counter()
                run.event('prepare', message=f'{task["label"]} / {task["kind"]} / {strategy}', counts={'index': task['index'], 'generated': len(groups['two_stage'])})
                try:
                    def generate(system, context):
                        if replay:
                            original = next(p for p in replay['pairs'] if p['id'] == pair['id'])[strategy]
                            item['raw_reused'] = True
                            return original['raw']
                        return call('qwen3-1.7b-q8_0', system, json.dumps(context, ensure_ascii=False), task, strategy, 'generate')
                    if strategy == 'legacy':
                        context = {**task, 'expected': task['expected'], 'matter': matter['excerpt'], 'pedagogy': pedagogy['excerpt']}
                        raw = generate(legacy_system, context)
                        item['raw'] = raw
                        value = parse(raw)
                        if set(value) != {'prompt', 'answer', 'result'}: raise ValueError('contrato antigo inválido')
                        intervention, question = split_legacy(value['answer'])
                        row = candidate_from_output(task, {'intervention': intervention, 'verification_question': question}, matter, pedagogy)
                        row.update(prompt=value['prompt'], result=value['result'], generated_prompt=value['prompt'])
                    else:
                        raw = generate(SYSTEM, private_context(task, matter, pedagogy))
                        item['raw'] = raw
                        value = parse(raw); row = candidate_from_output(task, value, matter, pedagogy)
                    item.update(raw=raw, candidate=row, accepted=None, reasons=['aguardando_triagem'])
                except Exception as error:
                    item.update(accepted=False, reasons=['erro_geracao: ' + str(error)])
                item['generation_seconds'] = time.perf_counter() - started
                if replay:
                    original = next(p for p in replay['pairs'] if p['id'] == pair['id'])[strategy]
                    item['replay_processing_seconds'] = item['generation_seconds']
                    item['generation_seconds'] = original['generation_seconds']
                pair[strategy] = item
                write(root / 'in-progress-pair.json', pair)
                groups[strategy].append(item)
            result['pairs'].append(pair); save()
        runtime.stop()
        time.sleep(2)
        runtime.gpu_layers = args.judge_gpu_layers
        for pair in result['pairs']:
            task = pair['task']
            for strategy in ('legacy', 'two_stage'):
                item = pair[strategy]; verdict = None
                if item.get('candidate'):
                    row = item['candidate']; previous = [i['candidate'] for i in groups[strategy] if i.get('accepted')]
                    reasons = screen(row, previous, {'approved': True})
                    if not reasons:
                        run.event('validate', message=f'Verificador4B / {task["label"]} / {strategy}')
                        try:
                            judge = lambda system, content: call('qwen3-4b-q4_k_m', system, content, task, strategy, 'judge')
                            item['judge_raw'], verdict = judge_candidate(row, task, judge)
                            reasons = screen(row, previous, verdict)
                        except Exception as error: reasons = ['erro_verificador: ' + str(error)]
                    else: reasons.append('juiz_nao_executado_pretriagem')
                    item.update(accepted=not reasons, reasons=reasons, judge=verdict)
                item['seconds'] = item['generation_seconds']
            save()
            run.beat(counts={'generated': len(groups['two_stage']), 'approved': sum(i.get('accepted') is True for i in groups['two_stage']),
                             'rejected': sum(i.get('accepted') is False for i in groups['two_stage'])})
        rows = [i['candidate'] for i in groups['two_stage'] if i['accepted']]
        with (root / 'corpus.jsonl').open('w', encoding='utf8') as f:
            for row in rows: f.write(json.dumps(row, ensure_ascii=False) + '\n')
        result['recommendation'] = 'Revisar respostas e descartes antes de ampliar o corpus; nenhum treino autorizado neste piloto.'
        result['preserved_hashes_after'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved}
        if result['preserved_hashes_after'] != preserved_hashes: raise ValueError('referência/prova alteradas')
        save()
        counts = {'sources_read': len(sources), 'sources_refused': len(refused), 'generated': len(groups['two_stage']),
                  'approved': len(rows), 'rejected': len(groups['two_stage']) - len(rows),
                  'missing': deficits(rows, 30), 'reasons': result['summaries']['two_stage']['reasons']}
        run.event('report', 'completed', 'Comparação da geração concluída. Sem treino; consulte as falhas e a recomendação.',
                  counts=counts, approval='não avaliado: nenhum adaptador', action='Não contratar GPU nem ampliar contagens sem revisar a qualidade.')
    except KeyboardInterrupt:
        run.event('prepare', 'interrupted', 'Piloto interrompido; gerações já recebidas foram preservadas.')
    except Exception as error:
        run.event('prepare', 'failed', str(error)); raise
    finally:
        finished.set(); worker.join(timeout=10); runtime.stop(); report(run)
    print(json.dumps(result['summaries'], ensure_ascii=False))


if __name__ == '__main__': main()
