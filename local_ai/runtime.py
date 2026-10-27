"""Managed localhost llama.cpp process; model inference never uses an external API."""

import json
import logging
import os
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from local_ai.installer import default_root, installed, manifest, validate_root, sha256


class ModelUnavailable(RuntimeError):
    pass


class LocalRuntime:
    def __init__(self, root=None):
        self.root = validate_root(root or default_root())
        self.process = None
        self.port = None
        self.model_key = None
        self.api_key = None
        self._lock = threading.RLock()
        self._log_thread = None
        self._recent_log = []

    def status(self, model_key):
        catalog = manifest()["models"]
        if model_key not in catalog:
            raise ValueError("modelo fora do catálogo")
        return {"model": model_key, "installed": installed(self.root, model_key),
                "running": bool(self.process and self.process.poll() is None and self.model_key == model_key),
                "model_root": str(self.root), "external": False,
                "license": catalog[model_key]["license"], "model_bytes": catalog[model_key]["bytes"]}

    @staticmethod
    def _free_port():
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def _urlopen(self, path, data=None, timeout=10):
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data,
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": "Bearer " + self.api_key} if data else {})
        return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=timeout)

    def _drain(self, stream):
        for line in stream:
            message = line.rstrip()
            logging.info("llama.cpp: %s", message)
            self._recent_log.append(message)
            del self._recent_log[:-40]

    def _startup_failure(self):
        recent = "\n".join(self._recent_log).lower()
        if any(term in recent for term in ("out of memory", "cuda error", "failed to allocate", "cuda_malloc")):
            return ModelUnavailable("Memória RAM ou VRAM insuficiente para carregar o modelo. Escolha o modelo menor em Configurações e consulte o diagnóstico.")
        return ModelUnavailable("O motor local encerrou durante a carga. Consulte Configurações → Diagnóstico.")

    def start(self, model_key, *, timeout=90):
        with self._lock:
            if self.process and self.process.poll() is None and self.model_key == model_key:
                return
            self.stop()
            info = manifest()["models"].get(model_key)
            if info is None:
                raise ModelUnavailable("Modelo local desconhecido.")
            if not installed(self.root, model_key):
                raise ModelUnavailable("Instale o modelo local em Configurações antes de conversar.")
            model = self.root / "models" / info["filename"]
            if sha256(model) != info["sha256"]:
                raise ModelUnavailable("O modelo instalado falhou na verificação SHA-256. Reinstale-o.")
            runtime_root = self.root / "runtime" / manifest()["runtime"]["version"]
            executable = next(runtime_root.rglob("llama-server.exe"))
            self.port = self._free_port()
            self.model_key = model_key
            self.api_key = secrets.token_urlsafe(32)
            self._recent_log.clear()
            args = [str(executable), "--model", str(model), "--host", "127.0.0.1",
                    "--port", str(self.port), "--ctx-size", "4096", "--n-gpu-layers", "99",
                    "--threads", "6", "--parallel", "1", "--no-webui",
                    "--cors-origins", "localhost", "--no-cors-credentials"]
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                child_env = os.environ.copy()
                child_env["LLAMA_API_KEY"] = self.api_key
                self.process = subprocess.Popen(args, cwd=executable.parent, stdin=subprocess.DEVNULL,
                                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                text=True, errors="replace", creationflags=flags, env=child_env)
                self._log_thread = threading.Thread(target=self._drain, args=(self.process.stdout,),
                                                    name="ritmo_llama_log", daemon=True)
                self._log_thread.start()
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if self.process.poll() is not None:
                        raise self._startup_failure()
                    try:
                        with self._urlopen("/health", timeout=2) as response:
                            if json.load(response).get("status") == "ok":
                                return
                    except (OSError, ValueError, urllib.error.HTTPError):
                        pass
                    time.sleep(0.5)
                raise ModelUnavailable("O modelo local demorou demais para iniciar. Consulte o diagnóstico.")
            except BaseException:
                self.stop()
                raise

    def complete(self, model_key, instructions, messages, *, timeout=120):
        self.start(model_key)
        payload = {"model": manifest()["models"][model_key]["filename"],
                   "messages": [{"role": "system", "content": instructions}, *messages],
                   "max_tokens": 420, "temperature": 0.3, "stream": False,
                   "chat_template_kwargs": {"enable_thinking": False}}
        try:
            with self._urlopen("/v1/chat/completions", json.dumps(payload, ensure_ascii=False).encode("utf-8"), timeout) as response:
                result = json.load(response)
            answer = result["choices"][0]["message"]["content"].strip()
            if not answer:
                raise ModelUnavailable("O modelo local não retornou texto. Tente novamente.")
            return answer
        except (OSError, ValueError, KeyError, IndexError) as error:
            raise ModelUnavailable("Falha na resposta local. Consulte o diagnóstico e tente novamente.") from error

    def stop(self):
        with self._lock:
            process = self.process
            self.process = None
            self.model_key = None
            self.port = None
            self.api_key = None
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                if process.stdout:
                    process.stdout.close()
