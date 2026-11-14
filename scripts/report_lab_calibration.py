"""Report frozen calibration; no inference, rule tuning or corpus export."""
import argparse
import copy
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from training.lab.state import write, digest


def restore_sources(candidate, originals):
    from training.lab.sources import read_text
    candidate = copy.deepcopy(candidate); checks = {}
    for kind in ('matter', 'pedagogy'):
        source = candidate[kind]
        assert Path(source['file']).name == source['file']
        path = originals / source['file']
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == source['sha256'], 'original arquivado incompatível'
        source['text'] = read_text(path)
        assert source['excerpt'] in source['text'], 'excerto ausente no original'
        checks[kind] = {'file': source['file'], 'sha256': actual, 'excerpt_present': True}
    return candidate, checks


def summarize(rows):
    out = {}
    for evaluator in ('screen', 'judge_raw', 'judge_effective'):
        good = [r for r in rows if r['expected']]
        bad = [r for r in rows if not r['expected']]
        actual = lambda r: not r['reasons'] if evaluator == 'screen' else r['judge' if evaluator == 'judge_raw' else 'effective_judge'].get('approved') is True
        out[evaluator] = {'good_accepted': sum(actual(r) for r in good), 'good_total': len(good),
                          'bad_accepted': sum(actual(r) for r in bad), 'bad_total': len(bad),
                          'target_contradictions': sum('juiz_contradiz_gabarito' in r['effective_judge']['overrides'] for r in rows)}
    return out


