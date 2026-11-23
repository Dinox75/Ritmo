# Plano priorizado e desenho da evolução

Base da continuação: `da0c7d1`, PR #13 aberta. Implementação local, sem deploy, merge, release ou mudança de dependências/runtime do aplicativo. O pedido autoriza avançar nas melhorias essenciais após diagnóstico/matriz; decisões abaixo são do implementador, não escolhas supostamente aprovadas pelo orientador.

## Essencial

1. Registrar linha de base, divergências e fontes acadêmicas disponíveis; preservar os 16 testes existentes e a história das PRs.
2. Reproduzir API-01/UI-01 com testes novos, observar falha e corrigir validação/feedback, sem redesenho.
3. AUD-01: migração nova para `audit_events` com ID servidor, instante servidor, owner interno, ação, resultado, recurso técnico, correlação e versão. Mutação de estado, recibo e evento no **mesmo batch D1**. Replay não insere evento. Falha de auditoria reverte a mutação; não afirmar sucesso. Não registrar conteúdo, email, cookies, tokens ou headers completos.
4. Restauração audita a operação local, não importa logs de outra conta. Exportação audita preparação concluída, não download/recebimento. Se registro da preparação falhar, responder erro e não entregar backup como confirmado. Falhas sem banco não são prometidas dentro do próprio banco.
5. Retenção: no máximo 200 eventos recentes por conta, até 30 dias na consulta; limpeza física durante novas gravações bem-sucedidas, sem promessa de cron. Log não é imutável/inviolável nem auditoria forense completa. GET `/api/audit` exige identidade do dispatch, página padrão 20/máximo 50 com cursor; sem escolha de proprietário pelo cliente. Interface somente lista própria em Configurações, sem administração.
6. Testar migração sobre cópia sintética anterior; concorrência/replay/rollback; isolamento, cursor/retenção, exclusão e recuperação; reexecutar suíte e UI. Documentar endpoints e comportamento de falhas.
7. Preparar protocolo humano e demonstração técnica; não preencher tempos/opiniões de participantes com automação. Escrever relatório parcial sanitizado e gerar PDF revisado quando houver resultados suficientes. Abrir nova PR em rascunho contra a branch da #13, deixando dependência explícita.

## Recomendado e futuro

Recomendado: observação prática do estudante com o protocolo, login remoto legítimo quando possível e aceite do orientador. Futuro: normalização/paginação do snapshot se escala real exigir, coleta operacional de órfãos R2, Android, sincronização e inferência. Nenhum desses amplia o escopo desta rodada.

## Alternativas consideradas

Somente console.log perde consistência com commit e pode vazar conteúdo; colocar trilha dentro do snapshot amplia todo fetch/backup e dificulta retenção/consulta. Escolha: tabela própria pequena no mesmo D1 e batch existente, mantendo o restante do domínio. Não trocar framework/banco. Não criar painel administrativo nem registrar falhas de autenticação com identidade não confiável.

## Sequência de verificação

- [x] Baseline: 16 testes e UI, antes de editar código.
- [x] Testes RED para defeitos reproduzidos.
- [x] Correções pequenas e GREEN.
- [x] Auditoria: testes RED, migração nova e implementação transacional.
- [x] Suíte, migração anterior→nova, falhas induzidas, UI e revisão independente.
- [x] Documentos técnicos, relatório parcial/PDF conferido; prontidão para abrir PR em rascunho.
- [ ] Ementas, decisão do orientador, avaliação humana, fotos e validação remota legítima (pendências externas; não bloqueiam esta entrega local).

Revisão especial: erro após commit não pode apagar original R2 já confirmado; concorrência não pode gerar evento órfão; auditoria não deve ter campos de conteúdo; expiração de acesso simulada não prova cookies Sites; fotos/capturas e opinião de usuário não podem ser inventadas.
