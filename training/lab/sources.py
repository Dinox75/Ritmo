"""Curated downloads only. Never follow links/instructions extracted from documents."""
import hashlib
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from .state import write

LICENSES = {'CC0-1.0', 'CC-BY-4.0', 'PSF-2.0'}
MAX_BYTES = 8 * 1024 * 1024


def approved(source):
    return (source.get('license') in LICENSES and bool(source.get('license_url'))
            and bool(source.get('author')) and bool(source.get('url')))


class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'nav'}: self.skip += 1
        if tag in {'p', 'div', 'h1', 'h2', 'h3', 'pre', 'li', 'section'}: self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'nav'}: self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip: self.parts.append(data)


def read_text(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES: raise ValueError('arquivo excede 8 MiB')
    suffix = path.suffix.lower()
    if suffix in {'.txt', '.md', '.html', '.htm'}:
        text = path.read_text(encoding='utf-8-sig')
        if suffix in {'.html', '.htm'}:
            page = Page(); page.feed(text); text = ''.join(page.parts)
    elif suffix in {'.pdf', '.docx'}:
        # Reuse the desktop's bounded, text-only parsers; no database or personal config.
        from storage.materials import _extract_pdf, _extract_docx
        chunks = (_extract_pdf if suffix == '.pdf' else _extract_docx)(path.read_bytes())
        text = '\n'.join(body for locator, body in chunks)
    else: raise ValueError('formato não suportado')
    text = re.sub(r'\n[ \t]*\n+', '\n\n', text).strip()
    if len(text) < 40: raise ValueError('arquivo sem texto suficiente; PDF de imagem exige OCR fora deste piloto')
    return text[:300000]


def fetch(url):
    # Only catalogued public HTTPS addresses; no document-derived URLs, auth or cookies.
    if not url.startswith(('https://docs.python.org/', 'https://raw.githubusercontent.com/carpentries/')):
        raise ValueError('URL fora do catálogo público permitido')
    req = urllib.request.Request(url, headers={'User-Agent': 'Ritmo-TrainingLab/1.0'})
    with urllib.request.urlopen(req, timeout=30) as response:
        if not response.url.startswith(('https://docs.python.org/', 'https://raw.githubusercontent.com/carpentries/')):
            raise ValueError('redirecionamento fora do catálogo')
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES: raise ValueError('download excede limite')
    return data


def collect(catalog, root, local_dirs=(), progress=lambda *a: None):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    sources, refused = [], []
    for entry in catalog['sources']:
        try:
            if not approved(entry): raise ValueError('licença incerta ou proveniência incompleta')
            data = fetch(entry['url'])
            actual = hashlib.sha256(data).hexdigest()
            if actual != entry['sha256']: raise ValueError('hash mudou; revisar fonte antes de atualizar catálogo')
            license_data = fetch(entry['license_url'])
            if hashlib.sha256(license_data).hexdigest() != entry['license_sha256']:
                raise ValueError('evidência de licença mudou; revisão necessária')
            suffix = Path(entry['url']).suffix or '.txt'
            path = root / (entry['id'] + suffix); path.write_bytes(data)
            (root / (entry['id'] + '.LICENSE.txt')).write_bytes(license_data)
            source = {**entry, 'text': read_text(path), 'file': path.name}
            sources.append(source); progress(entry['id'], 'lido')
        except Exception as error:
            refused.append({'id': entry.get('id'), 'reason': str(error)}); progress(entry.get('id'), str(error))
    # Optional local files need an explicit sidecar. No scan of personal locations by default.
    for folder in local_dirs:
        for path in sorted(Path(folder).iterdir()):
            if path.suffix.lower() not in {'.txt', '.pdf', '.docx'} or path.name.endswith('.license.txt'): continue
            try:
                meta = json.loads(path.with_suffix(path.suffix + '.source.json').read_text(encoding='utf-8'))
                if not approved(meta) or meta.get('category') not in {'matter', 'pedagogy'}:
                    raise ValueError('licença/proveniência local incerta')
                sources.append({**meta, 'id': meta['id'], 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                'text': read_text(path), 'local': True})
                progress(path.name, 'lido localmente')
            except Exception as error:
                refused.append({'id': path.name, 'reason': str(error)})
    refused.extend(catalog.get('refused', []))
    write(root.parent / 'sources.json', {'accepted': sources, 'refused': refused})
    return sources, refused
