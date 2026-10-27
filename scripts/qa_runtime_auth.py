"""Check that the managed local model rejects unauthenticated browser access."""

import argparse
import json
import socket
import urllib.error
import urllib.request
from pathlib import Path

from local_ai.runtime import LocalRuntime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    runtime = LocalRuntime(args.root)
    port = None
    try:
        runtime.start("qwen3-1.7b-q8_0")
        port = runtime.port
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        payload = json.dumps({"messages": [{"role": "user", "content": "Diga olá."}],
                              "max_tokens": 128,
                              "chat_template_kwargs": {"enable_thinking": False}}).encode("utf-8")
        request = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
                                         data=payload, headers={"Content-Type": "application/json"})
        try:
            opener.open(request, timeout=5).close()
            raise AssertionError("API do modelo aceitou requisição sem autenticação")
        except urllib.error.HTTPError as error:
            if error.code != 401:
                raise AssertionError(f"API respondeu {error.code}, esperado 401") from error
        origin_request = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
                                                method="OPTIONS", headers={
                                                    "Origin": "https://example.invalid",
                                                    "Access-Control-Request-Method": "POST"})
        try:
            with opener.open(origin_request, timeout=5) as response:
                allowed = response.headers.get("Access-Control-Allow-Origin")
        except urllib.error.HTTPError as error:
            allowed = error.headers.get("Access-Control-Allow-Origin")
        if allowed == "https://example.invalid" or allowed == "*":
            raise AssertionError("origem externa aceita no CORS")
        with runtime._urlopen("/v1/chat/completions", payload, 30) as response:
            answer = json.load(response)["choices"][0]["message"]["content"]
        if not answer.strip():
            raise AssertionError("chamada autorizada ficou sem resposta")
    finally:
        runtime.stop()
    if port is not None:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise AssertionError("porta do modelo continuou aberta")
    print("Motor local: 401 sem chave, CORS externo recusado, chamada interna respondeu e porta foi liberada.")


if __name__ == "__main__":
    main()
