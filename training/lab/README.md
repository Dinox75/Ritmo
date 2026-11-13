# Laboratório privado do tutor

Este laboratório funciona separado do banco, configuração e aplicativo pessoal.
Na [continuação da PR9](../../docs/qa-training-lab-two-stage.md), exercícios,
gabaritos e tentativas são construídos por código em dez famílias. O modelo só
gera intervenção e pergunta em campos separados. A comparação pareada local
ficou0/30 para ambas as abordagens na rubrica comum; é necessário corrigir a
qualidade pedagógica/avaliação antes de ampliar o corpus. Não houve treino.
O comando avança sozinho até concluir ou registrar bloqueio. **Não há adaptador
treinado nesta entrega**: o primeiro ensaio teve0/12 aprovados e a comparação seguinte
recusou todos os30 candidatos novos; os históricos estão preservados.
Veja [o relatório](../../docs/qa-training-lab.md) e [o guia Linux/GPU/custos](REMOTE.md).

## Fluxo

`coletar → preparar → validar → diagnosticar → treinar → avaliar → relatório`

O catálogo [catalog.json](catalog.json) contém três documentos Python em português
(matéria, PSF-2.0) e três documentos The Carpentries (didática, CC-BY-4.0).
Downloads e evidências de licença precisam corresponder aos hashes registrados.
Alterações na fonte interrompem a coleta daquela entrada; não atualizam o hash
silenciosamente. Não há busca aberta autônoma por novas licenças: o catálogo foi
pesquisado nesta etapa e cada nova fonte exige conferência antes de entrar nele.
The Carpentries permite adaptação com atribuição; mantenha avisos completos,
links de licença e indicação de alterações ao redistribuir corpus/adaptadores.
PSF-2.0 exige preservar os avisos aplicáveis; os downloads incluem sua licença.
Compatibilidade técnica da licença não é garantia sobre quaisquer dados pessoais
que alguém coloque voluntariamente numa pasta local.

Cada candidato carrega o excerto literal e proveniência da matéria e da didática.
As instruções nos documentos nunca se tornam comandos ou URLs para baixar.
O gabarito usa somente comparações, E, OU e NÃO de uma AST limitada; não usa eval,
exec ou código gerado. Resultados privados são metadados, não exemplos confiáveis
por si. Há verificações conservadoras de texto e um juiz distinto, cuja opinião
continua sendo estimativa. O ensaio exploratório mostrou o juiz aprovando erro.

As divisões são por famílias e documentos, com assinatura AST para detectar
variantes de números/nomes. A prova autoral CC0 é selada antes da geração;
o caso hostil de `18 <= 15` é exclusivamente regressão. O gerador não recebe
essa prova nem os gabaritos dela. Testes só entram depois do último checkpoint,
nunca na escolha de checkpoint. Limiares 200/30/30 não são garantia estatística.
As dez famílias atuais são limitadas a30 intervenções; não preenchem esses mínimos
sem ampliar a cobertura. Nunca multiplique exemplos para satisfazer contagens.

## Windows: comandos de reprodução

Na worktree `A:\Projetos & Estudos\Ritmo\TrainingLab`:

```powershell
$py = 'A:\Projetos & Estudos\Ritmo\Repositorio\.venv\Scripts\python.exe'
$models = 'A:\Projetos & Estudos\Ritmo\Modelos\RitmoModels'
& $py -m training.lab.pipeline --run 'A:\Projetos & Estudos\Ritmo\Laboratorio\nova-preparacao' --mode prepare --limit 12 --model-root $models
& $py -m training.lab.pipeline --run 'A:\Projetos & Estudos\Ritmo\Laboratorio\novo-piloto' --mode pilot --limit 30 --model-root $models
& $py -m training.lab.pipeline --run 'A:\Projetos & Estudos\Ritmo\Laboratorio\nova-longa' --mode long --limit 30 --model-root $models --pilot-proof 'A:\caminho\piloto\training\provenance.json'
& $py -m training.lab.panel --run 'A:\Projetos & Estudos\Ritmo\Laboratorio\validated-v2-20261113' --port 8765
& $py scripts\qa_training_lab.py --run 'A:\Projetos & Estudos\Ritmo\Laboratorio\validated-v2-20261113' --output 'A:\Projetos & Estudos\Ritmo\Laboratorio\nova-qa'
& $py -m unittest discover -s tests -q
```

O piloto e a longa **param por insuficiência de corpus no estado atual**, antes
de baixar pesos. Esses dois comandos são reprodução do fluxo, não evidência de
treino. A CLI retorna2 quando bloqueada,1 em falha e130 em interrupção.
Para retomar, repita exatamente o comando original acrescentando --resume.
Não altere corpus, modelos, catálogo, parâmetros ou código. O relógio absoluto
não reinicia na retomada. Se precisar alterar algo, preserve a execução e use
outra pasta. O prazo inclui preparação e é supervisionado no subprocesso;
salvamento a tempo não é garantido em OOM ou queda abrupta.

`prepare` não requer PyTorch/GPU de treino; para inferência inteiramente CPU,
use --generator-url e --judge-url de dois llama-server com -ngl0, como em REMOTE.md.
No Windows o modo --model-root reutiliza os GGUF verificados já instalados.
O painel em http://127.0.0.1:8765 é somente leitura. Pode ser reaberto com
`scripts/open_training_lab.py --run ...`, via pythonw/atalho, sem terminal.
Fechar o painel não mata o trabalho separado. O atalho abre o painel, nunca inicia
treinamento nem troca o modelo do aplicativo.

## Entradas locais opcionais

Nenhuma pasta pessoal é lida por padrão. Para usar uma pasta explicitamente:
`--local-dir A:\MateriaisDoLaboratorio`. Coloque TXT UTF-8, PDF com texto ou DOCX
e um sidecar `arquivo.ext.source.json` para cada arquivo:

```json
{"id":"meu-material","category":"matter","split":"train","author":"Autor real","url":"https://origem.example/material","license":"CC-BY-4.0","license_url":"https://origem.example/licenca","title":"Título"}
```

Use somente licença/proveniência verdadeiras. Sem sidecar ou licença suportada,
o arquivo é recusado. Licenças aceitas no piloto: CC0-1.0, CC-BY-4.0, PSF-2.0;
outras podem ser compatíveis, mas exigem análise e extensão explícita. PDF de
imagem é recusado, não há OCR neste piloto. Nenhum arquivo local é enviado à rede;
somente os downloads públicos fixados no catálogo acessam a internet.

## Arquivos da execução

- state.json / events.jsonl: fases, sinais, contagens, recursos e ações sugeridas.
- originals/ e sources.json: arquivos, avisos de licença, hashes e recusas.
- candidates.json: bruto, candidato, dupla evidência, juiz e razões de descarte.
- corpus.jsonl / preparation-lock.json: só aprovados e hashes de retomada.
- proof.json: prova fixada e critérios prévios, separada da preparação.
- model-metrics.jsonl: uso de tokens/timings retornados pelo runtime Windows.
- training/: ambiente, pesos-base identificados por hash, checkpoints completos,
  métricas e comparison.json, somente se houver treino real.
- report.md / report.json: resultado e bloqueios. `Não avaliado` é diferente de aprovado.

Use diretórios de execução fora do Git. O laboratório recusa escrita em uma
execução existente sem --resume. Artefatos e originais nunca devem ser colocados
no diretório do banco pessoal. Não há exportação/ativação automática de adaptador.
