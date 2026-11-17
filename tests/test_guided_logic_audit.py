import unittest


class LogicAuditTests(unittest.TestCase):
    def test_identity_is_stronger_than_retaining_scattered_anchors(self):
        from training.lab.guided_reference import tasks,reference,assess
        from training.lab.guided_audit import augment
        t=tasks()[0];r=reference(t,[])
        exact={'intervention':r['intervention'],'verification_question':r['verification_question']}
        a=augment(t,exact,assess(t,exact,r,'rewrite'),r,'rewrite')
        self.assertEqual(a['logic']['status'],'identical_to_reference')
        changed={**exact,'intervention':exact['intervention']+' Uma alegação adicional.'}
        b=augment(t,changed,assess(t,changed,r,'rewrite'),r,'rewrite')
        self.assertFalse(b['logic']['text_identical_to_reference'])
        self.assertNotEqual(b['logic']['status'],'identical_to_reference')
        self.assertFalse(a['corpus_eligible'])

    def test_asserted_equivalence_has_a_computed_counterexample(self):
        from training.lab.guided_audit import equivalences
        bad = equivalences("O aluno percebeu que 'not (p and q)' é equivalente a 'not p and not q'?", 'verification_question')
        self.assertEqual(bad[0]['status'], 'counterexample')
        self.assertTrue(bad[0]['asserted'])
        good = equivalences("'not (p and q)' é equivalente a 'not p or not q'.", 'intervention')
        self.assertEqual(good[0]['status'], 'proved_boolean_equivalence')

    def test_open_challenge_is_not_an_assertion_and_code_is_not_executed(self):
        from training.lab.guided_audit import equivalences
        q = equivalences("'p and q' é equivalente a 'p or q'?", 'verification_question')
        self.assertFalse(q[0]['asserted'])
        unsafe = equivalences("'__import__(p)' é equivalente a 'p'.", 'intervention')
        self.assertEqual(unsafe[0]['status'], 'unsupported')
