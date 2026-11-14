import tempfile
import unittest
from pathlib import Path


class BooleanLessonTests(unittest.TestCase):
    def setUp(self):
        from storage.database import Database
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=Database(Path(self.tmp.name)/'test.db');self.db.initialize()

    def test_default_disabled_and_no_table_created(self):
        from utils.config import load_config
        from tutor.boolean_lesson import BooleanLesson
        self.assertFalse(load_config()['experiments']['boolean_lesson'])
        with self.assertRaises(ValueError):BooleanLesson(self.db,False).start('negation_true')
        with self.db.connect() as db:
            self.assertFalse(db.execute("SELECT 1 FROM sqlite_master WHERE name='boolean_lessons'").fetchone())

    def flow(self,scenario):
        from tutor.boolean_lesson import BooleanLesson,scenarios
        service=BooleanLesson(self.db,True);state=service.start(scenario)
        self.assertEqual(state['stage'],'concept')
        for action in ('example','exercise'):
            state=service.turn(state['id'],{'request_id':action+'-0000000','action':action,'version':state['version']})
        spec=scenarios()[scenario];name,value=next(iter(spec['values'].items()))
        wrong={'fact_name':name,'fact_value':value,'expression':spec['mistake'],'conclusion':not spec['expected']}
        before=state
        req={'request_id':'first-attempt-000','action':'attempt','version':state['version'],'attempt':wrong}
        state=service.turn(state['id'],req)
        self.assertEqual(state['stage'],'retry')
        self.assertNotIn('expected',state)
        self.assertNotIn('correction',state)
        self.assertNotIn('resultado do exercício é',state['messages'][-1]['body'])
        self.assertEqual(service.turn(state['id'],req)['version'],state['version'])
        service=BooleanLesson(self.db,True)
        self.assertEqual(service.get(state['id'])['stage'],'retry')
        state=service.turn(state['id'],{'request_id':'second-attempt-000','action':'attempt','version':state['version'],'attempt':wrong})
        self.assertEqual(state['stage'],'correction')
        body=state['messages'][-1]['body']
        self.assertIn(f'{name} = {value}',body);self.assertIn(spec['rule'],body)
        self.assertNotIn('parcial',body.lower())
        state=service.turn(state['id'],{'request_id':'transfer-000','action':'transfer','version':state['version']})
        self.assertEqual(state['stage'],'transfer_wait')
        self.assertNotEqual(state['exercise']['values'],before['exercise']['values'])
        self.assertNotEqual(state['exercise']['context'],before['exercise']['context'])
        return service,state

    def test_balanced_keys_and_complete_two_misconception_flows(self):
        from tutor.boolean_lesson import scenarios
        self.assertEqual({c['expected'] for c in scenarios().values()},{True,False})
        for scenario in scenarios():self.flow(scenario)

    def test_out_of_scope_does_not_count_as_attempt_or_advance(self):
        from tutor.boolean_lesson import BooleanLesson
        service,state=self.flow('negation_true')
        before=state['stage']
        state=service.turn(state['id'],{'request_id':'outside-00000','action':'question','version':state['version'],'body':'Qual a probabilidade de chover amanhã?'})
        self.assertEqual(state['stage'],before)
        self.assertIn('não consigo verificar',state['messages'][-1]['body'].lower())

    def test_stale_version_and_early_transfer_refused(self):
        from tutor.boolean_lesson import BooleanLesson
        from storage.database import ConflictError
        s=BooleanLesson(self.db,True);r=s.start('negation_true')
        with self.assertRaises(ValueError):s.turn(r['id'],{'request_id':'early-00000','action':'transfer','version':0})
        r=s.turn(r['id'],{'request_id':'example-000','action':'example','version':0})
        with self.assertRaises(ConflictError):s.turn(r['id'],{'request_id':'stale-00000','action':'exercise','version':0})

    def test_transfer_answer_and_delete(self):
        from tutor.boolean_lesson import scenarios
        s,r=self.flow('implication_false');tr=scenarios()['implication_false']['transfer'];name,value=next(iter(tr['values'].items()))
        r=s.turn(r['id'],{'request_id':'transfer-final-000','action':'transfer_attempt','version':r['version'],
                         'attempt':{'fact_name':name,'fact_value':value,'expression':tr['expression'],'conclusion':tr['expected']}})
        self.assertEqual(r['stage'],'complete');self.assertIn('não demonstra aprendizagem',r['messages'][-1]['body'])
        s.delete(r['id'])
        with self.assertRaises(ValueError):s.get(r['id'])

    def test_unsupported_expression_and_question_preserve_pending_exercise(self):
        from tutor.boolean_lesson import BooleanLesson
        s=BooleanLesson(self.db,True);r=s.start('negation_true')
        for action in ('example','exercise'):r=s.turn(r['id'],{'request_id':action+'-prepare000','action':action,'version':r['version']})
        exercise=r['exercise']
        r=s.turn(r['id'],{'request_id':'unsupported-000','action':'attempt','version':r['version'],
                         'attempt':{'fact_name':'cadastro','fact_value':True,'expression':"__import__('os')",'conclusion':False}})
        self.assertEqual(r['stage'],'waiting_attempt');self.assertEqual(r['attempts'],0);self.assertEqual(r['exercise'],exercise)
        r=s.turn(r['id'],{'request_id':'question-pending00','action':'question','version':r['version'],'body':'Por que chove?'})
        self.assertEqual(r['stage'],'waiting_attempt');self.assertEqual(r['attempts'],0)

    def test_wrong_rule_with_correct_key_is_not_claimed_correct_reasoning(self):
        from tutor.boolean_lesson import check,scenarios,correction
        t=scenarios()['equivalence_false'];a={'fact_name':'a','fact_value':False,'expression':t['mistake'],'conclusion':False}
        result=check(t,a);self.assertTrue(result['conclusion_correct']);self.assertFalse(result['equivalent']);self.assertFalse(result['consistent_with_own_expression'])
        answer=correction(t,a,result);self.assertIn('coincide com o gabarito',answer);self.assertIn('não preserva',answer)

    def test_concurrent_versions_only_one_action_commits(self):
        from concurrent.futures import ThreadPoolExecutor
        from tutor.boolean_lesson import BooleanLesson
        from storage.database import ConflictError
        s=BooleanLesson(self.db,True);r=s.start('negation_true')
        def send(i):
            try:s.turn(r['id'],{'request_id':f'parallel-{i}-000','action':'example','version':0});return 'ok'
            except ConflictError:return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertCountEqual(list(pool.map(send,(1,2))),['ok','conflict'])
