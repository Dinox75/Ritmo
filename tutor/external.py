"""Pesquisa externa opcional. Somente a consulta confirmada sai do computador."""

import html
import json
import threading
import time
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen


class ExternalUnavailable(ValueError):
    pass


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(value):
    parser = _PlainText()
    parser.feed(str(value))
    return " ".join(html.unescape("".join(parser.parts)).split())


def _read_json(url):
    request = Request(url, headers={"User-Agent": "Ritmo/0.1 (https://github.com/Dinox75/Ritmo)",
                                    "Accept": "application/json"})
    try:
        with urlopen(request, timeout=8) as response:
            body = response.read(350_001)
            if len(body) > 350_000:
                raise ExternalUnavailable("A fonte devolveu dados demais para esta pesquisa.")
            return json.loads(body)
    except HTTPError as error:
        raise ExternalUnavailable(f"Fonte indisponível (HTTP {error.code}); tente mais tarde.") from error
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise ExternalUnavailable("Fonte indisponível; confira a conexão e tente mais tarde.") from error


def wikipedia_search(query):
    """Usa apenas os dois endpoints fixos da Wikipédia em português."""
    search_url = "https://pt.wikipedia.org/w/rest.php/v1/search/page?" + urlencode({"q": query, "limit": 5})
    found = _read_json(search_url).get("pages", [])
    pages = [item for item in found if isinstance(item, dict) and isinstance(item.get("id"), int)]
    if not pages:
        return []
    ids = "|".join(str(item["id"]) for item in pages)
    extract_url = "https://pt.wikipedia.org/w/api.php?" + urlencode({
        "action": "query", "prop": "extracts", "exintro": "1", "explaintext": "1",
        "exchars": "1600", "pageids": ids, "format": "json"})
    extracts = _read_json(extract_url).get("query", {}).get("pages", {})
    accessed = datetime.now(timezone.utc).isoformat()
    result = []
    for item in pages:
        page = extracts.get(str(item["id"]), {})
        title = str(page.get("title") or item.get("title") or item.get("key") or "")[:180]
        excerpt = plain_text(page.get("extract") or item.get("excerpt") or "")[:1600]
        if not title or not excerpt:
            continue
        result.append({"title": title, "url": "https://pt.wikipedia.org/wiki/" + quote(title.replace(" ", "_")),
                       "excerpt": excerpt, "provider": "Wikipédia em português", "accessed_at": accessed,
                       "license": "CC BY-SA 4.0; confira a licença e o histórico da página"})
    return result


class ExternalSearch:
    def __init__(self, searcher=None):
        self.searcher = searcher or wikipedia_search
        self._items = {}
        self._lock = threading.Lock()

    def search(self, query, confirmed=False):
        if confirmed is not True:
            raise ValueError("Revise e confirme a consulta antes de pesquisar.")
        if not isinstance(query, str) or not 2 <= len(query.strip()) <= 240 or "\n" in query:
            raise ValueError("Escreva uma consulta de 2 a 240 caracteres, em uma linha.")
        clean = query.strip()
        results = self.searcher(clean)
        if not isinstance(results, list):
            raise ExternalUnavailable("A fonte devolveu uma resposta inesperada.")
        now = time.monotonic()
        with self._lock:
            self._items = {key: value for key, value in self._items.items() if value[0] > now}
            output = []
            for item in results[:5]:
                if not isinstance(item, dict) or not all(item.get(key) for key in
                                                        ("title", "url", "excerpt", "provider", "accessed_at", "license")):
                    continue
                if not str(item["url"]).startswith("https://pt.wikipedia.org/wiki/"):
                    continue
                source = {key: str(item[key])[:limit] for key, limit in
                          (("title", 180), ("url", 500), ("excerpt", 1600),
                           ("provider", 80), ("accessed_at", 50), ("license", 120))}
                source["id"] = str(uuid.uuid4())
                self._items[source["id"]] = (now + 1800, source)
                output.append(source.copy())
            return {"query": clean, "provider": "Wikipédia em português", "results": output}

    def resolve(self, source_ids):
        if source_ids is None:
            return []
        if (not isinstance(source_ids, list) or len(source_ids) > 3 or
                any(not isinstance(item, str) for item in source_ids) or len(set(source_ids)) != len(source_ids)):
            raise ValueError("Escolha até três fontes externas da pesquisa atual.")
        now = time.monotonic()
        with self._lock:
            if any(key not in self._items or self._items[key][0] <= now for key in source_ids):
                raise ValueError("A pesquisa expirou; pesquise novamente antes de enviar ao tutor.")
            return [self._items[key][1].copy() for key in source_ids]
