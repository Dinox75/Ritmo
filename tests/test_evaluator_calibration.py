import unittest


class CalibrationTests(unittest.TestCase):
    def test_archived_sources_require_matching_bytes_and_excerpt(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from scripts.report_lab_calibration import restore_sources
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); body = 'Uma regra sintética suficientemente longa para verificar o excerto de estudo.'
            (root / 'rule.txt').write_text(body, encoding='utf8')
            source = {'file': 'rule.txt', 'sha256': hashlib.sha256(body.encode()).hexdigest(), 'excerpt': 'regra sintética'}
            candidate = {'matter': dict(source), 'pedagogy': dict(source)}
            restored, checked = restore_sources(candidate, root)
            self.assertNotIn('text', candidate['matter'])
            self.assertIn(source['excerpt'], restored['matter']['text'])
            self.assertTrue(checked['matter']['excerpt_present'])
            (root / 'rule.txt').write_text(body + ' alterado', encoding='utf8')
            with self.assertRaises(AssertionError): restore_sources(candidate, root)

    def test_full_decision_is_not_a_single_true_criterion(self):
        from scripts.report_lab_calibration import summarize
        row = {'expected': True, 'screen': True, 'judge_effective': True,
               'reasons': ['tamanho_campos_invalido'], 'judge': {'approved': False},
               'effective_judge': {'approved': False, 'overrides': []}}
        result = summarize([row])
        for evaluator in ('screen', 'judge_raw', 'judge_effective'):
            self.assertEqual(result[evaluator]['good_accepted'], 0)

    def test_battery_is_separate_minimal_pairs_with_computed_keys(self):
        from training.lab.calibration import battery, judge_payload
        from training.lab.validation import solve
        cases = battery()
        self.assertEqual(len(cases), 24)
        dev = {c['task']['family'] for c in cases if c['split'] == 'development'}
        reserved = {c['task']['family'] for c in cases if c['split'] == 'reserved'}
        self.assertFalse(dev & reserved)
        for c in cases:
            self.assertEqual(c['logic_key'], solve(c['task']['expression'], c['task']['values']))
            self.assertNotIn('18 <= 15', str(c))
            self.assertNotIn('expected', judge_payload(c))
            self.assertNotIn('reference', judge_payload(c))
        for split in ('development', 'reserved'):
            for name in {c['pair'] for c in cases}:
                good, bad = [c for c in cases if c['pair'] == name and c['split'] == split]
                self.assertEqual(good['task'], bad['task'])
                self.assertEqual(sum(good[k] != bad[k] for k in ('intervention','verification_question')), 1)

    def test_input_boolean_is_not_target_solution(self):
        from training.lab.exercises import build_tasks
        from training.lab.pedagogy import check_fields
        t = next(t for t in build_tasks() if t['family'] == 'negation_gate' and t['kind'] == 'hint')
        q = 'Como a negação transforma o valor de bloqueado?'
        self.assertNotIn('dica_entrega_solucao', check_fields(t, 'O dado bloqueado = False já foi fornecido. Aplique a negação antes de concluir.', q))
        self.assertIn('dica_entrega_solucao', check_fields(t, 'O resultado da expressão é True. Aplique a negação antes de concluir.', q))

    def test_parrot_question_and_repeated_example(self):
        from training.lab.exercises import build_tasks
        from training.lab.pedagogy import check_fields
        t = build_tasks()[0]
        self.assertIn('pergunta_sem_verificacao_contextual', check_fields(t, 'Compare cada limite separadamente antes de combinar as condições.', 'Qual é o valor de t >= lo and t <= hi?'))
        t = dict(t, kind='explanation')
        self.assertIn('explicacao_sem_exemplo_distinto', check_fields(t, 'Por exemplo, ' + t['exercise'].replace('?', '.') , 'Como o sinal >= muda a inclusão do limite inferior?'))

    def test_code_authority_cannot_be_overridden_by_judge(self):
        from training.lab.calibration import constrain_verdict
        from training.lab.exercises import build_tasks
        task = build_tasks()[0]
        raw = {'approved': True, 'logic_correct': True, 'target_result': False, 'reason': 'confiante'}
        v = constrain_verdict(raw, task, [])
        self.assertFalse(v['approved'])
        self.assertIn('juiz_contradiz_gabarito', v['overrides'])
        self.assertTrue(raw['approved'])

    def test_full_screen_preserves_boolean_input_exception(self):
        from training.lab.exercises import build_tasks
        from training.lab.prepare import candidate_from_output
        from training.lab.validation import screen
        from test_training_lab import sample
        task = next(t for t in build_tasks() if t['family'] == 'negation_gate' and t['kind'] == 'hint')
        row = candidate_from_output(task, {'intervention': 'O dado bloqueado = False já foi fornecido. Aplique a negação antes de concluir.',
                                          'verification_question': 'Como a negação transforma o valor de bloqueado?'}, sample()['matter'], sample()['pedagogy'])
        self.assertNotIn('dica_entrega_solucao', screen(row, [], {'approved': True}))

    def test_service_judge_cannot_replace_the_code_key(self):
        import json
        from training.lab.exercises import build_tasks
        from training.lab.prepare import candidate_from_output, judge_candidate
        from test_training_lab import sample
        task = build_tasks()[0]
        row = candidate_from_output(task, {'intervention': 'Compare cada limite separadamente antes de combinar as condições.',
                                          'verification_question': 'Como o sinal >= muda a inclusão do limite inferior?'}, sample()['matter'], sample()['pedagogy'])
        def judge(*unused):
            return json.dumps({'approved': True, 'support': True, 'logic_correct': True, 'question_useful': True,
                               'hint': True, 'partial_credit': True, 'new_example': True, 'target_result': not task['expected'], 'reason': 'confiante'})
        raw, verdict = judge_candidate(row, task, judge)
        self.assertTrue(json.loads(raw)['approved'])
        self.assertFalse(verdict['approved'])
        self.assertIn('juiz_contradiz_gabarito', verdict['overrides'])
