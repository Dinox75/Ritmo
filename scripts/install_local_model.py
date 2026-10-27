"""Ação explícita para instalar pesos locais, com progresso e verificação SHA-256."""
import argparse
from local_ai.installer import install


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model", choices=("qwen3-4b-q4_k_m", "qwen3-1.7b-q8_0"))
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    previous = {}
    def progress(name, done, total):
        percent = int(done * 100 / total)
        if previous.get(name) != percent:
            previous[name] = percent
            print(f"{name}: {percent}% ({done}/{total} bytes)", flush=True)
    print(install(args.model, args.root, progress), flush=True)


if __name__ == "__main__":
    main()
