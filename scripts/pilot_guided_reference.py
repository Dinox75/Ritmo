"""Freeze then run local three-way didactic comparison. No training/corpus export."""
import argparse
import copy
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from training.lab.guided_reference import tasks, reference, load_sources, assess, REWRITE, OBSERVE
from training.lab.prepare import SYSTEM, private_context, parse
from training.lab.state import write, digest


def summarize(cases):
    result = {}
    for c in cases:
        f = result.setdefault(c['task']['family'], {})
        for method, item in c['versions'].items():
            v = f.setdefault(method, {'total':0,'logic_constructed':0,'literal_anchors_preserved':0,
                                     'logic_inconclusive':0,'logical_vetoes':0,'question_objective_preserved':0,
                                     'question_inconclusive':0,'spoiler_avoided_by_construction':0,
                                     'no_explicit_spoiler_detected':0,'spoiler_detected':0,'corpus_eligible':0})
            a = item['assessment']; v['total'] += 1
            status = a['logic']['status']
            v['logic_constructed'] += status == 'proved_by_construction'
            v['literal_anchors_preserved'] += status == 'literal_anchors_preserved'
            v['logic_inconclusive'] += status == 'inconclusive'
            v['logical_vetoes'] += bool(a['vetoes'])
            question_ok = a['question']['status'] in ('structured_objective','preserved_objective')
            v['question_objective_preserved'] += question_ok
            v['question_inconclusive'] += not question_ok
            v['spoiler_avoided_by_construction'] += a['spoiler']['status'] == 'avoided_by_construction'
            v['no_explicit_spoiler_detected'] += a['spoiler']['status'] == 'no_explicit_spoiler_detected'
            v['spoiler_detected'] += a['spoiler']['status'] == 'detected'
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True); p.add_argument('--phase', choices=['freeze','run'],required=True)
    p.add_argument('--originals', type=Path); p.add_argument('--model-root',type=Path)
    a = p.parse_args(); repo = Path(__file__).resolve().parents[1]; root = a.run.resolve()
    assert not root.is_relative_to(repo), 'execução fora do Git'
    root.mkdir(parents=True,exist_ok=True)
    def preserved():
        files = subprocess.check_output(['git','ls-files','docs/qa/training-lab-results','docs/qa/training-lab-two-stage','docs/qa/training-lab-calibration'],cwd=repo,text=True).splitlines()
        return {name:hashlib.sha256((repo/name).read_bytes()).hexdigest() for name in files}
    def code():
        return {name:hashlib.sha256((repo/name).read_bytes()).hexdigest() for name in
                ['training/lab/guided_reference.py','training/lab/exercises.py','training/lab/validation.py','training/lab/prepare.py','scripts/pilot_guided_reference.py','local_ai/runtime.py','local_ai/models.json','training/lab/catalog.json']}
    if a.phase == 'freeze':
        assert not (root/'frozen.json').exists(), 'não sobrescrever'
        assert a.originals
        cases = []
        for task in tasks():
            sources = load_sources(a.originals,task); ref = reference(task,sources)
            cases.append({'id':task['family']+'-'+task['kind'],'task':task,'sources':sources,'reference':ref,
                          'current_input':private_context(task,*sources),
                          'rewrite_input':{'exercise':task['exercise'],'student':task['student'],'kind':task['kind'],
                                           'reference':ref,'sources':sources}})
        from local_ai.installer import manifest
        frozen = {'time':time.time(),'cases':cases,'code':code(),'preserved':preserved(),
                  'prompts':{'current':SYSTEM,'rewrite':REWRITE,'observer':OBSERVE},'manifest':manifest(),
                  'sampling':{'temperature':.2,'seed':42,'max_tokens':700,'thinking':False,'ctx':4096},
                  'observer_max_tokens':350,'gpu_layers':99,'training':False,'corpus_export':False}
        write(root/'frozen.json',frozen); write(root/'freeze-seal.json',{'sha256':digest(frozen)})
        print('9 cases and references frozen before inference'); return
    frozen = json.loads((root/'frozen.json').read_text(encoding='utf8'))
    assert digest(frozen) == json.loads((root/'freeze-seal.json').read_text())['sha256']
    assert frozen['code'] == code() and frozen['preserved'] == preserved()
    assert not (root/'guided-reference.json').exists(), 'não sobrescrever resultados'
    from local_ai.runtime import LocalRuntime
    runtime = LocalRuntime(a.model_root,gpu_layers=99)
    report = {'cases':[],'config':{k:v for k,v in frozen.items() if k!='cases'},'summaries':{},'complete':False,
              'decision':'Piloto observacional: nenhuma ampliação do corpus ou treino.',
              'limits':'Âncoras literais não provam toda a prosa. Pergunta preservada tem objetivo projetado, não eficácia de aprendizagem demonstrada. Juiz4B não decide; todos ficam fora do corpus.'}
    def save():
        report['summaries'] = summarize(report['cases']); write(root/'guided-reference.json',report)
        write(root/'state.json',{'status':'completed' if report['complete'] else 'running','phase':'evaluate',
                                'started':frozen['time'],'heartbeat':time.time(),'training_real':False,
                                'message':report['decision'],'counts':{'generated':sum(m!='reference' for c in report['cases'] for m in c['versions']),'approved':0}})
    def call(model,system,payload,tokens,case_id,method):
        try: runtime.start(model)
        except Exception as e:
            write(root/'startup-error.json',{'error':str(e),'log':runtime._recent_log}); raise
        body = {'model':model,'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}],
                'temperature':.2,'seed':42,'max_tokens':tokens,'stream':False,'chat_template_kwargs':{'enable_thinking':False}}
        started = time.perf_counter()
        with runtime._urlopen('/v1/chat/completions',json.dumps(body,ensure_ascii=False).encode(),timeout=180) as response: data=json.load(response)
        raw = data['choices'][0]['message']['content']
        metric = {'model':model,'raw':raw,'seconds':time.perf_counter()-started,'usage':data.get('usage'),
                  'timings':data.get('timings'),'finish_reason':data['choices'][0].get('finish_reason')}
        with (root/'calls.jsonl').open('a',encoding='utf8') as f: f.write(json.dumps({'case':case_id,'method':method,'request':body,**metric},ensure_ascii=False)+'\n')
        return raw,metric
    try:
        for case in frozen['cases']:
            t,ref = case['task'],case['reference']
            row = {'id':case['id'],'task':t,'sources':case['sources'],'versions':{}}
            row['versions']['reference'] = {'output':ref,'assessment':assess(t,ref,ref,'reference'),'generation':'deterministic_no_model'}
            report['cases'].append(row); save()
            for method in ('current','rewrite'):
                raw,metric=call('qwen3-1.7b-q8_0',frozen['prompts'][method],case[method+'_input'],700,case['id'],method)
                try:
                    output=parse(raw)
                    if set(output) != {'intervention','verification_question'}: raise ValueError('contrato de dois campos')
                except (ValueError,TypeError): output={'parse_error':True}
                row['versions'][method]={'output':output,'raw':raw,'metric':metric,'assessment':assess(t,output,ref,method)}
                save(); print(case['id']+' '+method,flush=True)
        runtime.stop()
        for row in report['cases']:
            for method,item in row['versions'].items():
                before=digest(item['assessment'])
                raw,metric=call('qwen3-4b-q4_k_m',OBSERVE,{'kind':row['task']['kind'],'exercise':row['task']['exercise'],
                    'key':row['task']['expected'],'student':row['task']['student'],'candidate':item['output'],'sources':row['sources']},350,row['id'],method+'-observer')
                try: observation=parse(raw)
                except (ValueError,TypeError): observation={'inconclusive':'resposta fora do contrato'}
                item['observer']={'observation':observation,'raw':raw,'metric':metric,'decision_authority':False}
                assert digest(item['assessment'])==before
                save(); print(row['id']+' '+method+' observer',flush=True)
        assert frozen['preserved'] == preserved() and frozen['code']==code()
        report['complete']=True; save()
    finally: runtime.stop()


if __name__=='__main__':main()
