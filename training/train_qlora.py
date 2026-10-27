"""Optional QLoRA experiment; refuses the small demonstration corpus.

Install requirements in a separate environment, then supply a reviewed JSONL with
at least 200 train, 30 validation, and 30 held-out test records. No personal data
is read and the test split is never passed to Trainer.
"""

import argparse
import json
import random
from collections import Counter
from pathlib import Path


BASE_ID = "Qwen/Qwen3-1.7B"
BASE_REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"


def read_dataset(path):
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("IDs duplicados no dataset")
    for row in rows:
        if row.get("split") not in {"train", "validation", "test"} or not all(
                row.get(field) for field in ("prompt", "answer", "source", "license")):
            raise ValueError("cada exemplo exige split, prompt, answer, source e license")
        if row["source"] != "Ritmo authored" or row["license"] != "CC0-1.0":
            raise ValueError("revise proveniência e licença antes de treinar")
    sizes = Counter(row["split"] for row in rows)
    if any(sizes[key] < minimum for key, minimum in (("train", 200), ("validation", 30), ("test", 30))):
        raise ValueError(f"corpus pequeno para experimento útil: {dict(sizes)}; mínimo 200/30/30")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-revision", default=BASE_REVISION)
    parser.add_argument("--max-length", type=int, default=512)
    args = parser.parse_args()
    rows = read_dataset(args.dataset)  # Refuse before downloading multi-GB training weights.
    if args.max_length < 128 or args.max_length > 1024:
        raise ValueError("max-length deve estar entre 128 e 1024")

    import torch
    from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                              Trainer, TrainingArguments)
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    if not torch.cuda.is_available():
        raise RuntimeError("QLoRA requer GPU CUDA disponível")
    random.seed(42)
    torch.manual_seed(42)
    tokenizer = AutoTokenizer.from_pretrained(BASE_ID, revision=args.base_revision)
    tokenizer.pad_token = tokenizer.eos_token
    quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                      bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16)
    model = AutoModelForCausalLM.from_pretrained(BASE_ID, revision=args.base_revision,
                                                  quantization_config=quantization, device_map="auto")
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05,
                                             bias="none", task_type="CAUSAL_LM",
                                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]))

    system = "Você é um tutor brasileiro. Ensine em etapas, fundamente respostas e admita incerteza."

    def encode(row):
        prefix = tokenizer.apply_chat_template(
            [{"role": "system", "content": system}, {"role": "user", "content": row["prompt"]}],
            tokenize=True, add_generation_prompt=True, enable_thinking=False)
        full = tokenizer.apply_chat_template(
            [{"role": "system", "content": system}, {"role": "user", "content": row["prompt"]},
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
    training = TrainingArguments(output_dir=str(args.output), num_train_epochs=1,
                                 per_device_train_batch_size=1, per_device_eval_batch_size=1,
                                 gradient_accumulation_steps=4, learning_rate=1e-4,
                                 gradient_checkpointing=True, fp16=True, optim="paged_adamw_8bit",
                                 eval_strategy="epoch", save_strategy="epoch", logging_steps=10,
                                 seed=42, data_seed=42, report_to="none")
    trainer = Trainer(model=model, args=training, train_dataset=Rows("train"),
                      eval_dataset=Rows("validation"), data_collator=collate)
    trainer.train()
    model.save_pretrained(args.output / "adapter")
    tokenizer.save_pretrained(args.output / "adapter")
    (args.output / "provenance.json").write_text(json.dumps({
        "base_id": BASE_ID, "base_revision": args.base_revision,
        "dataset": str(args.dataset.resolve()), "seed": 42,
        "test_split_used_for_training": False,
        "train_examples": sum(row["split"] == "train" for row in rows),
        "validation_examples": sum(row["split"] == "validation" for row in rows)}, indent=2), encoding="utf-8")
    print("Adaptador experimental salvo. Avalie no conjunto test separado antes de qualquer uso no aplicativo.")


if __name__ == "__main__":
    main()
