"""Ephemeral API credentials. No secrets are persisted or placed in URLs."""
import hmac
import secrets
import threading
import time
from http.cookies import SimpleCookie, CookieError


class AppSession:
    def __init__(self):
        self.token = secrets.token_urlsafe(32)
        self._codes = {}
        self._lock = threading.Lock()

    def issue_code(self):
        with self._lock:
            self._codes = {k:v for k,v in self._codes.items() if v > time.monotonic()}
            if len(self._codes) >= 4:
                self._codes.pop(next(iter(self._codes)))
            code = secrets.token_urlsafe(24)
            self._codes[code] = time.monotonic() + 300
            return code

    def exchange(self, code):
        if not isinstance(code,str):
            return False
        with self._lock:
            expiry = self._codes.pop(code, 0)
        return expiry > time.monotonic()

    def valid(self, headers):
        authorization = headers.get('Authorization', '')
        if authorization.startswith('Bearer ') and hmac.compare_digest(authorization[7:].encode('utf8'), self.token.encode('ascii')):
            return True
        try:
            cookie = SimpleCookie(); cookie.load(headers.get('Cookie', ''))
            value = cookie.get('ritmo_session')
            return bool(value and hmac.compare_digest(value.value.encode('utf8'),self.token.encode('ascii')))
        except (ValueError,TypeError,CookieError):
            return False

    def cookie(self):
        return f'ritmo_session={self.token}; HttpOnly; SameSite=Strict; Path=/'

    def authorize_browser(self, page, port):
        """In-process QA/launcher helper; never available over unauthenticated HTTP."""
        page.context.add_cookies([{'name':'ritmo_session','value':self.token,
                                  'url':f'http://127.0.0.1:{port}',
                                  'httpOnly':True,'sameSite':'Strict'}])
