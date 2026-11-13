"""Bounded expression interpreter and independent conservative screening. No eval/exec."""
import ast
import operator
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher

from .sources import approved


def solve(expression, values):
    if len(expression) > 200 or len(values) > 8: raise ValueError('expressão excede limite')
    if any(type(v) not in {bool, int} or abs(v) > 100000 for v in values.values()):
        raise ValueError('valores fora do domínio')
    try: tree = ast.parse(expression, mode='eval')
    except SyntaxError as error: raise ValueError('expressão inválida') from error
    if sum(1 for _ in ast.walk(tree)) > 60: raise ValueError('expressão muito complexa')
    ops = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt,
           ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne}
    def walk(node):
        if isinstance(node, ast.Expression): return walk(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in {bool, int} and abs(node.value) <= 100000: return node.value
        if isinstance(node, ast.Name) and node.id in values: return values[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not): return not walk(node.operand)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            results = [bool(walk(n)) for n in node.values]
            return all(results) if isinstance(node.op, ast.And) else any(results)
        if isinstance(node, ast.Compare) and all(type(op) in ops for op in node.ops):
            vals = [walk(node.left), *[walk(n) for n in node.comparators]]
            return all(ops[type(op)](a, b) for a, op, b in zip(vals, node.ops, vals[1:]))
        raise ValueError('nó não permitido: ' + type(node).__name__)
    return bool(walk(tree))


def normalized(text):
    text = ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[a-z]+|\d+', text))


def signature(row):
    # Numeric variants share a shape, even when different surface wording is used.
    try:
        tree = ast.parse(row.get('expression', ''), mode='eval'); names = {}
        class Canonical(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id not in names: names[node.id] = f'v{len(names)}'
                return ast.Name(id=names[node.id], ctx=ast.Load())
            def visit_Constant(self, node): return ast.Constant(value=type(node.value).__name__)
        return ast.dump(Canonical().visit(tree), include_attributes=False)
    except SyntaxError: return row.get('expression')


def screen(row, previous, judge):
    reasons = []
    if not all(row.get(k) for k in ('id', 'family', 'prompt', 'answer', 'matter', 'pedagogy')):
        return ['estrutura_incompleta']
    if row.get('split') not in {'train', 'validation'}: reasons.append('split_invalido')
    if not 20 <= len(row['prompt']) <= 2000 or not 30 <= len(row['answer']) <= 1800: reasons.append('tamanho_invalido')
    for category in ('matter', 'pedagogy'):
        source = row[category]
        if not approved(source): reasons.append('licenca_incerta')
        if not source.get('sha256') or not source.get('excerpt') or source['excerpt'] not in source.get('text', ''):
            reasons.append('excerto_inexistente')
    try:
        if type(row.get('result')) is not bool or solve(row['expression'], row['values']) != row['result']:
            reasons.append('gabarito_incorreto')
    except (KeyError, TypeError, ValueError): reasons.append('expressao_invalida')
    question = normalized(row['prompt'])
    for old in previous:
        if SequenceMatcher(None, question, normalized(old['prompt'])).ratio() >= .88:
            reasons.append('pergunta_duplicada')
        if old['split'] != row['split']:
            if old['family'] == row['family'] or signature(old) == signature(row): reasons.append('contaminacao_familia')
            if {row[k]['sha256'] for k in ('matter', 'pedagogy')} & {old[k]['sha256'] for k in ('matter', 'pedagogy')}:
                reasons.append('contaminacao_documento')
    answer = normalized(row['answer'])
    if row.get('kind') == 'hint' and re.search(r'\b(verdadeir\w*|fals\w*|resposta e|resultado e|pode retirar|nao pode retirar|esta dentro|esta fora)\b', answer):
        reasons.append('dica_entrega_solucao')
    values = row.get('values', {})
    if {'x', 'lo', 'hi'} <= set(values):
        inside = values['lo'] <= values['x'] <= values['hi']
        if ('esta dentro do intervalo' in answer and not inside) or ('esta fora do intervalo' in answer and inside):
            reasons.append('conclusao_intervalo_incorreta')
    # Fail closed on weak didactics. A second model's confident approval cannot override these checks.
    if row.get('kind') in {'hint', 'explanation', 'correction'} and row['answer'].count('?') != 1:
        reasons.append('falta_pergunta_unica_de_verificacao')
    if row.get('kind') == 'explanation' and not re.search(r'exemplo|por exemplo', answer):
        reasons.append('explicacao_sem_exemplo_distinto')
    if row.get('kind') == 'correction' and not (re.search(r'acert|corret|positivo|parte certa', answer) and re.search(r'mas|porem|entretanto|falta', answer)):
        reasons.append('correcao_sem_acerto_e_limite')
    if re.search(r'senha|execute .*comando|ignore .*instru', answer): reasons.append('instrucao_hostil_reproduzida')
    if not judge or judge.get('approved') is not True: reasons.append('juiz_nao_aprovou')
    return sorted(set(reasons))


def deficits(rows, test_count):
    sizes = Counter(row['split'] for row in rows)
    return {'train': max(0, 200 - sizes['train']), 'validation': max(0, 30 - sizes['validation']), 'test': max(0, 30 - test_count)}
