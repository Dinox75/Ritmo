"""Trusted exercise constructors. No model output and no held-out exam are inputs."""
import ast
import itertools
from .validation import solve


FAMILIES = [
    dict(family='inclusive_range', label='Limites inclusivos', split='train',
         expression='t >= lo and t <= hi', values={'t': 2, 'lo': 2, 'hi': 8},
         mistake='t > lo and t < hi', concept='>= e <= incluem igualdade nas fronteiras',
         cues=['limite', 'igualdade', '>=', '<='], source_terms=['Operações booleanas']),
    dict(family='exclusive_range', label='Limites exclusivos', split='train',
         expression='t > lo and t < hi', values={'t': 8, 'lo': 2, 'hi': 8},
         mistake='t >= lo and t <= hi', concept='> e < excluem igualdade nas fronteiras',
         cues=['limite', 'igualdade', 'estrito', 'exclu', 'fronteira'], source_terms=['Operações booleanas']),
    dict(family='conjunction_three', label='E: todas as condições', split='train',
         expression='a and b and not c', values={'a': True, 'b': True, 'c': True},
         mistake='a or b or not c', concept='E exige todas as condições, inclusive a terceira condição negada',
         cues=['terceira', 'todas', 'conjun', 'operador e', ' and ', 'condicoes'], source_terms=['Operações booleanas']),
    dict(family='negation_gate', label='NÃO: inversão', split='train',
         expression='not bloqueado', values={'bloqueado': False},
         mistake='bloqueado', concept='NÃO inverte o valor lógico da condição',
         cues=['nao', 'not', 'inver', 'negac', 'bloqueado'], source_terms=['Operações booleanas']),
    dict(family='precedence_or_and', label='Precedência E antes de OU', split='train',
         expression='a or b and c', values={'a': True, 'b': False, 'c': False},
         mistake='(a or b) and c', concept='E tem precedência sobre OU; parênteses mudam o agrupamento',
         cues=['primeiro', 'precedencia', 'parentes', 'agrup', 'ordem'], source_terms=['Operações booleanas']),
    dict(family='de_morgan', label='Negação de condição composta', split='train',
         expression='not (expirado or revogado)', values={'expirado': False, 'revogado': True},
         mistake='not expirado or not revogado', concept='Negar OU exige E entre as condições negadas',
         cues=['negac', 'negar', 'parentes', 'expirado', 'revogado', 'de morgan'], source_terms=['Operações booleanas']),
    dict(family='disjunction_inclusive', label='OU inclusivo', split='validation',
         expression='a or b', values={'a': True, 'b': True},
         mistake='(a or b) and not (a and b)', concept='OU inclusivo admite que ambas as condições sejam satisfeitas',
         cues=['ambas', 'pelo menos', 'inclusiv', 'operador ou', 'duas'], source_terms=['Operações booleanas']),
    dict(family='exclusive_or', label='OU exclusivo composto', split='validation',
         expression='(a or b) and not (a and b)', values={'a': True, 'b': True},
         mistake='a or b', concept='Exatamente uma condição: excluir o caso em que ambas ocorrem',
         cues=['ambas', 'exatamente uma', 'exclusiv', 'duas'], source_terms=['Operações booleanas']),
    dict(family='chained_boundary', label='Comparação encadeada e fronteira mista', split='validation',
         expression='lo < t <= hi', values={'lo': 2, 't': 6, 'hi': 6},
         mistake='lo < t < hi', concept='Comparação encadeada exige os dois lados; só o limite superior é inclusivo',
         cues=['limite superior', 'encade', 'dois lados', '<=', 'igualdade'], source_terms=['Comparações']),
    dict(family='nested_condition', label='Condição obrigatória com alternativas', split='validation',
         expression='conta and (cota or isencao)', values={'conta': False, 'cota': True, 'isencao': True},
         mistake='conta and cota or isencao', concept='A conta é obrigatória mesmo quando uma alternativa é satisfeita',
         cues=['obrigat', 'conta', 'parentes', 'alternativa', 'agrup'], source_terms=['Operações booleanas']),
]


def trace(expression, values):
    tree = ast.parse(expression, mode='eval')
    return [{'expression': ast.unparse(node), 'result': solve(ast.unparse(node), values)}
            for node in ast.walk(tree) if isinstance(node, (ast.Compare, ast.BoolOp, ast.UnaryOp))]


def contrast(expression, values):
    expected = solve(expression, values)
    domains = [[value, not value] if type(value) is bool else list(dict.fromkeys([value, 0, 1, 3, 5, 7, 9])) for value in values.values()]
    for combination in itertools.product(*domains):
        other = dict(zip(values, combination))
        if 'lo' in other and other['lo'] > other['hi']: continue
        if other != values and solve(expression, other) != expected:
            return {'expression': expression, 'values': other, 'expected': not expected,
                    'trace': trace(expression, other)}
    raise ValueError('família sem exemplo contrastante verificável')


def build_tasks(limit=30):
    if not 1 <= limit <= 30:
        raise ValueError('piloto tem 30 casos distintos; não repetir nem variar números para preencher a meta')
    result = []
    for spec in FAMILIES:
        expected = solve(spec['expression'], spec['values'])
        conclusion = solve(spec['mistake'], spec['values'])
        if expected == conclusion: raise ValueError('equívoco não produz erro neste caso')
        name, value = next(iter(spec['values'].items()))
        fact = f'{name} = {value}'
        student = {'correct_fact': fact, 'expression': spec['mistake'], 'conclusion': conclusion,
                   'text': f'Observei corretamente {fact}. Apliquei {spec["mistake"]} e concluí {conclusion}.'}
        for kind in ('hint', 'correction', 'explanation'):
            exercise = f'Condição: {spec["expression"]}. Valores: {spec["values"]}. A condição é satisfeita? Explique o raciocínio.'
            result.append({**spec, 'index': len(result), 'kind': kind, 'exercise': exercise,
                           'student': student, 'student_attempt': student['text'], 'expected': expected,
                           'solution': trace(spec['expression'], spec['values']),
                           'example': contrast(spec['expression'], spec['values'])})
    return result[:limit]
