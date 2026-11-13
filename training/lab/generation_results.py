"""Summarize observed generation, never evidence of adapter training."""
from collections import Counter, defaultdict
import re


def exercise_preserved(prompt, task):
    if not isinstance(prompt, str): return False
    compact = re.sub(r'\s+', '', prompt).lower()
    if re.sub(r'\s+', '', task['expression']).lower() not in compact: return False
    for name, value in task['values'].items():
        expected = ('true|verdadeiro' if value else 'false|falso') if type(value) is bool else re.escape(str(value))
        if not re.search(r'\b' + re.escape(name) + r'''['"]?\s*(?:=|:|é|e)\s*(?:''' + expected + r')(?![\w]|[.,]\d)(?!\s*[-+*/])', prompt, re.I): return False
    return True


def summarize(items):
    families, kinds, cells, reasons = {}, {}, {}, Counter()
    for item in items:
        task = item['task']
        for table, key in ((families, task['family']), (kinds, task['kind']), (cells, task['family'] + '|' + task['kind'])):
            cell = table.setdefault(key, {'label': task.get('label', key) if table is families else key,
                                          'generated': 0, 'approved': 0, 'rejected': 0, 'pending': 0})
            cell['generated'] += 1; cell['approved'] += item.get('accepted') is True
            cell['rejected'] += item.get('accepted') is False; cell['pending'] += item.get('accepted') is None
        reasons.update(item.get('reasons', []))
    return {'total': len(items), 'approved': sum(bool(i.get('accepted')) for i in items),
            'by_family': families, 'by_kind': kinds, 'by_cell': cells, 'reasons': dict(reasons.most_common())}


def split_legacy(answer):
    """Only extract an actually generated question; never insert punctuation/text."""
    if not isinstance(answer, str): raise ValueError('answer deve ser texto')
    if answer.count('?') != 1: return answer, ''
    end = answer.index('?') + 1
    boundaries = list(re.finditer(r'[.!](?:\s+|$)|\n', answer[:end]))
    start = boundaries[-1].end() if boundaries else 0
    question = answer[start:end].strip()
    return (answer[:start] + answer[end:]).strip(), question
