import copy
import unittest


class GuidedReferenceTests(unittest.TestCase):
    def test_new_families_and_computed_student_contrast(self):
        from training.lab.guided_reference import tasks, reference
        from training.lab.calibration import battery
        from training.lab.validation import solve
        cases = tasks()
        self.assertEqual(len(cases), 9)
        self.assertFalse({t['family'] for t in cases} & {c['task']['family'] for c in battery()})
        for t in cases:
            self.assertEqual(t['expected'], solve(t['expression'], t['values']))
            self.assertNotEqual(t['expected'], t['student']['conclusion'])
            self.assertNotEqual(t['example']['values'], t['values'])
            self.assertNotEqual(t['example']['expected'], t['expected'])
            r = reference(t, [])
            self.assertTrue(r['verification_question'].endswith('?'))
            if t['kind'] == 'hint': self.assertNotIn('resultado final', r['intervention'])
            if t['kind'] == 'correction': self.assertIn(t['student']['correct_fact'], r['intervention'])

    def test_mutation_spoiler_and_question_drift_are_not_silently_accepted(self):
        from training.lab.guided_reference import tasks, reference, assess
        for t in tasks():
            r = reference(t, [])
            self.assertEqual(assess(t, r, r, 'reference')['logic']['status'], 'proved_by_construction')
            mutated = copy.deepcopy(r)
            name, value = next(iter(t['values'].items()))
            mutated['intervention'] = f'{name} = {not value}. ' + mutated['intervention']
            self.assertIn('input_fact_changed', assess(t, mutated, r, 'rewrite')['vetoes'])
            drift = {**r, 'verification_question': 'Qual é a resposta?'}
            self.assertNotEqual(assess(t, drift, r, 'rewrite')['question']['status'], 'preserved_objective')
            if t['kind'] == 'hint':
                for field in ('intervention', 'verification_question'):
                    leak = {**r, field: r[field] + ' O resultado final é ' + str(t['expected']) + '.'}
                    self.assertIn('target_solution_revealed', assess(t, leak, r, 'rewrite')['vetoes'])

    def test_observer_has_no_decision_authority(self):
        from training.lab.guided_reference import tasks, reference, assess
        t = tasks()[0]; r = reference(t, [])
        result = assess(t, r, r, 'rewrite')
        self.assertFalse(result['corpus_eligible'])
        self.assertNotIn('observer', result)
