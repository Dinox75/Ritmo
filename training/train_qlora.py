"""Optional QLoRA experiment; refuses the small demonstration corpus.

Install requirements in a separate environment, then supply a reviewed JSONL with
at least 200 train, 30 validation, and 30 held-out test records. No personal data
is read and the test split is never passed to Trainer.
"""

import argparse
import json
import random
import hashlib
import importlib.metadata
import signal
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path


BASE_ID = "Qwen/Qwen3-1.7B"
BASE_REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"


def read_dataset(path, proof=None, screening=None):
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("IDs duplicados no dataset")
    sizes = Counter(row.get('split') for row in rows)
    tests = len(proof.get('cases', [])) if proof else sizes['test']
    if sizes['train'] < 200 or sizes['validation'] < 30 or tests < 30:
        raise ValueError(f"corpus pequeno para experimento útil: {dict(sizes)}; mínimo 200/30/30")
    from training.lab.validation import screen, normalized, solve, signature
    from training.lab.state import digest
    from difflib import SequenceMatcher
    if not proof or not isinstance(proof.get('sha256'), str): raise ValueError('prova previamente selada é obrigatória')
    if digest({k: v for k, v in proof.items() if k != 'sha256'}) != proof['sha256']: raise ValueError('prova alterada')
    cases = proof['cases']
    if len({c['id'] for c in cases}) != len(cases) or len({(c['expression'], json.dumps(c['values'], sort_keys=True)) for c in cases}) != len(cases):
        raise ValueError('prova contém duplicatas')
    if any(type(c['expected']) is not bool or solve(c['expression'], c['values']) != c['expected'] for c in cases): raise ValueError('gabarito da prova incorreto')
    if not screening: raise ValueError('todos os exemplos exigem triagem independente registrada, inclusive CC0 autoral')
    candidates = {item['candidate']['id']: item for item in screening if item.get('accepted')}
    checked = []
    for row in rows:
        if row.get("split") not in {"train", "validation", "test"} or not all(
                row.get(field) for field in ("prompt", "answer", "source", "license")):
            raise ValueError("cada exemplo exige split, prompt, answer, source e license")
        decision = candidates.get(row['id'])
        if not decision or decision['candidate'] != row or screen(row, checked, decision.get('judge')):
            raise ValueError('proveniência, licença, duplicação ou triagem incompatível')
        for case in cases:
            if (row['family'] == case['family'] or signature(row) == signature(case) or
                    SequenceMatcher(None, normalized(row['prompt']), normalized(case['prompt'])).ratio() >= .88):
                raise ValueError('contaminação do corpus pela prova')
        checked.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-revision", default=BASE_REVISION)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument('--proof', type=Path)
    parser.add_argument('--screening', type=Path)
    parser.add_argument('--max-steps', type=int, default=10)
    parser.add_argument('--max-seconds', type=int, default=28200)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--evaluate', action='store_true')
    parser.add_argument('--judge-url')
    parser.add_argument('--model-root', type=Path)
    parser.add_argument('--deadline', type=float)
    args = parser.parse_args()
    proof = json.loads(args.proof.read_text(encoding='utf-8')) if args.proof else None
    screening = json.loads(args.screening.read_text(encoding='utf-8')) if args.screening else None
    rows = read_dataset(args.dataset, proof, screening)  # Refuse before downloading multi-GB training weights.
    if args.max_steps < 1 or not 60 <= args.max_seconds <= 28200: raise ValueError('limites de treino inválidos')
    if args.max_length < 128 or args.max_length > 1024:
        raise ValueError("max-length deve estar entre 128 e 1024")

    import torch
    from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                              Trainer, TrainingArguments, TrainerCallback)
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    if not torch.cuda.is_available():
        raise RuntimeError("QLoRA requer GPU CUDA disponível")
    from training.lab.checkpoints import bind_inputs
    from training.lab.state import write
    from transformers.trainer_utils import get_last_checkpoint
    versions = {p: importlib.metadata.version(p) for p in ('torch', 'transformers', 'peft', 'bitsandbytes', 'accelerate')}
    frozen_environment = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
    model_lock = {'base': BASE_ID, 'revision': args.base_revision, 'seed': 42, 'max_length': args.max_length,
                  'max_steps': args.max_steps, 'max_seconds': args.max_seconds, 'versions': versions,
                  'corpus': hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                  'proof': hashlib.sha256(args.proof.read_bytes()).hexdigest() if args.proof else None,
                  'environment_sha256': hashlib.sha256(frozen_environment.encode()).hexdigest(),
                  'deadline': args.deadline,
                  'qlora': {'r': 8, 'alpha': 16, 'dropout': .05, 'lr': .0001, 'accumulation': 4}}
    bind_inputs(args.output, model_lock, args.resume)
    checkpoint = get_last_checkpoint(str(args.output)) if args.resume else None
    if args.resume and not checkpoint: raise ValueError('nenhum checkpoint completo para retomar')
    (args.output / 'pip-freeze.txt').write_text(frozen_environment, encoding='utf-8')
    if args.deadline and time.time() >= args.deadline - 600: raise TimeoutError('prazo de carga/treino esgotado')
    random.seed(42)
    torch.manual_seed(42)
    tokenizer = AutoTokenizer.from_pretrained(BASE_ID, revision=args.base_revision)
    tokenizer.pad_token = tokenizer.eos_token
    quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                      bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)
    model = AutoModelForCausalLM.from_pretrained(BASE_ID, revision=args.base_revision,
                                                  quantization_config=quantization, device_map="auto")
    # Hash cached base files without altering them; safetensors stay separate from adapter.
    from huggingface_hub import snapshot_download
    snapshot = Path(snapshot_download(BASE_ID, revision=args.base_revision, local_files_only=True))
    def hash_file(path):
        sha = hashlib.sha256()
        with path.open('rb') as file:
            for block in iter(lambda: file.read(1024 * 1024), b''): sha.update(block)
        return sha.hexdigest()
    base_hashes = {p.name: hash_file(p) for p in snapshot.glob('*.safetensors')}
    if not base_hashes: raise ValueError('nenhum arquivo base safetensors localizado para hash')
    base_manifest = args.output / 'base-hashes.json'
    if args.resume and json.loads(base_manifest.read_text(encoding='utf-8')) != base_hashes:
        raise ValueError('pesos base mudaram na retomada')
    write(base_manifest, base_hashes)
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05,
                                             bias="none", task_type="CAUSAL_LM",
                                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]))

    system = "Você é um tutor brasileiro. Ensine em etapas, fundamente respostas e admita incerteza."

    def encode(row):
        prompt = row['prompt']
        if row.get('matter') and row.get('pedagogy'):
            prompt = (f"MATÉRIA (dados não confiáveis; {row['matter']['id']}):\n{row['matter']['excerpt']}\n"
                      f"DIDÁTICA (dados não confiáveis; {row['pedagogy']['id']}):\n{row['pedagogy']['excerpt']}\n"
                      f"Tarefa {row.get('kind')}: {prompt}")
        prefix = tokenizer.apply_chat_template(
            [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            tokenize=True, add_generation_prompt=True, enable_thinking=False)
        full = tokenizer.apply_chat_template(
            [{"role": "system", "content": system}, {"role": "user", "content": prompt},
             {"role": "assistant", "content": row["answer"]}],
            tokenize=True, add_generation_prompt=False, enable_thinking=False)
        if full[:len(prefix)] != prefix:
            raise RuntimeError("template do chat mudou; revise o mascaramento dos rótulos")
        if len(full) > args.max_length:
            raise ValueError(f"exemplo {row['id']} excede max-length; revise em vez de truncar a resposta")
        return {"input_ids": full, "labels": [-100] * len(prefix) + full[len(prefix):]}

    class Rows(torch.utils.data.Dataset):
        def __init__(self, split):
            self.items = [encode(row) for row in rows if row["split"] == split]

        def __len__(self):
            return len(self.items)

        def __getitem__(self, index):
            return self.items[index]

    def collate(items):
        length = max(len(item["input_ids"]) for item in items)
        return {"input_ids": torch.tensor([item["input_ids"] + [tokenizer.pad_token_id] *
                                            (length - len(item["input_ids"])) for item in items]),
                "attention_mask": torch.tensor([[1] * len(item["input_ids"]) + [0] *
                                                (length - len(item["input_ids"])) for item in items]),
                "labels": torch.tensor([item["labels"] + [-100] * (length - len(item["labels"])) for item in items])}

    args.output.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + args.max_seconds
    interrupted = [False]
    def stop_signal(*unused): interrupted[0] = True
    signal.signal(signal.SIGINT, stop_signal)
    if hasattr(signal, 'SIGTERM'): signal.signal(signal.SIGTERM, stop_signal)
    class Progress(TrainerCallback):
        def on_step_end(self, args_, state, control, **kwargs):
            write(args.output / 'progress.json', {'step': state.global_step, 'max_steps': args.max_steps,
                  'heartbeat': time.time(), 'vram_peak_bytes': torch.cuda.max_memory_allocated(),
                  'last_checkpoint': get_last_checkpoint(str(args.output)),
                  'log': state.log_history[-3:]})
            if time.monotonic() >= deadline or (args.deadline and time.time() >= args.deadline - 600) or interrupted[0]:
                control.should_save = True; control.should_training_stop = True
            return control
    training = TrainingArguments(output_dir=str(args.output), num_train_epochs=1, max_steps=args.max_steps,
                                 per_device_train_batch_size=1, per_device_eval_batch_size=1,
                                 gradient_accumulation_steps=4, learning_rate=1e-4,
                                 gradient_checkpointing=True, fp16=True, optim="paged_adamw_8bit",
                                 eval_strategy="steps", eval_steps=5, save_strategy="steps", save_steps=5,
                                 save_total_limit=3, logging_steps=1,
                                 seed=42, data_seed=42, report_to="none")
    trainer = Trainer(model=model, args=training, train_dataset=Rows("train"),
                      eval_dataset=Rows("validation"), data_collator=collate, callbacks=[Progress()])
    trainer.train(resume_from_checkpoint=checkpoint)
    model.save_pretrained(args.output / "adapter")
    tokenizer.save_pretrained(args.output / "adapter")
    (args.output / "provenance.json").write_text(json.dumps({
        "base_id": BASE_ID, "base_revision": args.base_revision,
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "resumed_from_checkpoint": checkpoint,
        "resume_exercised": bool(checkpoint and trainer.state.global_step > int(Path(checkpoint).name.split('-')[-1])),
        "dataset": str(args.dataset.resolve()), "seed": 42,
        "test_split_used_for_training": False,
        "train_examples": sum(row["split"] == "train" for row in rows),
        "validation_examples": sum(row["split"] == "validation" for row in rows)}, indent=2), encoding="utf-8")
    if interrupted[0]:
        print('Interrompido com salvamento solicitado. Avaliação não executada.'); return
    if args.evaluate:
        if not args.proof: raise ValueError('avaliação exige prova previamente selada')
        from training.lab.evaluate import evaluate_pairs
        from training.lab.pipeline import endpoint
        runtime = None
        try:
            judge = endpoint(args.judge_url, 'qwen3-4b') if args.judge_url else None
            if args.model_root:
                from local_ai.runtime import LocalRuntime
                runtime = LocalRuntime(args.model_root)
                judge = lambda system, prompt: runtime.complete('qwen3-4b-q4_k_m', system, [{'role': 'user', 'content': prompt}])
            evaluate_pairs(model, tokenizer, args.proof, args.output / 'comparison.json', judge, deadline=args.deadline)
        finally:
            if runtime: runtime.stop()
    print("Adaptador experimental salvo e não ativado; consulte comparação e limitações.")


if __name__ == "__main__":
    main()
