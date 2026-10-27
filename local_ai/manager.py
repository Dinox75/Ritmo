"""Background install state for the local tutor, scoped to one application process."""

import threading

from local_ai.installer import install


class InstallManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = {"active": False, "file": "", "done": 0, "total": 0, "error": ""}

    def status(self):
        with self.lock:
            return self.state.copy()

    def start(self, model, root):
        with self.lock:
            if self.state["active"]:
                raise ValueError("Uma instalação já está em andamento.")
            self.state = {"active": True, "file": "", "done": 0, "total": 0, "error": ""}

        def progress(file, done, total):
            with self.lock:
                self.state.update(file=file, done=done, total=total)

        def work():
            try:
                install(model, root, progress)
            except Exception as error:
                with self.lock:
                    self.state["error"] = str(error)
            finally:
                with self.lock:
                    self.state["active"] = False

        threading.Thread(target=work, name="ritmo_model_install", daemon=True).start()
        return self.status()
