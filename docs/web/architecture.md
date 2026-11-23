# Ritmo web — piloto privado

Arquitetura inicial: 2026-11-19; revisão da continuação local do PI: 2026-11-23. Base inicial: main `7815c54`. Decisões técnicas do implementador dentro do pedido original; não implicam aprovação da logo #4 nem da distribuição Windows. Mudanças do PI nesta branch não foram implantadas no Site.

## Arquitetura escolhida antes da implementação

Sites conectado oferece Worker Cloudflare, autenticação gerenciada ChatGPT, D1 e R2. Escolha: Worker ES module independente em `webapp/`, JavaScript, interface HTML sem framework baseada nos fluxos e estilo do desktop. Backend novo, sem importar o servidor desktop, sensores, runtime CUDA ou credencial efêmera. Build empacotado com esbuild; migrações D1 versionadas via Drizzle. Os dois produtos permanecem no mesmo repositório, em diretórios distintos.

Alternativas: expor o servidor Python desktop viola isolamento; Vercel exige provisionar autenticação, banco e arquivos externos adicionais; Sites já integra os três recursos. Não ativar planos pagos nem inferência remota. O cadastro permanece restrito ao proprietário; acesso inicial é pela mesma conta ChatGPT. Expansão a convidados exige política explícita da plataforma, nunca cadastro ilimitado.

## Dados e autorização

Identidade vem exclusivamente do dispatch Sites: `oai-authenticated-user-id` e email. Não há endpoint de login próprio nem senha padrão. Todo acesso ao banco ou R2 usa o ID estável como proprietário, inclusive downloads, notas e referências. Nenhum header fornecido pelo navegador substitui a autorização da plataforma. Localhost de QA injeta identidades sintéticas somente em um adaptador separado, não empacotado.

D1 guarda matérias/metas, sessões/eventos, metadados/texto extraído e notas. R2 privado guarda originais com chaves internas. Sem dados do desktop, seeds ou credenciais no deploy. Respostas privadas são no-store; sem service worker ou promessa offline. CSP, nosniff, política de referência, CSRF por Origin exata + header próprio em mutações; autenticação/cookies HTTPS pertencem ao Sites. Upload e ações têm cotas persistidas por conta.

Decisão de implementação do piloto: registros de cada conta são um snapshot JSON com versão em uma linha D1; recibos idempotentes e cotas usam tabelas separadas. Texto extraído e originais são objetos R2 imutáveis. CAS por conta serializa atualizações e garante snapshot de backup. Limites reduzidos: 500 notas/sessões e 1,5 milhão de caracteres por snapshot. Evita adaptar inadvertidamente o banco pessoal desktop para múltiplas contas; para escala maior será necessário normalizar o domínio e paginar consultas.

## Sessões, concorrência e rede

Relógio servidor, estado e eventos persistidos; somente uma sessão aberta por proprietário. A regra é verificada no domínio sobre o snapshot e protegida pela atualização condicional da versão da conta (CAS); **não há índice parcial SQL de sessão única no web**. Cada ação carrega ID idempotente e versão esperada. Atualização condicional, recibo e, na continuação do PI, evento de auditoria ocorrem num batch D1 atômico. Conflito retorna 409 e exige recarregar o estado confirmado, sem sobrescrever outra aba. Foco continua enquanto desconectado, até pausa/conclusão confirmada; fechar aba não gera evento. UI mostra tempo estimado desde a última confirmação e mantém a indicação de rede. Rascunhos de notas são locais por conta e explicitamente não sincronizados, com aviso antes de sair; o status salvo só aparece após confirmação. A continuação local mantém o mesmo pedido pendente diante de 503/429 para reenvio exato, sem chamar resultado incerto de falha definitiva.

## Arquivos, limites e recuperação

