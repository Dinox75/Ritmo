# Executar o laboratório sem depender do PC

Nenhuma máquina foi contratada, arquivo enviado ou cobrança ativada nesta etapa.
Só prossiga numa instância paga depois de o Vinicius autorizar um teto em USD,
incluindo GPU, disco, impostos e eventual transferência. O corpus atual é
insuficiente: **não vale pagar pelo treino ainda**.

## Ambiente proposto

Linux x86_64, Python 3.11, CUDA 12.4, GPU de 24 GB (RTX 3090/4090/A5000),
32 GB RAM e 50 GB de disco **persistente**. Não confundir disco do contêiner
com volume persistente. Pesos de treino são safetensors Qwen/Qwen3-1.7B,
Apache-2.0, revisão `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`.
GGUF e o runtime CUDA do Windows não são pesos nem runtime de treino Linux.
Os pesos base não são sobrescritos. Reserve aproximadamente 4 GB para os pesos
base, além de cache, ambientes, fontes e checkpoints; planeje 50 GB livres.

Documentação conferida em 13/11/2026:

- [Qwen3 1.7B e licença](https://huggingface.co/Qwen/Qwen3-1.7B)
- [NF4/QLoRA no PEFT](https://huggingface.co/docs/peft/developer_guides/quantization)
- [bitsandbytes e compatibilidade](https://huggingface.co/docs/bitsandbytes/installation)
- [Trainer 4.51.3 / retomada](https://huggingface.co/docs/transformers/v4.51.3/en/trainer)
- [Armazenamento Runpod](https://docs.runpod.io/pods/storage/types)
- [Preços Runpod](https://www.runpod.io/pricing)

As APIs foram consultadas; instalação dessas versões e treino CUDA **não foram
validados neste PC**. Dependências diretas estão fixadas em requirements-linux.txt;
o treino grava pip-freeze completo e recusa diferenças nas versões comparadas.

Após autorização, em disco persistente (exemplo /workspace):

```bash
git clone --branch feat/ritmo-training-lab https://github.com/Dinox75/Ritmo.git /workspace/ritmo-lab
cd /workspace/ritmo-lab
python3.11 -m venv /workspace/venv
source /workspace/venv/bin/activate
export HF_HOME=/workspace/hf-cache
export TMPDIR=/workspace/tmp
mkdir -p "$TMPDIR" /workspace/runs
python -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124
python -m pip install -r training/lab/requirements-linux.txt
python -m pip freeze > /workspace/environment.lock.txt
python -c 'import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))'
```

Para geração/verificação sem GPU de treino, use dois servidores llama.cpp
Linux previamente instalados, com modelos 1.7B e 4B separados, **somente loopback**.
`--n-gpu-layers 0` usa CPU. As entradas nunca vão para serviços de inferência externos:

```bash
llama-server --model /workspace/models/qwen3-1.7b.gguf --host 127.0.0.1 --port 8781 --n-gpu-layers 0 --ctx-size 4096 --parallel 1
llama-server --model /workspace/models/qwen3-4b.gguf --host 127.0.0.1 --port 8784 --n-gpu-layers 0 --ctx-size 4096 --parallel 1
```

Esses são processos distintos; rode em serviços/tmux separados. Não exponha as
portas na internet. Modelo/quantização do juiz precisam constar no relatório do
ambiente; o identificador enviado por API não certifica qual arquivo o servidor usa.

## Comando único do fluxo e painel

```bash
python -m training.lab.pipeline --run /workspace/runs/piloto --mode pilot --limit 500 \
  --generator-url http://127.0.0.1:8781 --judge-url http://127.0.0.1:8784
python -m training.lab.panel --run /workspace/runs/piloto --port 8765
```

`--mode prepare` termina após triagem/diagnóstico, sem importar PyTorch ou baixar
pesos de treino. `pilot` solicita no máximo 10 passos se os mínimos forem atingidos.
`long` solicita até 10.000 passos, limitado a 7h50 de treino, e exige `--pilot-proof`
com provenance.json de **retomada CUDA realmente exercitada** e corpus idêntico.
Os quatro grupos atuais de geração são um piloto limitado, não garantem 200/30
exemplos únicos; ampliar o número solicitado não resolve falta de diversidade.
Sem corpus suficiente o fluxo encerra bloqueado antes de baixar pesos.

Para manter ativo após fechar navegador, Codex e PC, rode cada comando em `tmux`
na máquina remota e desconecte com Ctrl+B, D. O serviço precisa existir no servidor;
fechar o PC não desliga a instância remota. Uma alternativa com systemd instalado:

```bash
sudo systemd-run --unit=ritmo-pilot --property=WorkingDirectory=/workspace/ritmo-lab \
  --property=RuntimeMaxSec=28800 --property=TimeoutStopSec=300 \
  --setenv=HF_HOME=/workspace/hf-cache --setenv=TMPDIR=/workspace/tmp \
  /workspace/venv/bin/python -m training.lab.pipeline --run /workspace/runs/piloto \
  --mode pilot --limit 500 --generator-url http://127.0.0.1:8781 --judge-url http://127.0.0.1:8784
sudo systemd-run --unit=ritmo-panel --property=WorkingDirectory=/workspace/ritmo-lab \
  /workspace/venv/bin/python -m training.lab.panel --run /workspace/runs/piloto --port 8765
```

No computador do estudante, `ssh -N -L 8765:127.0.0.1:8765 usuario@host`, depois
abra http://127.0.0.1:8765. O painel é somente leitura; não inicia comandos.
Não publique um link de proxy HTTP público. O acesso depende do SSH autenticado.

## Interrupção e retomada

Checkpoints a cada 5 passos incluem adaptador, otimizador, scheduler e RNG
(não usar save_only_model). Sinais SIGINT/SIGTERM solicitam salvamento ao fim do
passo. Queda abrupta/OOM pode impedir esse salvamento: retome o último checkpoint
completo, nunca prometa recuperar o passo interrompido.

Teste futuro **real**: interromper o piloto depois do checkpoint-5 e antes do10;
reexecutar o mesmo comando com `--resume`; conferir avanço além do checkpoint,
estados carregados e provenance.json com resume_exercised=true. Testes unitários
de manifesto/interrupção não demonstram retomada CUDA. Só depois faça execução
longa em novo diretório com corpus idêntico e `--pilot-proof /workspace/runs/piloto/training/provenance.json`.

O manifesto rejeita alteração de código, catálogo, arquivos locais, corpus,
prova, revisão do modelo, parâmetros e versões verificadas na retomada. Se um
processo morrer abruptamente pode sobrar .worker.lock: confira o PID e a ausência
do processo **antes** de remover somente esse arquivo. Não apague checkpoints.

A prova é usada somente depois do treino, não para escolher checkpoint. A
comparação é base com adaptador desativado versus adaptador ativo no mesmo
modelo NF4, contexto e parâmetros. Um juiz ausente/inconclusivo impede aprovação.
Não exporta GGUF nem ativa o adaptador no Ritmo.

## Oito horas e cobrança

O prazo do treinador é 28.200 s (7h50), com 10 min de margem dentro de 8h.
O watchdog de 8h limita o **processo**, não a cobrança. Coleta, geração, avaliação
e falhas podem consumir esse orçamento; um encerramento forçado pode deixar só
o checkpoint anterior. O prazo não é uma garantia de salvamento.

Referência pública de 13/11/2026: RTX4090 24GB US$0,89/h; 8h = US$7,12.
Volume de rede de 50GB a US$0,07/GB/mês = US$3,50/mês enquanto existir.
Piloto inicial sugerido: até 1h, GPU US$0,89 + armazenamento proporcional,
**teto proposto US$2**, sujeito à cotação/região/impostos. Noite: **teto proposto
US$10** para computação de até8h mais disco temporariamente provisionado;
retenção de disco deve ter prazo e teto próprios. São estimativas, não contratação.
Só autorizar depois de resolver insuficiência/qualidade do corpus.

Parar se: OOM repetido; nenhum checkpoint completo; retomada incompatível;
loss não finita; limite de tempo; regressão lógica/hostil ou avaliação inconclusiva.
Confira no console a tarifa efetiva antes de iniciar e o gasto acumulado.
Depois copie apenas resultados explicitamente escolhidos, por exemplo:

```bash
scp -r usuario@host:/workspace/runs/piloto ./resultados-piloto
```

Copiar arquivos para a máquina remota continua exigindo autorização de envio.
Não copie o banco pessoal. Para encerrar cobrança de GPU, **pare/termine a
instância no console do provedor** e confirme o estado e faturamento. Desligar
Linux ou matar Python não assegura isso. Apague volume persistente só após
baixar e verificar hashes dos resultados; volume retido pode continuar cobrando.
