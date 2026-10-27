"""Busca lexical local; retorna apenas trechos das matérias e materiais escolhidos."""

import re
import unicodedata


STOPWORDS = set("a o as os um uma de da do das dos e ou que qual quando como para por com sem no na nos nas sobre "
                "se eu ele ela você voces isso este esta esse essa seria pode porque pois um uns umas a ao "
                "material materiais arquivo arquivos selecionado selecionados conforme segundo exato exata "
                "explique ensine aula pergunta resposta texto trecho fonte".split())


def _fold(value):
    return "".join(char for char in unicodedata.normalize("NFD", value.casefold())
                   if unicodedata.category(char) != "Mn")


def _terms(question):
    values = re.findall(r"\w+", _fold(question), flags=re.UNICODE)
    return list(dict.fromkeys(value for value in values if (len(value) >= 3 or value.isdigit())
                              and value not in STOPWORDS))[:10]


def _excerpt(body, terms, limit=650):
    segments = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", body) if part.strip()]
    if not segments:
        return body[:limit]
    best, score = body[:limit], -1
    for index in range(len(segments)):
        candidate = " ".join(segments[index:index + 2])
        folded = _fold(candidate)
        rank = sum(2 if term in folded else 0 for term in terms) + sum(folded.count(term) for term in terms)
        if rank > score:
            best, score = candidate[:limit], rank
    return best


def search_chunks(database, subject_id, material_ids, question, *, limit=6):
    if not material_ids:
        return []
    terms = _terms(question)
    if not terms:
        return []
    # Apenas tokens normalizados entre aspas entram na sintaxe MATCH.
    expression = " OR ".join('"' + term + '"' for term in terms)
    placeholders = ",".join("?" for _ in material_ids)
    with database.connect() as db:
        rows = db.execute(
            "SELECT c.id AS chunk_id, c.locator, c.body, m.id AS material_id, "
            "m.name AS material_name, m.status FROM material_chunks_fts "
            "JOIN material_chunks c ON c.rowid=material_chunks_fts.rowid "
            "JOIN materials m ON m.id=c.material_id "
            f"WHERE material_chunks_fts MATCH ? AND m.subject_id=? AND m.id IN ({placeholders}) "
            "AND m.status='ready' ORDER BY bm25(material_chunks_fts), c.ordinal LIMIT ?",
            (expression, subject_id, *material_ids, limit))
        results = []
        for row in rows:
            body_terms = set(re.findall(r"\w+", _fold(row["body"]), flags=re.UNICODE))
            overlap = len(set(terms) & body_terms)
            if overlap < (2 if len(terms) >= 4 else 1):
                continue
            results.append({"material_id": row["material_id"], "chunk_id": row["chunk_id"],
                            "material_name": row["material_name"], "locator": row["locator"],
                            "excerpt": _excerpt(row["body"], terms)})
        return results


def opening_chunks(database, subject_id, material_ids, *, limit=5):
    """Abertura curta para uma aula pedida sem palavras chave específicas."""
    if not material_ids:
        return []
    placeholders = ",".join("?" for _ in material_ids)
    with database.connect() as db:
        rows = db.execute(
            "SELECT c.id AS chunk_id, c.locator, c.body, m.id AS material_id, m.name AS material_name "
            "FROM material_chunks c JOIN materials m ON m.id=c.material_id "
            f"WHERE m.subject_id=? AND m.id IN ({placeholders}) AND m.status='ready' "
            "ORDER BY m.imported_at DESC, c.ordinal LIMIT ?", (subject_id, *material_ids, limit))
        return [{"material_id": row["material_id"], "chunk_id": row["chunk_id"],
                 "material_name": row["material_name"], "locator": row["locator"],
                 "excerpt": row["body"][:650]} for row in rows if row["body"].strip()]
