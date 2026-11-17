"""Allowlisted startup evidence; never serialize headers, codes, cookies or URLs."""
import json
import logging
import os
import re
import time

BEGAN = time.monotonic()
PHASES = {'executable', 'native', 'authorization', 'qa', 'shutdown'}
STATES = {'started','ready','created','before_show','shown','loaded','requested',
          'authorized','failed','fallback','closing','closed','unavailable','connected'}


def event(name, phase, state, **fields):
    if not re.fullmatch(r'[a-z_]{1,50}', name) or phase not in PHASES or state not in STATES:
        raise ValueError('Evento de diagnóstico inválido')
    allowed = {'port','surface','error_type','cdp_requested'}
    if fields.keys() - allowed:
        raise ValueError('Campo de diagnóstico não permitido')
    if 'port' in fields and (type(fields['port']) is not int or not 0 <= fields['port'] <= 65535):
        raise ValueError('Porta inválida')
    if 'surface' in fields and fields['surface'] not in {'authorization','application','other'}:
        raise ValueError('Superfície inválida')
    if 'error_type' in fields and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,80}',fields['error_type']):
        raise ValueError('Tipo de erro inválido')
    if 'cdp_requested' in fields and type(fields['cdp_requested']) is not bool:
        raise ValueError('Estado CDP inválido')
    record = {'event':name,'phase':phase,'state':state,'pid':os.getpid(),
              'elapsed_ms':round((time.monotonic()-BEGAN)*1000),**fields}
    logging.info('RITMO_LIFECYCLE %s',json.dumps(record,ensure_ascii=True))
    return record
