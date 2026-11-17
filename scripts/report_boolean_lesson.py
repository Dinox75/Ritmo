"""Preserve baseline raw outputs, replay structured lesson and attach explicit review."""
import argparse
import copy
import hashlib
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from storage.database import Database
from tutor.boolean_lesson import BooleanLesson,scenarios
from scripts.compare_boolean_lesson import attempts
from training.lab.state import write,digest


REVIEW={
 'negation_true':{'hint_useful':False,'early_solution_avoided':True,'correction_foundation':False,'outside_limit_acknowledged':True,
    'reason':'Primeiro feedback foi fallback seguro, sem próximo passo específico. Na segunda correção a regra de De Morgan está certa, mas o campo acerto atribui ao aluno uma regra que ele não usou. Na transferência o resultado False correto foi chamado incorreto.'},
 'implication_false':{'hint_useful':False,'early_solution_avoided':False,'correction_foundation':False,'outside_limit_acknowledged':True,
    'reason':'Primeira correção atribui ao aluno a negação que ele omitiu e conclui True, embora False or False seja False. Segunda resposta caiu em fallback. A avaliação de transferência acertou a conclusão, mas a etapa permaneceu correction.'},
 'equivalence_false':{'hint_useful':False,'early_solution_avoided':None,'correction_foundation':None,'outside_limit_acknowledged':True,
    'reason':'Primeira correção alega troca de autorizado para True que não consta da tentativa. Segunda resposta reconhece conclusão False e menciona erro AND/OR, mas não reconhece a entrada a=False nem distingue a expressão do aluno da original. Não há declaração inequívoca do gabarito na primeira resposta; ausência de spoiler não certificada.'}}


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--view',type=Path,required=True);p.add_argument('--publish',type=Path,required=True);p.add_argument('--frozen-engine',type=Path);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];frozen=json.loads((a.run/'frozen.json').read_text(encoding='utf8'))
    assert digest(frozen)==json.loads((a.run/'seal.json').read_text())['sha256']
    for name,sha in frozen['preserved'].items():assert hashlib.sha256((repo/name).read_bytes()).hexdigest()==sha
    for name,sha in frozen['code'].items():
        path=(a.frozen_engine or a.publish/'engine-frozen.py.txt') if name=='tutor/boolean_lesson.py' else repo/name
        assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
    source=a.run/'lesson-comparison.json';result=json.loads(source.read_text(encoding='utf8'));assert result['complete'] and len(result['cases'])==3
    if (a.view/'lesson-comparison.json').exists():raise ValueError('Relatório existente; use outra pasta, sem sobrescrever resultados.')
    a.view.mkdir(parents=True,exist_ok=True);a.publish.mkdir(parents=True,exist_ok=True)
    if a.frozen_engine:(a.publish/'engine-frozen.py.txt').write_bytes(a.frozen_engine.read_bytes())
    db=Database(a.view/'experimental-reviewed.db');db.initialize();engine=BooleanLesson(db,True)
    for c in result['cases']:
        key=c['id'];task=scenarios()[key];first,second=attempts(task,key)
        c['experimental_frozen']=copy.deepcopy(c['experimental'])
        s=engine.start(key);snaps=[s]
        tr=task['transfer'];name,value=next(iter(tr['values'].items()))
        actions=[('example',{}),('exercise',{}),('attempt',{'attempt':first}),('attempt',{'attempt':second}),('transfer',{}),
                 ('transfer_attempt',{'attempt':{'fact_name':name,'fact_value':value,'expression':tr['expression'],'conclusion':tr['expected']}}),
                 ('question',{'body':'Qual a probabilidade de chover amanhã?'})]
        for i,(action,extra) in enumerate(actions):
            s=engine.turn(s['id'],{'request_id':key+f'-reviewed-{i:02d}','action':action,'version':s['version'],**extra});snaps.append(s)
        c['experimental']={'dialog':s['messages'],'snapshots':snaps,'model_calls':0,'verification':'bounded_boolean_code_replayed_after_transfer_wording_fix'}
        assert [x['stage'] for x in snaps]==['concept','example','waiting_attempt','retry','correction','transfer_wait','complete','complete']
        hint=snaps[3]['messages'][-1]['body'];correction=snaps[4]['messages'][-1]['body']
        assert task['step'] in hint and task['question'] in hint and not any(x in hint for x in ('True','False','resultado do exercício'))
        assert task['rule'] in correction and f'{first["fact_name"]} = {first["fact_value"]}' in correction
        assert task['transfer']['context']!=task['context'] and task['transfer']['values']!=task['values']
        c['assessment']={'current':{'source':'agent_review_of_displayed_dialogue_not_a_validated_judge',**REVIEW[key]},
                         'experimental':{'source':'automated_state_and_closed_content_checks','hint_useful':True,'early_solution_avoided':True,
                                         'correction_foundation':True,'transfer_context_changed':True,'outside_limit_acknowledged':True,
                                         'limits':'Checks target the designed step and Boolean fields; no proof of student learning or free-text reasoning.'}}
    result['post_comparison']={'source_raw_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                              'engine_sha256':hashlib.sha256((repo/'tutor/boolean_lesson.py').read_bytes()).hexdigest(),
                              'change':'After independent review, transfer feedback names new variables instead of old context. Experimental flows replayed with same attempts, no new model calls. Original experimental snapshots retained.',
                              'student_learning_evidence':False}
    write(a.view/'lesson-comparison.json',result);write(a.publish/'results.json',result)
    for name in ('frozen.json','seal.json','calls.jsonl'):(a.publish/name).write_bytes((a.run/name).read_bytes())
    (a.publish/'results-frozen.json').write_bytes(source.read_bytes())
    write(a.view/'state.json',{'status':'completed','phase':'report','started':frozen['time'],'heartbeat':time.time(),'training_real':False,
                             'message':'Fluxo experimental verificado em dados sintéticos; aprendizagem com estudantes não foi medida.','counts':{'generated':0,'approved':0}})
    print(json.dumps({'cases':3,'baseline_model_calls':len((a.run/'calls.jsonl').read_text(encoding='utf8').splitlines()),'experimental_model_calls':0,'student_learning_evidence':False}))


if __name__=='__main__':main()
