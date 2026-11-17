import copy
import tempfile
import unittest
from pathlib import Path


class TrainingLabTests(unittest.TestCase):
    def test_safe_logic_and_no_arbitrary_execution(self):
        from training.lab.validation import solve
        self.assertFalse(solve('x > 0 and x <= y', {'x': 18, 'y': 15}))
        self.assertTrue(solve('not (x < y) or x == 0', {'x': 2, 'y': 2}))
        for text in ["__import__('os').system('echo bad')", 'x ** 99999', 'x.attr', '[x]']:
            with self.assertRaises(ValueError):
                solve(text, {'x': 1})

    def test_uncertain_license_and_no_text(self):
        from training.lab.sources import approved, read_text
        self.assertFalse(approved({'license': 'unknown'}))
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'empty.txt'; path.write_text('  ')
            with self.assertRaisesRegex(ValueError, 'texto'):
                read_text(path)

    def test_citations_duplicates_leakage_and_independent_judge(self):
        from training.lab.validation import screen
        row = sample()
        self.assertEqual(screen(row, [], {'approved': True}), [])
        row['matter']['excerpt'] = 'não existe'
        self.assertIn('excerto_inexistente', screen(row, [], {'approved': True}))
        row = sample()
        self.assertIn('pergunta_duplicada', screen(row, [row], {'approved': True}))
        variant = copy.deepcopy(row); variant['prompt'] = 'Outra formulação de pergunta'
        variant['split'] = 'validation'
        self.assertIn('contaminacao_familia', screen(variant, [row], {'approved': True}))
        self.assertIn('juiz_nao_aprovou', screen(row, [], None))
        variant = copy.deepcopy(row); variant.update(family='renamed', split='validation', expression='a > 0 and a <= b', values={'a': 18, 'b': 15})
        self.assertIn('contaminacao_familia', screen(variant, [row], {'approved': True}))
        row['answer'] = 'A resposta é falso. Por quê?'; row['kind'] = 'hint'
        self.assertIn('dica_entrega_solucao', screen(row, [], {'approved': True}))

    def test_known_false_interval_and_spoiled_hint_rejected_even_if_judge_approves(self):
        from training.lab.validation import screen
        row = sample(); row.update(kind='hint', expression='x >= lo and x <= hi',
                                   values={'x': 5, 'lo': 2, 'hi': 8}, result=True,
                                   answer='Neste caso x é 5, que está dentro do intervalo. Confira os limites.')
        self.assertIn('dica_entrega_solucao', screen(row, [], {'approved': True}))
        row.update(kind='explanation', expression='x < lo or x > hi', values={'x': 10, 'lo': 2, 'hi': 8},
                   result=True, answer='Neste caso x é 10, que está dentro do intervalo [2, 8]. O que você acha?')
        self.assertIn('conclusao_intervalo_incorreta', screen(row, [], {'approved': True}))

    def test_insufficient_corpus(self):
        from training.lab.validation import deficits
        self.assertEqual(deficits([], 30), {'train': 200, 'validation': 30, 'test': 0})

    def test_frozen_exam_has_thirty_unique_cases(self):
        import json
        from training.lab.proof import freeze
        from training.lab.state import digest
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'proof.json'; seal = freeze(path)
            proof = json.loads(path.read_text(encoding='utf8'))
            self.assertEqual(len(proof['cases']), 30)
            self.assertEqual(len({(r['expression'], str(r['values'])) for r in proof['cases']}), 30)
            self.assertEqual(digest({k: v for k, v in proof.items() if k != 'sha256'}), seal)

    def test_resume_rejects_changed_inputs_and_panel_staleness(self):
        from training.lab.state import Run, view
        with tempfile.TemporaryDirectory() as root:
            run = Run(Path(root), {'seed': 42})
            run.event('prepare', 'running', 'um arquivo')
            self.assertEqual(view(run.snapshot, now=run.snapshot['heartbeat'] + 200)['status'], 'stale')
            Run(Path(root), {'seed': 42}, resume=True)
            with self.assertRaisesRegex(ValueError, 'incompat'):
                Run(Path(root), {'seed': 43}, resume=True)
            run.event('prepare', 'interrupted', 'interrupção')
            self.assertEqual(view(run.snapshot)['status'], 'interrupted')


def sample():
    return {'id': 'one', 'split': 'train', 'family': 'and-bank', 'kind': 'correction',
            'prompt': '18 é positivo, então posso retirar 18 com saldo 15?',
            'answer': 'Você acertou que 18 é positivo. Mas 18 supera 15; E exige as duas condições. Qual condição falta?',
            'expression': 'x > 0 and x <= y', 'values': {'x': 18, 'y': 15}, 'result': False,
            'matter': {'id': 'm', 'sha256': 'abc', 'text': 'E exige ambas as condições.', 'excerpt': 'E exige ambas as condições.', 'license': 'CC-BY-4.0', 'license_url': 'https://example.org/license', 'author': 'Autor', 'url': 'https://example.org/m'},
            'pedagogy': {'id': 'p', 'sha256': 'def', 'text': 'Give feedback.', 'excerpt': 'Give feedback.', 'license': 'CC-BY-4.0', 'license_url': 'https://example.org/license', 'author': 'Autor', 'url': 'https://example.org/p'}}
