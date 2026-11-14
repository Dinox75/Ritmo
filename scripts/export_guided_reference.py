"""Reapply supplementary code audit to unchanged raw pilot outputs; no inference."""
import argparse
import copy
import hashlib
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from training.lab.guided_audit import augment
from training.lab.state import write,digest
from scripts.pilot_guided_reference import summarize


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--view',type=Path,required=True);p.add_argument('--publish',type=Path)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    frozen=json.loads((a.run/'frozen.json').read_text(encoding='utf8'))
    assert digest(frozen)==json.loads((a.run/'freeze-seal.json').read_text())['sha256']
    for name,expected in frozen['code'].items():assert hashlib.sha256((repo/name).read_bytes()).hexdigest()==expected
    for name,expected in frozen['preserved'].items():assert hashlib.sha256((repo/name).read_bytes()).hexdigest()==expected
    source=a.run/'guided-reference.json';original=json.loads(source.read_text(encoding='utf8'))
    assert original['complete'] and len(original['cases'])==9
    result=copy.deepcopy(original)
    for c in result['cases']:
        for method,item in c['versions'].items():
            assert item['observer']['decision_authority'] is False
            item['assessment_frozen']=copy.deepcopy(item['assessment'])
            item['assessment']=augment(c['task'],item['output'],item['assessment'],c['versions']['reference']['output'],method)
            assert item['assessment']['corpus_eligible'] is False
    result['summaries']=summarize(result['cases'])
    for family,methods in result['summaries'].items():
        for method,values in methods.items():
            values['identity_preserved']=sum(c['task']['family']==family and c['versions'][method]['assessment']['logic']['status']=='identical_to_reference' for c in result['cases'])
    result['post_run_audit']={'timing':'Added after independent review on the SAME raw outputs; not a held-out calibration result.',
         'original_result_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
         'code_sha256':hashlib.sha256((repo/'training/lab/guided_audit.py').read_bytes()).hexdigest(),
         'changes':'False asserted equivalence gets a computed counterexample; full text identity to the reference is distinguished from scattered anchors. Frozen assessment retained. Correction disclosure is N/A.'}
    result['decision']='Estrutura de código preserva referências e objetivos; reescrita copia 8/9. Pedagogia aberta permanece inconclusiva; nenhum item vai ao corpus.'
    a.view.mkdir(parents=True,exist_ok=True);write(a.view/'guided-reference.json',result)
    write(a.view/'state.json',{'status':'completed','phase':'report','started':frozen['time'],'heartbeat':time.time(),
                             'training_real':False,'message':result['decision'],'counts':{'generated':18,'approved':0}})
    if a.publish:
        a.publish.mkdir(parents=True,exist_ok=True)
        write(a.publish/'results.json',result)
        for name in ('frozen.json','freeze-seal.json','calls.jsonl'):(a.publish/name).write_bytes((a.run/name).read_bytes())
        (a.publish/'results-frozen.json').write_bytes(source.read_bytes())
    print(json.dumps({'cases':9,'versions':27,'eligible':0,'full_verbatim_rewrites':sum(c['versions']['reference']['output']['intervention']==c['versions']['rewrite']['output'].get('intervention') for c in result['cases'])}))


if __name__=='__main__':main()
