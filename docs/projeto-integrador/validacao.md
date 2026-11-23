# Validação e limitações

## Classificação das evidências

**Inspeção desta rodada:** Git/PRs, arquitetura, limites, falta de auditoria, fronteira dispatch e documentação. **Execução desta rodada:** baseline, regressões, migração e ensaios abaixo. **Histórico:** 179 testes desktop da PR #11 e 16 web do relatório de 19/11/2026. **Pendência:** currículo detalhado, orientador, avaliação humana, fotos e ambiente remoto autenticado. Não somar históricos à contagem desta execução.

## Ambiente e comandos

Windows, Node 24.22.3 portátil oficial já existente, Edge headless em perfil descartável, Miniflare 4.20260730.0/workerd, D1/R2 locais isolados. Sem materiais pessoais. Instalação de ferramentas PDF em venv externo, sem dependências novas no aplicativo. A primeira tentativa pip falhou por certificado; repetição usou truststore do sistema, sem desativar TLS.

```powershell
# webapp; Node 24 no PATH apenas do processo
npm ci
node scripts/build.mjs
node --test --test-concurrency=1 tests/*.test.mjs
node scripts/qa-ui.mjs
node scripts/pi-demo.mjs
npm audit --json
git diff --check
```

Migração gerada com `node node_modules/drizzle-kit/bin.cjs generate`. A 0000 e seu snapshot não foram modificados. Nova 0001 cria auditoria e índice de consulta por owner/instante/ID. O ensaio preserva snapshot, versão, recibo antigo, original R2 e nota ancorada, aplica a migração nova e só então registra operações novas; não inventa auditoria retroativa.

## Verificações novas, por risco

| Risco / critério | Evidência implementada |
| --- | --- |
| API01 | null, array e string JSON retornam 400 sem mutação; antes null retornou 503 |
| Q01/Q03 | rejeição de upload encerra feedback; backup confirmado é status; carregamento de material indica espera e só libera busca após texto; regressões reproduzidas antes da correção |
| AUD01/AUD02 | ações com correlação/versão, replay simultâneo sem evento extra, corrida distinta com 200/409, sessão concluída protegida |
| AUD02/SEC03 | trigger sintético aborta INSERT de log: rollback de estado/recibo, resposta 503 sanitizada e compensação de provisórios |
| SEC03 | wrapper executa batch D1 **real**, depois perde resposta; importação e restauração, com recibo legível/indisponível; original preservado e replay cria um só evento |
| Q01/SEC03 | UI recebe 503 depois de nota já salva: conserva chave e reenvia sem duplicar nota |
| SEC01 | IDs de notas/arquivos e backup não cruzam owner; endpoint de auditoria rejeita seleção de owner |
| AUD03 | cursor sem repetição com mesmo milissegundo, padrão/limite, 30 dias filtrados e expurgo até 200 em nova gravação |
| RF05 | migração de base anterior e ensaio de recuperação em destino separado; totais/restauração herdados reexecutados |

Revisão independente detectou P1 de compensação após resposta perdida: versão 2 e documento confirmado podiam coexistir com R2 vazio. A regressão reproduziu o defeito com banco real local. Correção preserva objetos referenciados e não tenta compensar quando o resultado do commit é desconhecido. Log de segurança não contém texto, nomes de arquivos, email, tokens ou cabeçalhos completos, verificado com canários sintéticos. A cobertura não prova ausência de vulnerabilidades.

## Resultado final e procedência

A contagem/duração final e o commit do código estão no registro de execução abaixo e nos arquivos de evidência. As 16 verificações herdadas permanecem na suíte; os testes novos foram acrescentados por riscos/defeitos e auditoria, não por meta de contagem. Há regressões isoladas e cenários múltiplos dentro de um teste; quantidade de testes não equivale a quantidade de requisitos aprovados.

Código funcional: `79aa55cf85347b8a634df5c7f931594e5c5662dd`. Suíte final: **31/31, zero skips, 35,767s** em 23/11/2026 ([saída](evidencias/tests-final.txt)). Roteiro técnico reexecutado após o commit: quatro tarefas concluídas, zero erros JS ([JSON](evidencias/demo.json)); hash do Worker local **`a91e7f0cbe310aaecb308755db99e5a25c7827a1b52caa7cf6acde25520a1524`**. Os tempos 161/612/581/833 ms são durações da automação nesta rodada, não tempos de usuário. [UI final](evidencias/ui-final.json), [npm audit sem achados conhecidos](evidencias/npm-audit.json). Nenhum binário Windows foi gerado.

PDF parcial sanitizado: gerado com `scripts/pi_report.py`, ReportLab e renderizado com PDFium (Poppler indisponível neste ambiente); 5 páginas com texto extraível e páginas renderizadas examinadas. Fonte: `relatorio.md`. Hash **`8aa6937d2dd0357a6de4071dd56932d54ba6b9941226b5e44b7410ecf77236fd`**; [metadados sanitizados](evidencias/pdf.json). PDF e imagens ficam fora do Git, em `Laboratorio/PI-Evidencias/` na organização local do projeto. Não há fotografias de pessoas anexadas nem versão final pronta para submissão.

```powershell
# Ferramenta documental, não dependência do aplicativo:
python scripts/pi_report.py --output <pasta-privada>/relatorio-parcial-ritmo.pdf --render-dir <pasta-privada>/pdf-render
```

UI técnica: seis telas × quatro larguras (390/768/1366/1920) × dois temas. Verifica ausência de overflow, erros JS, foco alcançável, controles e fluxo; não é auditoria completa de acessibilidade nem teste em celular físico. Áudio foi verificado por estado/sinal interno, sem escuta física nesta rodada.

## O que não foi aprovado

Nenhuma mudança publicada no Site, main ou instalação Windows. Não houve teste remoto autenticado novo, republicação, segundo dispositivo físico, avaliação humana, fotos reais, validação de aprendizagem ou aprovação do orientador. O host de acesso do navegador retornou indisponível. Persistência local após reinício e restore separados **não** provam persistência remota após redeploy. Sem suíte desktop nova, pacote Windows novo ou fechamento DIST-01.

Retenção da auditoria não apaga fisicamente linhas antigas sem nova gravação; não há cron. Falhas de autenticação/CSRF e indisponibilidade total do D1 não são prometidas no log do próprio D1. Admin do banco pode alterar o log. R2 pode manter provisórios órfãos quando a confirmação é desconhecida; nenhuma limpeza destrutiva é feita nessa incerteza. Estes limites precisam ser explicados na demonstração.
