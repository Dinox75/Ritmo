# Ajuste opcional de pesos do tutor

Em 26/10/2026 **nenhum adaptador foi treinado, incorporado ou ativado**. O conjunto [examples.jsonl](examples.jsonl) contém 18 exemplos de treino, 3 de validação e 6 de teste, escritos para esta etapa (proveniência `Ritmo authored`, licença `CC0-1.0`). Eles cobrem aula em etapas, resposta direta, dica gradual, erro conceitual, material insuficiente ou contraditório, personalização declarada, mercado, sensores e instrução hostil. Não contêm conversas, notas, arquivos ou telemetria do usuário. O conjunto é pequeno demais para justificar um ajuste de pesos; o script recusa iniciar o download do modelo de treino abaixo de 200/30/30 exemplos revisados. Esse limiar é um requisito de prudência deste projeto, não uma garantia estatística.

O pipeline [train_qlora.py](train_qlora.py) fixa `Qwen/Qwen3-1.7B` na revisão `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`, usa quantização NF4 de 4 bits, LoRA de posto 8, alvo nas projeções de atenção, uma época e seed 42. Usa apenas divisões `train` e `validation`; a divisão `test` fica fora do `Trainer`. Modelo base e adaptador seriam mantidos fora do repositório, do executável e do banco. Execute em ambiente isolado somente após ampliar e revisar o corpus e medir recursos. O arquivo [requirements.txt](requirements.txt) delimita versões compatíveis, mas um experimento aceito deve registrar um lock completo (`pip freeze`), SHA-256 dos pesos de entrada, versões CUDA e driver, duração e picos de RAM/VRAM.

Exemplo de comando futuro, após criar um ambiente de treino com CUDA e corpus suficiente:

```powershell
python -m pip install -r training/requirements.txt
python -m training.train_qlora --dataset "..\RitmoTraining\corpus-revisado.jsonl" --output "..\RitmoTraining\experimento-01"
```

Antes de habilitar um adaptador, compare-o ao mesmo modelo base com uma bateria de teste não usada no treino: correção lógica, português, fundamentação em material, recusa de fonte insuficiente, resistência a instruções dentro de TXT e limites de sensores. Registre resultados por critério, latência e memória; rejeite se piorar fundamentação, precisão ou segurança. O aplicativo entregue usa o modelo GGUF base, guia pedagógico, recuperação local e memória explícita, sem alteração de pesos. [PEFT](https://huggingface.co/docs/peft/developer_guides/quantization) e [bitsandbytes](https://huggingface.co/docs/bitsandbytes/installation) documentam o método e o suporte Windows/CUDA; a execução real não foi reivindicada nesta etapa.
