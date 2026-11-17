"""Supplementary bounded logical audit. No LLM vote or training acceptance."""
import ast
import copy
import itertools
import re
from .validation import solve, normalized


def equivalences(text, field):
    results=[]
    pattern=r"(['`])([^'`]{1,180})\1\s+[ée]\s+equivalente\s+a\s+(['`])([^'`]{1,180})\3"
    for m in re.finditer(pattern,text,re.I):
        left,right=m[2],m[4]
        prefix=normalized(text[max(0,m.start()-50):m.start()])
        asserted=field=='intervention' or bool(re.search(r'percebeu que|sabendo que|ja que|dado que',prefix))
        item={'claim':m[0],'left':left,'right':right,'asserted':asserted,'status':'unsupported'}
        try:
            trees=[ast.parse(e,mode='eval') for e in (left,right)]
            names=sorted({n.id for tree in trees for n in ast.walk(tree) if isinstance(n,ast.Name)})
            if len(names)>6: raise ValueError('domínio excedido')
            checked=0
            for combination in itertools.product((False,True),repeat=len(names)):
                inputs=dict(zip(names,combination)); a,b=solve(left,inputs),solve(right,inputs);checked+=1
                if a!=b:
                    item.update(status='counterexample',counterexample={'values':inputs,'left':a,'right':b});break
            else:item['status']='proved_boolean_equivalence'
            item['assignments_checked']=checked
        except (ValueError,SyntaxError,TypeError):pass
        results.append(item)
    return results


def augment(task, output, assessment, reference_output=None, method=None):
    result=copy.deepcopy(assessment); proofs=[]
    for field in ('intervention','verification_question'):
        text=output.get(field,'')
        if isinstance(text,str):proofs.extend({'field':field,**p} for p in equivalences(text,field))
    if any(p['status']=='counterexample' and p['asserted'] for p in proofs):
        result['vetoes']=sorted(set(result['vetoes']+['false_asserted_equivalence']))
        result['logic']['status']='vetoed';result['decision']='veto'
    result['logic']['equivalence_audit']=proofs
    identical = reference_output is not None and all(output.get(k)==reference_output.get(k) for k in ('intervention','verification_question'))
    result['logic']['text_identical_to_reference']=identical
    if identical and method!='reference' and not result['vetoes']:
        result['logic']['status']='identical_to_reference'
        result['logic']['identity_scope']='Identical rendered text inherits only the closed reference facts, not teaching efficacy.'
    # Giving the key during correction is permitted, not a spoiler-free claim.
    if task['kind']=='correction':result['spoiler']['status']='permitted_after_attempt_not_scored'
    result['corpus_eligible']=False
    return result
