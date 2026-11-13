"""Conservative field checks; independent semantic judgment remains necessary."""
import re
from .validation import normalized, solve


def check_fields(task, intervention, question):
    if not isinstance(intervention, str) or not isinstance(question, str): return ['campos_pedagogicos_invalidos']
    reasons = []
    answer, q = normalized(intervention), normalized(question)
    text = intervention + ' ' + question
    if not 30 <= len(intervention) <= 1500 or not 25 <= len(question) <= 300: reasons.append('tamanho_campos_invalido')
    if '?' in intervention or question.count('?') != 1 or not question.rstrip().endswith('?'):
        reasons.append('campos_intervencao_pergunta_misturados')
    # 'interpretada como' is a comparison, not an interrogative demand for reasoning.
    cognitive = re.search(r'(?:^|[.!]\s+|,\s+)(?:como|por que|qual|quais|o que|em que|que diferen[cç]a)\b', question.strip(), re.I)
    generic = re.search(r'entendeu|tudo certo|faz sentido|qual e a resposta|qual (?:e )?o resultado|gostou|alguma duvida', q)
    cues = any(normalized(cue) in q if re.search(r'\w', cue) else cue in question for cue in task['cues'])
    if not cognitive or generic or not cues: reasons.append('pergunta_sem_verificacao_contextual')
    # A question containing the answer is a spoiler too. No automatic '?' insertion.
    if task['kind'] == 'hint' and re.search(r'\b(verdadeir\w*|fals\w*|true|false|esta dentro|esta fora|resultado e|resposta e|condicao e satisfeita|nao e satisfeita)\b', normalized(text)):
        reasons.append('dica_entrega_solucao')
    if task['kind'] == 'correction':
        if not re.search(r'acert|corret|parte certa|bem observado', answer): reasons.append('correcao_sem_acerto_parcial')
        fact_name = normalized(task['student']['correct_fact'].split('=')[0]).strip()
        if not re.search(r'\b' + re.escape(fact_name) + r'\b', answer): reasons.append('correcao_sem_acerto_especifico')
        if not re.search(r'porque|pois|exige|inverte|incluir|excluir|precedencia|agrup|parentes', answer):
            reasons.append('correcao_sem_fundamento')
        if not re.search(r'mas|porem|entretanto|erro|equivoc|confund|na verdade|diferenca', answer):
            reasons.append('correcao_sem_identificar_erro')
    if task['kind'] == 'explanation' and not re.search(r'exemplo|por exemplo', answer): reasons.append('explicacao_sem_exemplo_distinto')
    # Deterministic checks on explicit mathematical claims, not just the private result.
    pattern = r'(-?\d+)\s*(<=|>=|==|!=|<|>)\s*(-?\d+)\s*(?:é|e|resulta em|é igual a)?\s*(verdadeir\w*|fals\w*|True|False)'
    for m in re.finditer(pattern, text, re.I):
        actual = solve(m[1] + m[2] + m[3], {})
        stated = normalized(m[4]).startswith(('verdadeir', 'true'))
        if actual != stated: reasons.append('afirmacao_logica_incorreta')
    bad_rules = [r'\be (?:exige|precisa de|basta) (?:apenas |so )?uma condicao',
                 r'\bou (?:exige|precisa de) (?:todas|ambas)', r'\bnao (?:mantem|preserva) o valor',
                 r'\b(?:operador and|operador e|and) (?:exclui|excluira|inclui|incluira) (?:a )?igualdade']
    if any(re.search(rule, normalized(text)) for rule in bad_rules): reasons.append('regra_logica_incorreta')
    if re.search(r'senha|execute .*comando|ignore .*instru', normalized(text)): reasons.append('instrucao_hostil_reproduzida')
    return sorted(set(reasons))