Piloto: 2 MiB por original, 100 páginas PDF, 120 mil caracteres extraídos, DOCX com expansão limitada a 8 MiB e 512 entradas, XML sem DTD/entidades, nomes seguros e sem HTML confiável. Processamento limitado dentro do isolate Worker, sem subprocesso/comando/rede externa; rejeitar formato inválido ou documento sem texto com erro claro. Sem OCR. Quota 20 MiB de originais/conta, 50 materiais, 50 matérias, **500 notas e 500 sessões**, conforme `LIMITS` do domínio. Extratores PDF/DOCX têm avaliação própria de dependências; custo CPU de documentos complexos pode impedir importação no plano gratuito e precisa ser medido no deploy.

## Continuação do Projeto Integrador (local, sem deploy)

A migração 0001 acrescenta `audit_events`, sem reescrever migrações anteriores. Sucesso do CAS e inserção efetiva do recibo condicionam a auditoria e seu expurgo: batch com UPDATE de zero linhas não é tratado como sucesso. A consulta tem escopo da própria conta, cursor estável por instante/ID, padrão 20/máximo 50. Retém até 200 registros e filtra 30 dias; limpeza física ocorre em novas gravações, sem cron prometido. Exportação registra preparação completa, na versão do snapshot serializado, não recebimento do download. Auditoria não integra backup de estudos nem é transplantada entre contas no restore.

Falha de auditoria aborta a mutação. Se a resposta do commit se perder, o recibo permite recuperar o estado; chaves R2 já referenciadas são preservadas. Se nem a consulta do recibo for possível, o resultado é desconhecido: retorna 503 e preserva os objetos para reconciliação posterior. Pode sobrar objeto órfão, preferível a apagar um original possivelmente confirmado. Não há log inviolável, forense completo ou promessa de registrar no próprio banco sua indisponibilidade. [Detalhes e contrato](../projeto-integrador/endpoints.md).

Backup explícito JSON versionado inclui registros e originais com hashes. Exportação usa uma leitura transacional e arquivos imutáveis. Restauração validada, em conta vazia, IDs novos e vínculos remapeados; arquivos são gravados antes de batch SQL e compensados em falha. Sessão aberta é restaurada pausada, sem contar tempo entre exportação e importação. Não é backup automático nem sincronização desktop. Testar restore em armazenamento isolado; não substituir dados existentes.

## Interface e IA

Navegação Início, Estudar, Materiais, Notas, Evolução e Configurações. Material e notas têm prioridade no celular; controles com alvos de toque e foco visível, temas claro/escuro. Som sintetizado opcional iniciado por gesto; para em pausa/conclusão. Nenhuma permissão de câmera/microfone/notificação. Tutor generativo explicitamente indisponível; nenhum envio para modelo/API/PC. Aula booleana não é requisito do fluxo principal e só deve ser exposta se portada e testada, sem simular IA.

## Entrega e verificação

Testes unitários/domínio, integração D1/R2 reais via Miniflare, duas identidades, IDs diretos, concorrência/repetição, uploads hostis, backup/restore separado. UI em 390/768/1366/1920, ambos temas, teclado, offline/recuperação, erros JS. Separar evidências locais de URL publicada. Validar login real, sessão, redeploy e persistência na URL; se autenticação do proprietário exigir interação, não contornar ou substituir por bypass com identidade fictícia. Fonte em branch/PR, deploy reproduzível e rollback por versão sem desfazer migrações aplicadas.

## Custos e limites conhecidos

Referências oficiais consultadas em 2026-11-19: [Workers](https://developers.cloudflare.com/workers/platform/limits/) Free 100 mil requests/dia, 10ms CPU, 128MiB; [D1](https://developers.cloudflare.com/d1/platform/pricing/) 5 milhões linhas lidas/dia, 100 mil escritas/dia e 5GB; [R2](https://developers.cloudflare.com/r2/pricing/) franquia Standard 10GB-mês, 1 milhão operações A e 10 milhões B/mês. São limites públicos Cloudflare, **não promessa de franquia contratual do Sites**. A ferramenta Sites provisiona os bindings sem compra explícita; disponibilidade, retenção, suspensão e quotas do workspace precisam ser descritas conforme retornos verificáveis, sem inventar SLA. O app impõe cotas menores. Sem cobrança habilitada por esta tarefa.
