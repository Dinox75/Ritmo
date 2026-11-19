# QA do piloto Ritmo web

Data: 2026-11-19. Base `7815c54`, branch `feat/ritmo-web-pilot`, worktree `A:\Projetos & Estudos\Ritmo\WebPilot`. Checkout original preservado em `feat/ritmo-study-sources`/`f0b7f18`; instalação pessoal e dados não utilizados.

## Ambiente e comandos

Windows, Node oficial portátil 24.22.3 (ZIP validado pelo SHASUMS oficial; SHA-256 `e612af99f626ab415ea225af6bce5c971feb448cb5cae250bb1c3fa50c5f7d9f`), Edge headless em perfis temporários, Miniflare 4.20260730.0/workerd com D1/R2 locais reais. Diretórios de QA descartáveis. Nenhum material ou conversa pessoal em fixture ou relatório.

```powershell
# Dentro de webapp, com Node 24 no PATH
npm ci
node node_modules/drizzle-kit/bin.cjs generate
node scripts/notices.mjs
node scripts/build.mjs
node --test --test-concurrency=1 tests/*.test.mjs
node scripts/qa-ui.mjs
npm audit --json
git diff --check
```

O helper oficial Sites `install-dependencies.mjs` também foi utilizado. Após mudar overrides, `npm install --package-lock-only` e reinstalação reproduziram o lock. O shim `.cmd` de Drizzle falhou no caminho com `&`; chamada direta Node resolveu. Não foi alterado PATH global nem instalado runtime no Windows pessoal.

## Evidências locais

- Domínio: relógio/eventos foco e pausa, transições, referências, limites e encerramento no teto de eventos.
- Integração: identidade obrigatória, Origin/header anti-CSRF, ausência de CORS amplo, respostas privadas no-store; isolamento Alice/Bob inclusive IDs diretos; repetição simultânea de mesmo pedido e chave com corpo diferente; duas ações concorrentes com 200/409 e uma única sessão.
- Arquivos: TXT UTF-8, DOCX e PDF sintéticos extraídos pelo parser real; original baixado byte a byte; leitura negada a outra conta; seleção da nota validada no servidor. TXT hostil permanece texto. Tamanhos, bytes inválidos, XML DTD/entidades, DOCX inflado e tamanho ZIP forjado rejeitados.
- Backup: hashes, IDs novos e vínculos remapeados, conta não vazia protegida; D1/R2 persistentes após reiniciar Worker; restauração em **outra instância**. Foco aberto congela na exportação e volta pausado; intervalo backup/restore excluído dos totais.
- UI: login/logout **simulados apenas localmente**, matéria/meta, foco/reload/pausa/retomada/conclusão; TXT, busca, seleção, nota e destaque; falha de rede conserva rascunho e reenvio exato; conflito de segunda aba; backup baixado; logout limpa rascunho. Chuva, ruído marrom, volume e pausa/conclusão de áudio por estado/sinal interno — sem medição acústica.
- Seis telas × 390/768/1366/1920 × claro/escuro: sem overflow horizontal, foco alcançável por teclado, zero erros JS observados. [Resultado estruturado](ui-local.json). Capturas sintéticas mantidas como artefatos de QA; exame visual de 390 escuro e 1920 claro.
- `npm audit` atual: zero avisos conhecidos em produção **e desenvolvimento**. [JSON completo](npm-audit.json). Overrides esbuild 0.28.2, sharp 0.35.5 e undici 8.12.4 corrigem a cadeia de ferramentas; testes repetidos com esses overrides. Isto não prova ausência de vulnerabilidade. Avisos completos dos componentes runtime incluídos em `/third-party.txt`; não são as DLLs do DIST-01.

