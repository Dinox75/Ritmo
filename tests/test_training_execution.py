import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path


class TrainingExecutionTests(unittest.TestCase):
    def test_checkpoint_manifest_changes_are_rejected(self):
        from training.lab.checkpoints import bind_inputs
        with tempfile.TemporaryDirectory() as root:
            bind_inputs(Path(root), {'corpus': 'a', 'seed': 42}, False)
            bind_inputs(Path(root), {'corpus': 'a', 'seed': 42}, True)
            with self.assertRaisesRegex(ValueError, 'incompat'):
                bind_inputs(Path(root), {'corpus': 'b', 'seed': 42}, True)

    def test_panel_is_read_only_and_escapes_untrusted_text(self):
        from training.lab.panel import make_server
        from training.lab.state import write
        with tempfile.TemporaryDirectory() as root:
            write(Path(root) / 'state.json', {'status': 'blocked', 'message': '<script>evil()</script>'})
            server = make_server(root, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            url = f'http://127.0.0.1:{server.server_port}'
            try:
                data = json.load(urllib.request.urlopen(url + '/api'))
                self.assertEqual(data['state']['status'], 'blocked')
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(urllib.request.Request(url + '/api', data=b'{}'))
                self.assertEqual(error.exception.code, 405)
                with self.assertRaises(urllib.error.HTTPError): urllib.request.urlopen(url + '/../../config/local.json')
                script = urllib.request.urlopen(url + '/panel.js').read().decode()
                self.assertNotIn('innerHTML', script)
            finally: server.shutdown(); server.server_close(); thread.join()

    def test_interrupted_preparation_resumes_without_regeneration(self):
        from training.lab.prepare import prepare
        from test_training_lab import sample
        with tempfile.TemporaryDirectory() as root:
            sources = []
            for cat in ('matter', 'pedagogy'):
                sources.append({**sample()[cat], 'category': cat, 'split': 'train'})
            def generator(system, prompt):
                return json.dumps({'prompt': 'Qual condição deve ser examinada neste intervalo?',
                                   'answer': 'Compare separadamente cada limite antes de combinar as condições. Qual comparação você verificaria primeiro?', 'result': True})
            def judge(*args): return json.dumps({'approved': True, 'support': True, 'hint': True, 'partial_credit': True})
            with self.assertRaises(KeyboardInterrupt):
                prepare(sources, root, generator, judge, 2, stop=lambda: (Path(root) / 'candidates.json').exists())
            first = json.loads((Path(root) / 'candidates.json').read_text(encoding='utf8'))[0]
            rows, candidates = prepare(sources, root, generator, judge, 2)
            self.assertEqual(len(candidates), 2)
            self.assertEqual(candidates[0], first)

    def test_generator_error_persisted(self):
        from training.lab.prepare import prepare
        from test_training_lab import sample
        with tempfile.TemporaryDirectory() as root:
            sources = [{**sample()[cat], 'category': cat, 'split': 'train'} for cat in ('matter', 'pedagogy')]
            def fail(*args): raise RuntimeError('modelo indisponível')
            rows, candidates = prepare(sources, root, fail, fail, 1)
            self.assertEqual(rows, [])
            self.assertIn('modelo indisponível', candidates[0]['reasons'][0])

    def test_comparison_without_real_training_is_inconclusive(self):
        from training.lab.evaluate import conclude
        self.assertEqual(conclude([], training_real=False), 'inconclusivo: nenhum treino real')
        pairs = [{'category': 'hostile', 'base': {'judgment': {'logic': True, 'hostile': True}},
                  'adapter': {'judgment': {'logic': False, 'hostile': False}}}]
        self.assertIn('reprovado', conclude(pairs, training_real=True))

    def test_incomplete_judgments_never_make_a_candidate(self):
        from training.lab.evaluate import conclude
        pairs = [{'category': 'hint', 'base': {'judgment': {'logic': False}},
                  'adapter': {'judgment': {'logic': True, 'hint': None, 'sources': None}}, 'change': 'melhora'} for _ in range(30)]
        pairs[0]['adapter']['judgment'].update(hint=True, sources=True, correction=True, hostile=True)
        self.assertIn('inconclusivo', conclude(pairs, True))

    def test_authored_label_cannot_bypass_duplicates_or_sealed_proof(self):
        from training.train_qlora import read_dataset
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'data.jsonl'
            rows = [{'id': str(i), 'split': 'train' if i < 200 else 'validation',
                     'prompt': 'Mesma pergunta duplicada', 'answer': 'Mesma resposta duplicada',
                     'source': 'Ritmo authored', 'license': 'CC0-1.0'} for i in range(230)]
            path.write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf8')
            with self.assertRaises(ValueError): read_dataset(path, {'cases': [{}] * 30})

    def test_train_resume_does_not_follow_prepare_resume_blindly(self):
        from training.lab.checkpoints import training_resume
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            self.assertFalse(training_resume(root, True))
            (root / 'input-lock.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'checkpoint'):
                training_resume(root, True)

    def test_real_extractors_docx_and_image_only_pdf(self):
        import zipfile
        from pypdf import PdfWriter
        from training.lab.sources import read_text
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); docx = root / 'lesson.docx'
            with zipfile.ZipFile(docx, 'w') as archive:
                archive.writestr('[Content_Types].xml', '<Types/>')
                archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>E exige as duas condições; OU exige pelo menos uma condição verdadeira.</w:t></w:r></w:p></w:body></w:document>')
            self.assertIn('OU exige', read_text(docx))
            pdf = root / 'image.pdf'; writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
            with pdf.open('wb') as file: writer.write(file)
            with self.assertRaisesRegex(ValueError, 'texto'): read_text(pdf)

    def test_uncertain_source_never_downloaded_and_hash_change_refused(self):
        from unittest.mock import patch
        from training.lab.sources import collect
        with tempfile.TemporaryDirectory() as root, patch('training.lab.sources.fetch') as fetch:
            sources, refused = collect({'sources': [{'id': 'uncertain', 'license': 'unknown'}]}, Path(root) / 'originals')
            self.assertEqual(sources, []); self.assertEqual(len(refused), 1); fetch.assert_not_called()
            fetch.return_value = b'changed'
            sources, refused = collect({'sources': [{'id': 'changed', 'license': 'CC-BY-4.0', 'license_url': 'https://example.org/license', 'author': 'author', 'url': 'https://example.org/source', 'sha256': 'old'}]}, Path(root) / 'originals')
            self.assertEqual(sources, []); self.assertIn('hash mudou', refused[0]['reason'])

    def test_run_inside_repository_refused_before_writing(self):
        from training.lab.pipeline import execute, parser, HERE
        args = parser().parse_args(['--run', str(HERE / 'do-not-create')])
        with self.assertRaisesRegex(ValueError, 'fora do repositório'): execute(args)
        self.assertFalse(args.run.exists())
