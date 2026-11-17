# Laboratório privado do tutor — plano de implementação

Objetivo: coleta reproduzível de fontes permissivas, candidatos gerados localmente,
triagem independente, QLoRA opcional e comparação base/adaptador, sem tocar no Ritmo pessoal.
Execução direta autorizada no pedido; nenhuma etapa exige revisão exemplo a exemplo.

Arquitetura escolhida: pacote Python `training.lab`, CLI persistente e painel HTTP
somente leitura em loopback. Reutilizar extração, runtime GGUF e treinador existentes;
não embutir treino no processo desktop. Alternativas descartadas: serviço pago de
geração (privacidade/custo) e painel com comandos remotos (aumenta superfície de ataque).

Restrições: originais, corpus, pesos, checkpoints e dados pessoais fora do Git;
sem upload, contratação ou ativação automática. Base aceb8a7. Os commits indicados
e065a0f/77ecdc6 e patch não estavam disponíveis após busca local e fetch.

- [x] Fontes: catálogo com licença/evidência, download com hash fixado, pastas
  opcionais, leitura limitada de TXT/DOCX/PDF/HTML/MD, recusas explicadas.
- [x] Triagem: DSL lógica limitada sem eval/exec, proveniência literal dupla,
  deduplicação e famílias/documentos separados, juiz distinto e estimado.
- [x] Orquestração: prova selada antes da geração, eventos/heartbeat, retomada
  por fingerprint, limites 200/30/30, diagnóstico, piloto10/longa, bloqueios claros.
- [x] Treino: parâmetros/versões/revisão fixos, checkpoint completo e retomada,
  prazo de salvamento com margem; teste CUDA não substituído por simulação.
- [x] Avaliação/painel: prova fechada, critérios prévios, pares brutos com fonte,
  critérios separados e falhas críticas, status sem sinal, rede somente loopback.
- [x] Verificação: testes de erros solicitados, preparação modelo/fontes reais,
  navegador e captura, relatório e PR rascunho. Sem GPU paga nesta rodada.

Foco de revisão: licenças desconhecidas; interrupção antes de persistir;
mudança de corpus na retomada; falsa aprovação por referência válida;
conclusão sem treinamento real. Esses casos devem ter testes próprios.

Implementado e validado ate o bloqueio por corpus; treino e retomada CUDA continuam nao exercitados. Nao ha adaptador real. A revisao independente encontrou cinco problemas, corrigidos com regressoes.
