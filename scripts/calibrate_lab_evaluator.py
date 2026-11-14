"""Local-only calibration. Freeze expectations, then dev, lock, reserve and rescore unchanged outputs."""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from training.lab.calibration import battery, judge_payload, CALIBRATED_JUDGE, constrain_verdict, confusion, REASONS
from training.lab.state import write, digest
from training.lab.prepare import JUDGE, parse


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--phase', choices=['freeze', 'baseline', 'development', 'lock', 'reserved', 'replay'], required=True)
    p.add_argument('--model-root', type=Path)
    p.add_argument('--gpu-layers', type=int, choices=range(100), default=99)
    a = p.parse_args(); root = a.run; root.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[1]
    paths = ['docs/training-lab-results/validated.json', 'docs/training-lab-results/proof.json', 'docs/training-lab-two-stage/results.json', 'docs/training-lab-two-stage/metrics.json']
    preserved = {x: hashlib.sha256((repo / x).read_bytes()).hexdigest() for x in paths}
    def rules():
        return {x: hashlib.sha256((repo / x).read_bytes()).hexdigest() for x in ['training/lab/pedagogy.py', 'training/lab/validation.py', 'training/lab/calibration.py', 'training/lab/prepare.py', 'scripts/calibrate_lab_evaluator.py']}
    if a.phase == 'freeze':
        if (root / 'expectations.json').exists(): raise ValueError('expectations already frozen')
        write(root / 'expectations.json', {'cases': battery(), 'preserved': preserved,
              'gate': 'Reserved: zero false positives and >=90% good accepted for BOTH screen and effective judge; no raw target contradiction. No tuning after reserve.'})
        write(root / 'freeze.json', {'sha256': digest(json.loads((root / 'expectations.json').read_text(encoding='utf8'))), 'time': time.time()})
        print('expectations frozen'); return
    frozen = json.loads((root / 'expectations.json').read_text(encoding='utf8'))
    assert preserved == frozen['preserved'], 'historical artifacts changed'
    assert digest(frozen) == json.loads((root / 'freeze.json').read_text())['sha256']
    if a.phase == 'lock':
        if (root / 'rules-lock.json').exists(): raise ValueError('rules already locked')
        write(root / 'rules-lock.json', {'rules': rules(), 'judge': digest(CALIBRATED_JUDGE), 'time': time.time()})
        print('rules locked'); return
    if a.phase in ('reserved', 'replay'):
        lock = json.loads((root / 'rules-lock.json').read_text())
        assert lock['rules'] == rules() and lock['judge'] == digest(CALIBRATED_JUDGE), 'rules changed after lock'
    from training.lab.pedagogy import check_fields
    checker = check_fields
    if a.phase == 'baseline':
        old = subprocess.check_output(['git', 'show', 'e2c639b:training/lab/pedagogy.py'], cwd=repo).decode('utf8')
        ns = {'__package__': 'training.lab'}; exec(compile(old, '<historical-checker>', 'exec'), ns); checker = ns['check_fields']
    from local_ai.runtime import LocalRuntime
    runtime = LocalRuntime(a.model_root, gpu_layers=a.gpu_layers)
    model = 'qwen3-4b-q4_k_m'
    rows = []; output = root / (a.phase + '.json')
    if output.exists(): raise ValueError('phase output exists; refuse overwrite')
    system = CALIBRATED_JUDGE if a.phase != 'baseline' else JUDGE + '\nRetorne também new_example (exemplo realmente distinto) e target_result (resultado do exercício, não da tentativa). Critérios não aplicáveis: true.'
    def call(payload):
        try: runtime.start(model)
        except Exception as error:
            write(root / (a.phase + '-startup-error-' + str(int(time.time())) + '.json'),
                  {'error': str(error), 'log': runtime._recent_log, 'gpu_layers': a.gpu_layers})
            raise
        body = {'model': model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
                'temperature': .2, 'seed': 42, 'max_tokens': 400, 'stream': False, 'chat_template_kwargs': {'enable_thinking': False}}
        start = time.perf_counter()
        with runtime._urlopen('/v1/chat/completions', json.dumps(body, ensure_ascii=False).encode(), timeout=180) as response: data = json.load(response)
        raw = data['choices'][0]['message']['content']
        metric = {'raw': raw, 'seconds': time.perf_counter() - start, 'usage': data.get('usage'), 'timings': data.get('timings'), 'model': model, 'gpu_layers': a.gpu_layers}
        # Persist raw even when parse fails.
        with (root / (a.phase + '-calls.jsonl')).open('a', encoding='utf8') as f: f.write(json.dumps({'payload': payload, **metric}, ensure_ascii=False) + '\n')
        try: verdict = parse(raw)
        except (ValueError, TypeError): verdict = {'approved': False, 'reason': 'invalid JSON'}
        return verdict, metric
    try:
        if a.phase == 'replay':
            original = json.loads((repo / 'docs/training-lab-two-stage/results.json').read_text(encoding='utf8'))
            from training.lab.validation import screen
            for pair in original['pairs']:
                for method in ('legacy', 'two_stage'):
                    item = pair[method]; candidate = item.get('candidate'); task = pair['task']
                    if not candidate: raise ValueError('all original outputs must have candidate fields')
                    reasons = screen(candidate, [], {'approved': True})
                    case = {'task': task, 'intervention': candidate['intervention'], 'verification_question': candidate['verification_question'],
                            'source': {k: candidate[k] for k in ('matter', 'pedagogy')}}
                    v, metric = call(judge_payload(case)); effective = constrain_verdict(v, task, reasons)
                    accepted = not reasons and effective.get('approved') is True
                    old_reasons = item.get('reasons', [])
                    rows.append({'id': pair['id'] + '-' + method, 'family': pair['family'], 'kind': pair['kind'], 'method': method,
                                 'raw_sha256': hashlib.sha256(item['raw'].encode()).hexdigest(), 'intervention': case['intervention'], 'verification_question': case['verification_question'],
                                 'old_accepted': item.get('accepted'), 'accepted': accepted, 'screen_reasons': reasons,
                                 'screen_added': sorted(set(reasons) - set(old_reasons)), 'screen_removed': sorted(set(old_reasons) - set(reasons) - {'juiz_nao_executado_pretriagem','juiz_nao_aprovou'}),
                                 'old_judge': item.get('judge'), 'judge': v, 'effective_judge': effective, 'metric': metric,
                                 'decision_origin': {'screen_changed': set(reasons) != set(r for r in old_reasons if not r.startswith('juiz_')), 'judge_now_measured': item.get('judge') is None, 'judge_changed': item.get('judge') != v}})
                    write(output, {'rows': rows, 'complete': len(rows) == 60, 'historical_preserved': preserved})
                    print(f'replay {len(rows)}/60', flush=True)
        else:
            split = 'reserved' if a.phase == 'reserved' else 'development'
            for case in frozen['cases']:
                if case['split'] != split: continue
                reasons = checker(case['task'], case['intervention'], case['verification_question'])
                v, metric = call(judge_payload(case)); effective = constrain_verdict(v, case['task'], reasons)
                criterion = case['criterion']
                screen_ok = not any(r in reasons for r in REASONS[criterion])
                judge_ok = v.get(criterion) is True
                rows.append({'id': case['id'], 'criterion': criterion, 'expected': case['expected'], 'screen': screen_ok,
                             'judge_raw': judge_ok, 'judge_effective': judge_ok and not effective['overrides'],
                             'reasons': reasons, 'judge': v, 'effective_judge': effective, 'metric': metric})
                write(output, {'rows': rows, 'confusion': confusion(rows), 'rules': rules(), 'judge_prompt': system, 'complete': len(rows) == 12})
                print(f'{a.phase} {len(rows)}/12', flush=True)
    finally: runtime.stop()


if __name__ == '__main__': main()