Rodada final local: **16/16**, zero skips, 42,911s; [saída completa](tests-local.txt). UI final passou os 48 pares tela/largura/tema e os oito grupos de fluxos registrados no JSON. CI independente Windows também passou: [push 44556510383](https://github.com/Dinox75/Ritmo/actions/runs/44556510383) e [PR 44556603519](https://github.com/Dinox75/Ritmo/actions/runs/44556603519). São testes locais no runner, **não** testes do site autenticado. A suíte desktop não foi reexecutada localmente; seus arquivos executáveis não foram modificados.

## Falhas encontradas e corrigidas

1. PDF.js transfere/destaca o buffer de entrada: armazenava original vazio. Agora recebe cópia; teste compara download byte a byte.
2. API de descarte do unpdf é `loadingTask.destroy`, não `pdf.destroy`.
3. FormData nativo Node não era reconhecido pelo fetch interno Miniflare; adaptador serializa o multipart real. Não foi alterada a validação do servidor para acomodar o teste.
4. Revisão independente achou perda de texto digitado após salvar; comparação do rascunho enviado preserva alterações posteriores. Teste falhou antes e passou depois.
5. Navegação indireta podia atribuir rascunho a outra matéria; guarda central aplicada a cards, materiais e notas. Teste falhou antes e passou depois.
6. Limite de 1000 eventos bloqueava conclusão; conclusão continua permitida. Regressão RED→GREEN.
7. Intervalo backup/restore contava como pausa; intervalos excluídos explicitamente, validados ao reimportar. Regressão RED→GREEN.
8. DOCX precisava interromper inflater ao detectar excesso real, inclusive erro capturado pelo fflate; entrada alimentada em 512 bytes e abort após cada bloco. Regressão com cabeçalho de tamanho forjado e entrada insegura posterior confirma prioridade do limite de expansão.

## Avaliação própria de segurança web e limitações

Não há senha padrão, cadastro público, sensor, comando de documento, chamada de IA ou importação automática do desktop. D1 CAS protege todos os registros da conta, inclusive restore vazio verificado no commit; R2 é privado e não recebe nomes externos como chaves. A prova local de isolamento não valida a implementação interna do dispatch Sites, seu ciclo de cookies ou a substituição dos headers forjados na URL final. Essa fronteira exige teste do ambiente publicado.

O parser PDF é limitado por páginas/texto/tamanho e pelo isolate da plataforma; PDF complexo pode esgotar CPU/memória antes da extração. Não há sandbox de processo adicional, OCR ou recuperação administrativa completa testada de um desastre no provedor. Objetos órfãos por crash entre R2 e D1 ainda exigem manutenção futura. O piloto permanece privado.

## Implantação real

Publicado com HTTPS: **https://ritmo-estudos.dinox-xv.chatgpt.site**. Projeto `appgprj_6aff1175288c81919986e66898d292b6`, acesso customizado **somente proprietário**, sem grupos/convidados. Primeiro acesso: abrir a URL e entrar com a mesma conta ChatGPT proprietária deste Site. Não existe senha padrão nem cadastro público. Login explícito: `/signin-with-chatgpt?return_to=%2F`.

- Código GitHub: `c6a5620c5d9815a9b64235392cb46e5e0804e4ff`, [PR #13](https://github.com/Dinox75/Ritmo/pull/13).
- Cópia sanitizada do subdiretório `webapp` no repositório privado Sites: `2f1c7bc771c6c98428732af7ebca3629714c45a6`; `RITMO_SOURCE.json` vincula o commit GitHub. Criada com `git archive HEAD:webapp`, sem histórico/dados/ambientes do desktop, depois `npm ci` e build nesta cópia. Helper oficial Sites recebeu credencial somente por stdin em memória. A PTY do executor falhou com acesso negado; o mesmo helper foi iniciado via Node child_process com pipe de entrada, um caminho não interativo suportado por seu leitor de JSON. Credenciais não foram colocadas em argv, arquivos ou logs de fonte.
- Pacote: `A:\Projetos & Estudos\Ritmo\Laboratorio\ritmo-web-site-v1.tar.gz`, SHA-256 **`f50532796ccf5129667b705970cfa573b23ce4beb0775ee159e31c0fa4316ba1`**. Só Worker, manifesto, build metadata e migrações; sem adaptador `/__qa/login`, dados ou runtime Windows.
- Versão Sites: `appgprj_6aff1175288c81919986e66898d292b6~appgver_de0d532575408191ba6dfafd1fec756c`.
- Publicação `appgdep_6aff17a53fa4819193a8c1a31df98a69`: **succeeded**. Reaplicação da mesma versão `appgdep_6aff181332b081918a805bdbc86b38b7`: **succeeded**. Não houve rebuild ou troca de bytes entre ambas.
- Banco remoto inspecionado pela ferramenta Sites: binding exato `DB`, tabelas `accounts`, `rates`, `requests`; migração aplicada. Manifesto declara R2 privado `BUCKET`. Nenhum seed ou importação de dados pessoais.
- Sondas HTTPS reais `/api/state`: anônimo **401**; headers `oai-authenticated-*` forjados sem login **401**; token de serviço sem identidade **401 JSON**; token de serviço com identidade forjada **401 JSON**. O dispatch remove os headers forjados e o backend exige o estudante. Token de serviço não foi usado como login nem para inserir estudos.
- Logs operacionais dessas sondas: outcome `ok`, 0–1ms CPU; não medem importação ou fluxo autenticado. Logs da plataforma podem conter metadados de rede; **não foram copiados** para o Git.

**Pendências que impedem integração à main nesta rodada:** login interativo remoto, sessão completa na URL, importação TXT/DOCX/PDF sob limites reais da hospedagem, segundo dispositivo, logout/expiração real e persistência de registros sintéticos entre redeploy. A reaplicação da versão foi confirmada, mas não havia registro autenticado sintético para provar persistência. Não se declara esse requisito aprovado. PR permanece em rascunho; nenhum merge.

O host de automação do navegador/computador desta sessão retornou indisponível (`native pipe` não encontrado e `browser access host unavailable`). Não se usará um token de serviço como identidade de estudante ou se forjará login para declarar teste remoto aprovado. Login real, ciclo de sessão, importação sob quota CPU e persistência entre redeploy devem ser marcados separadamente conforme evidência real.

Para completar a validação: disponibilizar o acesso do navegador à automação e entrar na URL com a conta proprietária, sem compartilhar senha/token no chat. Executar com dados sintéticos os mesmos fluxos e publicar novamente a versão salva, comprovando que esses registros permanecem. O site já está publicado; não falta contratar infraestrutura ou configurar chave de IA. A única conta do piloto continua restrita ao proprietário.

Instalação Windows conferida ao fim: SHA-256 `0bbf4346bab2ecd8e1237938c20bedbffc6a122f6b715521f94a43b3e35a926c`, igual ao anterior; checkout original limpo em `f0b7f18`. Banco, modelos, materiais e configuração pessoais não foram abertos ou migrados.

DIST-01 e históricos Windows preservados. Logo #4 e Android não incorporados. Sem GPU, treino, instalação pessoal, domínio ou plano pago.
