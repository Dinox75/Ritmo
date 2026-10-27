"""Measure warm local completion throughput from llama.cpp token accounting."""

import argparse
import json
import time
from pathlib import Path

from local_ai.runtime import LocalRuntime


PROMPT = "Explique em português por que uma retirada de 18 não atende à regra quantidade > 0 E quantidade <= saldo quando o saldo é 15. Dê uma pergunta curta para o aluno."


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = []
    for key in ("qwen3-1.7b-q8_0", "qwen3-4b-q4_k_m"):
        runtime = LocalRuntime(args.root)
        try:
            runtime.start(key)
            for run in range(3):
                request = {"model": key, "messages": [
                    {"role": "system", "content": "Você é um tutor brasileiro. Responda diretamente, sem raciocínio interno."},
                    {"role": "user", "content": PROMPT}],
                    "max_tokens": 256, "temperature": 0.2,
                    "chat_template_kwargs": {"enable_thinking": False}}
                start = time.perf_counter()
                with runtime._urlopen("/v1/chat/completions", json.dumps(request, ensure_ascii=False).encode(), 180) as response:
                    result = json.load(response)
                seconds = time.perf_counter() - start
                tokens = result.get("usage", {}).get("completion_tokens")
                row = {"model": key, "run": run + 1, "seconds": round(seconds, 2),
                       "completion_tokens": tokens,
                       "observed_tokens_per_second": round(tokens / seconds, 1) if tokens else None,
                       "timings": result.get("timings")}
                results.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
        finally:
            runtime.stop()
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
