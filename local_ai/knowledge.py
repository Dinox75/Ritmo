"""Versioned source catalog bundled for transparent, offline tutor context."""

import json
from pathlib import Path


PATH = Path(__file__).with_name("knowledge.json")


def catalog():
    return json.loads(PATH.read_text(encoding="utf-8"))


def prompt_summary():
    data = catalog()
    lines = ["Catálogo local de fontes, verificado em " + data["checked_at"] + ". "
             "São resumos originais de escopo, não dados atuais nem textos integrais."]
    for item in data["pedagogy"]:
        lines.append(f"- {item['name']} ({item['year']}): {item['use']}")
    for item in data["academic_and_labor_sources"]:
        lines.append(f"- {item['name']}: {item['scope']} URL: {item['url']}")
    lines.append("Para números acadêmicos ou trabalhistas, declare ausência de dados atuais e indique a fonte adequada. "
                 "INEP descreve ensino superior; Novo Caged descreve vínculos formais de trabalho. "
                 "Não inferir demanda profissional de matrículas ou vagas de curso. Não inventar estatísticas.")
    return "\n".join(lines)
