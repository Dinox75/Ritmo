# Requisitos e critérios de aceitação

Escopo mínimo sem IA/câmera. Critérios escritos antes de declarar resultados; não equivalem a certificação de norma. Vínculo com conteúdo programático: a confirmar pelas ementas. Manual do PI sustenta o processo/documentação, não cada requisito técnico.

| ID | Requisito / origem | Critério observável |
| --- | --- | --- |
| RF01 | Matéria e meta (herdado) | Criar/editar nome válido e minutos inteiros 0–10080; servidor recusa valores inválidos |
| RF02 | Sessão íntegra (herdado) | Iniciar → pausar → retomar → concluir; uma aberta por conta por domínio+CAS; concluída não aceita alteração |
| RF03 | Tempo (herdado) | Eventos do servidor em ms; foco/pausa separados; desconexão mantém estado até transição confirmada; datas exibidas no fuso do dispositivo |
| RF04 | TXT e nota (herdado) | Importar TXT UTF-8 sintético, buscar palavra, selecionar trecho e salvar/reabrir nota; âncora validada no servidor |
| RF05 | Recuperação (herdado) | Exportar, validar hashes, restaurar em instância/conta vazia com IDs remapeados; intervalo entre export/restore não entra no tempo |
| Q01 | Feedback (novo) | Upload recusado não permanece “enviando”; backup recebido usa status de sucesso; 503/429 mantém pedido sem confirmação para repetir com mesma chave |
| Q02 | Rascunho e conflito (herdado/validado) | Nova digitação não é apagada por confirmação tardia; outra aba recebe conflito sem sobrescrita; rascunho local identificado |
| Q03 | Acessibilidade/responsivo (validação) | Fluxo por controles rotulados, foco alcançável e visível; 390/768/1366/1920, claro/escuro, sem overflow horizontal e sem erros JS observados |
| API01 | Validação estrutural (novo) | JSON null/array/string não é objeto de operação: responder 400, sem alteração |
| AUD01 | Trilha mínima (novo) | ID servidor, instante servidor, owner, ação, resultado, recurso técnico, correlação e versão; sem corpo dos estudos/credenciais/email |
| AUD02 | Consistência (novo) | Estado, recibo e evento atômicos; conflito ou replay não cria evento; falha de auditoria não confirma mutação |
| AUD03 | Consulta e retenção (novo) | Só owner autenticado, 20 por padrão/50 máximo, cursor estável, até 200 registros/30 dias consultáveis; limpeza física em novas gravações |
| SEC01 | Fronteira de identidade (herdado/validado local) | API exige identidade de dispatch; CSRF de origem externa recusado; segunda identidade não acessa IDs/backup/notas da primeira |
| SEC02 | Dados não confiáveis (herdado/validado) | TXT/nota hostil vira texto, não instrução; limites de formato/tamanho/expansão no servidor |
| SEC03 | Falha pós-commit (novo) | Perda de resposta não remove original referenciado; resultado desconhecido preserva R2 e retorna erro sem stack/segredo; replay não duplica negócio |
| DOC01 | Honestidade da evidência (novo) | Baseline, resultado histórico, teste novo e pendência separados; sem participantes/fotos/benefícios inventados |

Prevenção/organização da qualidade: requisitos, escopo, critérios, matriz, revisão independente e plano. Verificações do produto: inspeção de código, regressões, suíte, UI, migração e ensaio de recuperação. Avaliação humana de usabilidade é atividade distinta e ainda pendente.
