"""Classificação básica de executáveis, sem inferir estudo."""

import json
from pathlib import Path


DEFAULT_RULES = Path(__file__).resolve().parents[1] / "config" / "classificacao_apps.json"


def carregar_classificacao(path=DEFAULT_RULES):
    with Path(path).open(encoding="utf-8") as file:
        rules = json.load(file)
    if not isinstance(rules, dict) or any(not isinstance(v, list) for v in rules.values()):
        raise ValueError("classificacao_apps.json deve mapear categorias para listas")
    return rules


def classificar_programa(programa, rules=None):
    rules = rules if rules is not None else carregar_classificacao()
    for categoria, apps in rules.items():
        if programa.casefold() in (app.casefold() for app in apps):
            return categoria
    return None
