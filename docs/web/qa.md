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

Projeto Sites provisionado: `appgprj_6aff1175288c81919986e66898d292b6`, acesso customizado **somente proprietário**, sem grupos/convidados. URL esperada não equivale a publicação: `https://ritmo-estudos.dinox-xv.chatgpt.site`. Estado e versão publicada serão registrados aqui após retorno terminal da ferramenta.

O host de automação do navegador/computador desta sessão retornou indisponível (`native pipe` não encontrado e `browser access host unavailable`). Não se usará um token de serviço como identidade de estudante ou se forjará login para declarar teste remoto aprovado. Login real, ciclo de sessão, importação sob quota CPU e persistência entre redeploy devem ser marcados separadamente conforme evidência real.

DIST-01 e históricos Windows preservados. Logo #4 e Android não incorporados. Sem GPU, treino, instalação pessoal, domínio ou plano pago.
