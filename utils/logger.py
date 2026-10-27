"""Log local de diagnóstico, sem console obrigatório no executável Windows."""

import logging
from logging.handlers import RotatingFileHandler

from utils.config import LOG_FILE


def configure_logging(path=LOG_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=2,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(item, RotatingFileHandler) and item.baseFilename == handler.baseFilename
               for item in root.handlers):
        root.addHandler(handler)
    return path
