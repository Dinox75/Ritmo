import copy
import unittest


class TwoStageTests(unittest.TestCase):
    def test_families_have_coherent_misconceptions_and_contrasting_examples(self):
        from training.lab.exercises import build_tasks
        from training.lab.validation import solve, signature
        tasks = build_tasks()
        self.assertEqual(len(tasks), 30)
        self.assertEqual(len({t['family'] for t in tasks}), 10)
        for task in tasks:
            self.assertEqual(task['expected'], solve(task['expression'], task['values']))
            self.assertNotEqual(task['expected'], task['student']['conclusion'])
            self.assertEqual(task['student']['conclusion'], solve(task['student']['expression'], task['values']))
            self.assertNotEqual(task['values'], task['example']['values'])
            self.assertNotEqual(task['expected'], task['example']['expected'])
            self.assertNotIn('18', task['exercise'])
        train = {signature(t) for t in tasks if t['split'] == 'train'}
        validation = {signature(t) for t in tasks if t['split'] == 'validation'}
        self.assertFalse(train & validation)

    def test_no_exercise_or_student_formula_reuses_sealed_exam_family(self):
        import json
        from pathlib import Path
        from training.lab.exercises import build_tasks
        from training.lab.validation import signature
        proof = json.loads((Path(__file__).parents[1] / 'docs/training-lab-results/proof.json').read_text(encoding='utf8'))
        reserved = {signature(c) for c in proof['cases']}
        for task in build_tasks():
            self.assertNotIn(signature(task), reserved)
            self.assertNotIn(signature(task['student']), reserved)

    def test_question_mark_and_generic_question_are_not_useful(self):
        from training.lab.pedagogy import check_fields
        from training.lab.exercises import build_tasks
        task = build_tasks()[0]
        for question in ['Entendeu?', 'Tudo certo?', 'Qual é a resposta?', 'Qual é a capital do Brasil?',
                         'A condição lo < t <= hi foi interpretada como lo < t < hi?']:
            reasons = check_fields(task, 'Compare cada limite separadamente antes de combinar as condições.', question)
            self.assertIn('pergunta_sem_verificacao_contextual', reasons)
        self.assertEqual(check_fields(task, 'Compare cada limite separadamente antes de combinar as condições.',
                                     'Como o sinal >= muda a inclusão do limite inferior?'), [])
        self.assertEqual(check_fields(task, 'Compare cada limite separadamente antes de combinar as condições.',
                                     'Se t coincide com lo, como o sinal >= muda a inclusão do limite inferior?'), [])

    def test_spoiler_in_either_field_and_false_math_rejected(self):
        from training.lab.pedagogy import check_fields
        from training.lab.exercises import build_tasks
        task = build_tasks()[0]
        for intervention, question in [('A condição é verdadeira; você acertou.', 'Por que o limite é incluído?'),
                                       ('Compare os dois limites antes de decidir.', 'Como você explica que a condição é verdadeira?')]:
            self.assertIn('dica_entrega_solucao', check_fields(task, intervention, question))
        task = copy.deepcopy(task); task['kind'] = 'correction'
        self.assertIn('afirmacao_logica_incorreta', check_fields(task, 'Você acertou o valor. Mas 8 < 2 é verdadeiro, pois este é o limite.', 'Como o limite inferior entra na comparação?'))

    def test_separate_fields_remain_separate_and_no_question_repair(self):
        from training.lab.prepare import candidate_from_output
        from training.lab.exercises import build_tasks
        task = build_tasks()[0]
        output = {'intervention': 'Compare os limites separadamente.', 'verification_question': 'Entendeu'}
        row = candidate_from_output(task, output, {}, {})
        self.assertEqual(row['verification_question'], 'Entendeu')
        self.assertNotIn('?', row['answer'])
        with self.assertRaises(ValueError): candidate_from_output(task, {**output, 'result': True}, {}, {})

    def test_runtime_gpu_budget_is_explicit_and_default_unchanged(self):
        import tempfile
        from local_ai.runtime import LocalRuntime
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(LocalRuntime(root).gpu_layers, 99)
            self.assertEqual(LocalRuntime(root, gpu_layers=24).gpu_layers, 24)
            with self.assertRaises(ValueError): LocalRuntime(root, gpu_layers=-1)

    def test_independent_judge_must_assess_question_and_logic(self):
        import json
        from training.lab.prepare import candidate_from_output, judge_candidate
        from training.lab.exercises import build_tasks
        from test_training_lab import sample
        task = build_tasks()[0]
        row = candidate_from_output(task, {'intervention': 'Compare os dois limites separadamente antes de combinar as condições.',
                                         'verification_question': 'Como o sinal >= muda a inclusão do limite inferior?'}, sample()['matter'], sample()['pedagogy'])
        def incomplete(*args): return json.dumps({'approved': True, 'support': True, 'reason': 'aparenta correta'})
        _, verdict = judge_candidate(row, task, incomplete)
        self.assertFalse(verdict['approved'])

    def test_common_screen_does_not_treat_different_interventions_as_duplicate(self):
        from training.lab.prepare import candidate_from_output
        from training.lab.exercises import build_tasks
        from training.lab.validation import screen
        from test_training_lab import sample
        tasks = build_tasks()
        sources = sample()
        row = candidate_from_output(tasks[0], {'intervention': 'Compare cada limite separadamente antes de combinar as condições.',
                                              'verification_question': 'Como o sinal >= muda a inclusão do limite inferior?'}, sources['matter'], sources['pedagogy'])
        self.assertEqual(screen(row, [], {'approved': True}), [])
        self.assertIn('pergunta_duplicada', screen(row, [row], {'approved': True}))
        correction = candidate_from_output(tasks[1], {'intervention': 'Você acertou t = 2. Mas usou > em vez de >=; este último inclui a igualdade porque o limite não é estrito.',
                                                     'verification_question': 'Como a igualdade altera o teste no limite inferior?'}, sources['matter'], sources['pedagogy'])
        self.assertNotIn('pergunta_duplicada', screen(correction, [row], {'approved': True}))

    def test_changed_or_missing_exercise_values_are_rejected(self):
        from training.lab.generation_results import exercise_preserved, split_legacy
        from training.lab.exercises import build_tasks
        task = build_tasks()[0]
        self.assertTrue(exercise_preserved(task['exercise'], task))
        self.assertFalse(exercise_preserved(task['exercise'].replace("'t': 2", "'t': 9"), task))
        self.assertFalse(exercise_preserved('Condição: t >= lo and t <= hi. Valores: t=2.5, lo=2, hi=8.', task))
        self.assertFalse(exercise_preserved('Condição: t >= lo and t <= hi. Valores: t=2 + 1, lo=2, hi=8.', task))
        self.assertFalse(exercise_preserved('Compare os limites e explique sua resposta.', task))
        text = 'Considere a versão 1.7. Como o limite se aplica ao valor 1.5?'
        answer, question = split_legacy(text)
        self.assertEqual(question, 'Como o limite se aplica ao valor 1.5?')

    def test_summary_keeps_pending_separate_from_rejection(self):
        from training.lab.generation_results import summarize
        from training.lab.exercises import build_tasks
        tasks = build_tasks()
        s = summarize([{'task': tasks[0], 'accepted': True}, {'task': tasks[1], 'accepted': False}, {'task': tasks[2], 'accepted': None}])
        self.assertEqual(s['by_family']['inclusive_range']['approved'], 1)
        self.assertEqual(s['by_family']['inclusive_range']['rejected'], 1)
        self.assertEqual(s['by_family']['inclusive_range']['pending'], 1)
        self.assertEqual(s['by_cell']['inclusive_range|hint']['approved'], 1)

    def test_conjunction_does_not_choose_inclusive_or_exclusive_boundary(self):
        from training.lab.pedagogy import check_fields
        from training.lab.exercises import build_tasks
        task = build_tasks()[5]
        self.assertIn('regra_logica_incorreta', check_fields(task, "O operador 'and' excluirá a igualdade nas fronteiras.",
                                                          'Como o limite superior altera a comparação?'))
