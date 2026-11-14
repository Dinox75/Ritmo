"""Synthetic isolated lesson-flow comparison, no training or corpus export."""
import argparse
import base64
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from storage.database import Database
from storage.materials import import_material
from tutor.boolean_lesson import BooleanLesson,scenarios
from tutor.service import TutorService
from local_ai.runtime import LocalRuntime
from utils.config import DEFAULT_CONFIG,save_config
from training.lab.state import write,digest


def attempts(task,key):
    name,value=next(iter(task['values'].items()))
    first={'fact_name':name,'fact_value':value,'expression':task['mistake'],'conclusion':not task['expected']}
    second=dict(first)
    if key=='implication_false':second.update(expression=task['expression'],conclusion=task['expected'])
    if key=='equivalence_false':second['conclusion']=task['expected']
    return first,second


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--model-root',type=Path,required=True);p.add_argument('--freeze',action='store_true');a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];root=a.run.resolve();assert not root.is_relative_to(repo);root.mkdir(parents=True,exist_ok=True)
    def preserved():
        names=subprocess.check_output(['git','ls-files','docs/training-lab-results','docs/training-lab-two-stage','docs/training-lab-calibration','docs/training-lab-guided-reference'],cwd=repo,text=True).splitlines()
        return {name:hashlib.sha256((repo/name).read_bytes()).hexdigest() for name in names}
    def code():return {name:hashlib.sha256((repo/name).read_bytes()).hexdigest() for name in ('tutor/boolean_lesson.py','tutor/boolean_sources.json','tutor/service.py','tutor/protocol.py','scripts/compare_boolean_lesson.py')}
    if a.freeze:
        assert not (root/'frozen.json').exists()
        frozen={'scenarios':scenarios(),'preserved':preserved(),'code':code(),'time':time.time(),
                'baseline':{'model':'qwen3-4b-q4_k_m','temperature':.3,'seed':42,'max_tokens':420,'thinking':False,'gpu_layers':99},
                'rubric':{'hint':'procedural next step linked to misconception, not only another result request',
                          'early_solution':'do not disclose main key before second attempt; worked different example permitted',
                          'correction':'specific true fact + exact mistaken transformation + valid rule/current values',
                          'transfer':'new context/form, same rule, computed key, no automatic mastery claim'},
                'harness':'Baseline opening is real TutorService. Harness then pins same pending exercise in lesson state to compare feedback; no baseline response fabricated. Later messages use unchanged service transitions.',
                'training':False,'student_learning_evidence':False,'corpus_export':False}
        write(root/'frozen.json',frozen);write(root/'seal.json',{'sha256':digest(frozen)});print('frozen');return
    frozen=json.loads((root/'frozen.json').read_text(encoding='utf8'));assert digest(frozen)==json.loads((root/'seal.json').read_text())['sha256']
    assert frozen['preserved']==preserved() and frozen['code']==code();assert not (root/'lesson-comparison.json').exists()
    config=json.loads(DEFAULT_CONFIG.read_text(encoding='utf8'));config['tutor']={'provider':'local','model':'qwen3-4b-q4_k_m','model_root':str(a.model_root)}
    config['experiments']={'boolean_lesson':True};save_config(config,root/'config.json')
    db=Database(root/'synthetic.db');db.initialize();experimental=BooleanLesson(db,True);runtime=LocalRuntime(a.model_root,gpu_layers=99)
    report={'cases':[],'config':frozen,'complete':False,'student_learning_evidence':False,'training':False}
    active_case=[''];metrics=[]
    def provider(model,instructions,messages):
        runtime.start(model)
        payload={'model':model,'messages':[{'role':'system','content':instructions},*messages],
                 'temperature':.3,'seed':42,'max_tokens':420,'stream':False,'chat_template_kwargs':{'enable_thinking':False}}
        start=time.perf_counter()
        with runtime._urlopen('/v1/chat/completions',json.dumps(payload,ensure_ascii=False).encode(),timeout=180) as response:data=json.load(response)
        raw=data['choices'][0]['message']['content']
        metric={'case':active_case[0],'request':payload,'raw':raw,'seconds':time.perf_counter()-start,'usage':data.get('usage'),'timings':data.get('timings'),'finish_reason':data['choices'][0].get('finish_reason')}
        metrics.append(metric)
        with (root/'calls.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(metric,ensure_ascii=False)+'\n')
        return raw
    service=TutorService(db,config_path=root/'config.json',provider=provider,runtime=runtime)
    def save():
        write(root/'lesson-comparison.json',report)
        write(root/'state.json',{'status':'completed' if report['complete'] else 'running','phase':'evaluate','started':frozen['time'],'heartbeat':time.time(),'training_real':False,'message':'Aula booleana isolada: comportamento do software, não aprendizagem.','counts':{'generated':len(metrics),'approved':0}})
    try:
        for key,t in frozen['scenarios'].items():
            active_case[0]=key;first,second=attempts(t,key)
            state=experimental.start(key);snapshots=[state]
            for index,(action,extra) in enumerate([('example',{}),('exercise',{}),('attempt',{'attempt':first}),('attempt',{'attempt':second}),('transfer',{})]):
                state=experimental.turn(state['id'],{'request_id':f'{key}-{index}-experiment','version':state['version'],'action':action,**extra});snapshots.append(state)
            tr=t['transfer'];name,value=next(iter(tr['values'].items()))
            transfer_attempt={'fact_name':name,'fact_value':value,'expression':tr['expression'],'conclusion':tr['expected']}
            state=experimental.turn(state['id'],{'request_id':key+'-transfer-answer','version':state['version'],'action':'transfer_attempt','attempt':transfer_attempt});snapshots.append(state)
            outside='Qual a probabilidade de chover amanhã?'
            before=state['attempts'];state=experimental.turn(state['id'],{'request_id':key+'-outside-scope','version':state['version'],'action':'question','body':outside});snapshots.append(state);assert state['attempts']==before
            item={'id':key,'task':t,'experimental':{'dialog':state['messages'],'snapshots':snapshots,'model_calls':0,'verification':'bounded_boolean_code'},'current':{'turns':[]},'assessment':None}
            report['cases'].append(item);save()
            subject=db.create_subject('QA sintético '+key)
            material=import_material(db,subject['id'],'Regra sintética','regra.txt',base64.b64encode((t['concept']+'\n'+t['rule']+'\nTrue e False são os únicos valores destas entradas.').encode()).decode())
            thread=service.store.create_thread(subject['id']);service.store.set_mode(thread['id'],'aula');service.store.set_materials(thread['id'],[material['id']])
            def send(label,body,kind='question'):
                old=service.store.get_lesson(thread['id']);start=len(metrics)
                result=service.send(thread['id'],key+'-'+label+'-current',body,message_kind=kind)
                item['current']['turns'].append({'label':label,'body':body,'message_kind':kind,'stage_before':old['stage'],'stage_after':service.store.get_lesson(thread['id'])['stage'],'last_turn':service.last_turn,'calls':list(range(start,len(metrics)))})
                item['current']['dialog']=result['messages'];save();print(key+' '+label,flush=True)
            send('opening','Explique '+t['concept']+' com um exemplo curto, sem antecipar exercícios.')
            original_state=service.store.get_lesson(thread['id']);pinned={**original_state,'stage':'waiting_attempt','exercise':t['context']+' '+t['expression']+' '+str(t['values']),'sources':service.last_turn['sources']}
            with db.connect() as connection:connection.execute('INSERT INTO tutor_lesson_state VALUES (?,?) ON CONFLICT(thread_id) DO UPDATE SET state_json=excluded.state_json',(thread['id'],json.dumps(pinned,ensure_ascii=False)))
            item['current']['harness_intervention']={'before':original_state,'pinned':pinned,'note':frozen['harness']}
            send('first_attempt',json.dumps(first,ensure_ascii=False),'attempt')
            send('second_attempt',json.dumps(second,ensure_ascii=False),'attempt')
            send('transfer','Proponha um exercício de transferência neste novo contexto, sem resolver: '+tr['context']+' Condição '+tr['expression']+' Entradas '+str(tr['values']))
            send('transfer_attempt',json.dumps(transfer_attempt,ensure_ascii=False),'attempt')
            send('outside',outside)
        assert frozen['preserved']==preserved() and frozen['code']==code();report['complete']=True;save()
    finally:runtime.stop()


if __name__=='__main__':main()
