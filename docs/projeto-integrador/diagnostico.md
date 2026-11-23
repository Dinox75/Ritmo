# Diagnóstico e linha de base

Inspeção em 2026-11-23, antes de modificar código. Nenhum AGENTS.md encontrado na árvore versionada ou nos ancestrais verificados. Lidos README, SECURITY, arquitetura desktop/web, QA web, README web, rotas, domínio, store, backup, documentos, UI, testes, migrações e workflow web. Referências técnicas: [desktop](../arquitetura.md), [web](../web/architecture.md), [QA histórico](../web/qa.md).

## Estados conferidos

| Item | Valor observado | Classificação |
| --- | --- | --- |
| main remoto | `7815c545e798b3447bb554928038bec0f4a726ff` | Inspeção Git/GitHub nesta rodada |
| PR #13 | aberta, rascunho; head `da0c7d1894b24dda982d23e86aeea8b7bacff694` | Integração GitHub nesta rodada |
| Checkout original | limpo, `feat/ritmo-study-sources`, `f0b7f18` | Inspeção; preservado |
| WebPilot | limpo, `feat/ritmo-web-pilot`, `da0c7d1` | Inspeção; preservado |
| Continuação | branch/worktree separados a partir do HEAD da PR #13 | Nova organização; sem merge |
| 179 testes desktop/PR #11 | registro histórico, versão e detalhes no relatório original | Histórico; não aprovação desta rodada |
| 16 testes web/19-11 | relatório da PR #13 e CI anterior | Histórico; não aprovação de mudanças novas |

## Reutilização, sem recriação

O desktop usa Python/API loopback, SQLite/FTS5 e janela nativa; continua preservado. O web é Worker JavaScript independente, com autenticação do dispatch Sites, D1 e R2 privado. Uma linha `accounts` contém snapshot JSON e versão por conta; `requests` contém recibos de idempotência e `rates` as cotas. Atualização condicional (CAS) e recibo estão no mesmo batch transacional D1. Não há índice parcial SQL de sessão única: a regra do domínio procura sessão aberta no snapshot e o CAS evita duas escritas concorrentes. Repetição exata consulta recibo; mesma chave com outro corpo falha.

Sessões, notas, âncoras, backup com hashes, restauração em conta vazia, remapeamento de IDs e exclusão do intervalo exportação/restore já existiam. Não contabilizar essas implementações como criação deste PI. Textos extraídos/originais imutáveis ficam em R2; metadados/estado no D1. A primeira evolução deve manter este desenho, não normalizar o banco por motivo meramente acadêmico.

## Problemas constatados por inspeção

| ID | Constatação na base | Decisão |
| --- | --- | --- |
| DOC-01 | arquitetura web diz índice parcial inexistente | Corrigir descrição para domínio + CAS; preservar mecanismo |
| DOC-02 | mesma arquitetura lista 1000 notas/2000 sessões e também 500; código aplica 500/500 | Unificar em 500/500 sem aumentar cotas |
| AUD-01 | eventos de sessão não têm ID/correlação de auditoria; recibos não têm instante/ação/recurso; não há trilha para importação, exclusão ou restore | Acrescentar trilha mínima transacional, com retenção e consulta limitada própria |
| SEC-DOC | SECURITY descreve apenas autenticação loopback, embora README agora tenha web | Explicitar duas fronteiras; não reutilizar credencial desktop |
| UI-01 | erros de upload podem deixar texto “Enviando e extraindo” visível; status de backup bem-sucedido usa estilo de erro | Reproduzir antes de corrigir; alteração pontual de feedback, sem redesenho |
| API-01 | JSON `null` chega ao acesso de `payload.request_id`, podendo virar 503 genérico em vez de validação 400 | Reproduzir em integração, depois validar estrutura |

## Executado na linha de base desta rodada

`npm ci`, build do Worker, suíte web e QA de UI em Windows/Node 24.22.3/Edge/Miniflare: **16/16, zero skips, 24,481s** antes das mudanças. UI: fluxo sintético e 390/768/1366/1920 em ambos os temas, zero erros JS registrados. [Saída da suíte](evidencias/baseline-tests.txt), [resultado UI](evidencias/baseline-ui.json). A autenticação desta UI é simulada exclusivamente no loopback de teste, não no site.

## Pendências e limites preservados

Login remoto autenticado, uso em outro dispositivo e persistência após republicação não estão aprovados. Republicar não está autorizado nesta etapa. PDF complexo pode esgotar o isolate; R2 pode reter órfãos em crash entre escrita e CAS; backup por conta não é recuperação administrativa de todo o provedor. Sem IA generativa web, sincronização desktop/web ou evidência de aprendizagem. DIST-01 é achado de redistribuição Windows, não inventário de DLLs do Worker. O tema ainda depende do orientador.

## Fontes acadêmicas

O estudante indicou Downloads. Foi localizado e lido integralmente `manual-projeto-integrador.pdf`, FASUL, 2026, 7 páginas; [mapeamento por página](rastreabilidade.md#associação-documental-verificada). Ementas das três disciplinas não foram identificadas por nomes relacionados; nenhuma busca em documentos de empresa foi realizada. Não inferir conteúdo curricular a partir de código.