def main():
    p = argparse.ArgumentParser(); p.add_argument('--run', type=Path, required=True)
    p.add_argument('--originals', type=Path, required=True, help='snapshots originais já arquivados; hashes precisam corresponder às fontes')
    p.add_argument('--publish', type=Path); a = p.parse_args(); root = a.run
    repo = Path(__file__).resolve().parents[1]
    expectations = json.loads((root / 'expectations.json').read_text(encoding='utf8'))
    assert digest(expectations) == json.loads((root / 'freeze.json').read_text())['sha256']
    for name, expected in json.loads((root / 'rules-lock.json').read_text())['rules'].items():
        assert hashlib.sha256((repo / name).read_bytes()).hexdigest() == expected
    for name, expected in expectations['preserved'].items():
        assert hashlib.sha256((repo / name).read_bytes()).hexdigest() == expected
    phases = {name: json.loads((root / (name + '.json')).read_text(encoding='utf8')) for name in ('baseline','development','reserved')}
    cases = {c['id']: c for c in expectations['cases']}
    for phase_name, phase in phases.items():
        expected_ids = {c['id'] for c in expectations['cases'] if c['split'] == ('reserved' if phase_name == 'reserved' else 'development')}
        assert phase['complete'] and len(phase['rows']) == len(expected_ids)
        assert {r['id'] for r in phase['rows']} == expected_ids
        phase['full_acceptance'] = summarize(phase['rows'])
        for row in phase['rows']: row['case'] = cases[row['id']]
    reserved = phases['reserved']['full_acceptance']
    passed = all(v['bad_accepted'] == 0 and v['good_accepted'] / v['good_total'] >= .9 and v['target_contradictions'] == 0
                 for k,v in reserved.items() if k in ('screen','judge_effective'))
    # Criterion metrics are diagnostics, not full acceptance.
    passed = passed and all(not r['effective_judge']['overrides'] or r['effective_judge']['overrides'] == ['codigo_detectou_erro_logico'] for r in phases['reserved']['rows'])
    replay_file = root / 'replay.json'
    replay = json.loads(replay_file.read_text(encoding='utf8')) if replay_file.exists() else {'rows': [], 'complete': False}
    original = json.loads((repo / 'docs/training-lab-two-stage/results.json').read_text(encoding='utf8'))
    expected_raws = {p['id'] + '-' + m: hashlib.sha256(p[m]['raw'].encode()).hexdigest() for p in original['pairs'] for m in ('legacy','two_stage')}
    originals = {p['id'] + '-' + m: (p['task'],p[m]['candidate']) for p in original['pairs'] for m in ('legacy','two_stage')}
    original_items = {p['id'] + '-' + m: p[m] for p in original['pairs'] for m in ('legacy','two_stage')}
    from training.lab.validation import screen
    for row in replay['rows']:
        assert expected_raws[row['id']] == row['raw_sha256']
        task, candidate = originals[row['id']]
        candidate, source_checks = restore_sources(candidate, a.originals)
        # Published historical JSON deliberately omits full source text. Restore
        # verified inputs to the SAME locked screen; retain the incomplete-input
        # measurement and all raw judge calls unchanged. No new rule or inference.
        row['screen_before_source_restoration'] = row['screen_reasons']
        row['source_restoration'] = source_checks
        row['screen_reasons'] = screen(candidate, [], {'approved': True})
        assert set(row['screen_before_source_restoration']) == set(row['screen_reasons']) | {'excerto_inexistente'}, 'restauração alterou outra checagem'
        old_reasons = original_items[row['id']]['reasons']
        row['screen_added'] = sorted(set(row['screen_reasons']) - set(old_reasons))
        row['screen_removed'] = sorted(set(old_reasons) - set(row['screen_reasons']) - {'juiz_nao_executado_pretriagem','juiz_nao_aprovou'})
        row['accepted'] = not row['screen_reasons'] and row['effective_judge'].get('approved') is True
        row['decision_origin']['screen_changed'] = set(row['screen_reasons']) != {r for r in old_reasons if not r.startswith('juiz_')}
        row['task'] = task
        row['evidence'] = {kind: {k:v for k,v in candidate[kind].items() if k != 'text'} for kind in ('matter','pedagogy')}
    replay['summary'] = {'evaluated': len(replay['rows']), 'accepted': sum(r['accepted'] for r in replay['rows']),
                         'full_decision_changes': sum(r['old_accepted'] != r['accepted'] for r in replay['rows']),
                         'screen_reason_changes': sum(r['decision_origin']['screen_changed'] for r in replay['rows']),
                         'newly_measured_judges': sum(r['decision_origin']['judge_now_measured'] for r in replay['rows'])}
    result = {'decision': 'A avaliação ainda precisa de correção' if not passed else 'Calibração limitada aprovada; ainda não é evidência de melhora do gerador',
              'generation_pilot_allowed': passed, 'new_generation_executed': False, 'training': False,
              'metric_scope': 'Confusão: somente critério-alvo. Full acceptance: todas as regras/flags aplicáveis, medida separadamente.',
              'source_restoration_scope': 'JSON histórico omitira texto completo: a primeira triagem de replay marcou excerto_inexistente. Restaurados os originais por hash e reaplicadas as MESMAS regras congeladas. Medida inicial e todos os juízos brutos mantidos; nenhum julgamento refeito.',
              'baseline_scope': 'Prompt antigo com campos adicionais new_example/target_result e payload comum novo; baseline de compatibilidade, não reprodução exata do juiz antigo. Veto lógico reportado separadamente do bruto.',
              'limitations': ['Reserva pequena: seis pares mínimos em duas famílias; sem estimativa ampla de confiabilidade.',
                             'Reavaliação isola cada candidato (previous=[]); não revalida duplicação/contaminação entre candidatos. Nenhum é promovido ao corpus.',
                             'Triagem por padrões pode bloquear paráfrases válidas e não prova semântica completa.',
                             'Hash inicial da bateria não inclui pesos; modelos locais permanecem os já instalados; manifesto e dependências adicionais arquivados no relatório.'],
              'phases': phases, 'replay': replay, 'preserved': expectations['preserved'],
              'expectations': expectations, 'freeze': json.loads((root / 'freeze.json').read_text()),
              'rules_lock': json.loads((root / 'rules-lock.json').read_text())}
    result['additional_dependencies_after_run'] = {}
    for name in ('training/lab/exercises.py','training/lab/generation_results.py','training/lab/sources.py','local_ai/runtime.py','local_ai/models.json'):
        data = (repo / name).read_bytes()
        historical = subprocess.check_output(['git','show','e2c639b:' + name], cwd=repo)
        # Normalize Git checkout line endings for this supplementary check.
        result['additional_dependencies_after_run'][name] = {'sha256': hashlib.sha256(data).hexdigest(),
              'unchanged_since_e2c639b': data.replace(b'\r\n',b'\n') == historical.replace(b'\r\n',b'\n')}
    write(root / 'calibration.json', result)
    if a.publish:
        assert replay['complete'] and len(replay['rows']) == 60
        assert {r['id'] for r in replay['rows']} == set(expected_raws)
        a.publish.mkdir(parents=True, exist_ok=True)
        for name in ('calibration.json','expectations.json','freeze.json','rules-lock.json'):
            (a.publish / name).write_bytes((root / name).read_bytes())
    write(root / 'state.json', {'status': 'completed' if replay['complete'] else 'running', 'phase': 'report',
                              'heartbeat': time.time(), 'started': result['freeze']['time'], 'training_real': False,
                              'message': result['decision'], 'counts': {'generated': 0, 'approved': 0}, 'phases': {}})
    print(json.dumps({'decision': result['decision'], 'full_acceptance': {k:v['full_acceptance'] for k,v in phases.items()}, 'replay': replay['summary']}, ensure_ascii=True, indent=2))


if __name__ == '__main__': main()
