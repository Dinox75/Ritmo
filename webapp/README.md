# Ritmo web — piloto privado

Aplicação independente do servidor Windows. Backend Worker ES module, autenticação gerenciada Sites/ChatGPT, D1 para registros e R2 privado para originais e texto extraído. A primeira implantação começa vazia.

## Desenvolvimento (Node 24)

```powershell
cd webapp
npm ci
node scripts/notices.mjs
node scripts/build.mjs
node --test --test-concurrency=1 tests/*.test.mjs
node scripts/qa-ui.mjs
node scripts/dev.mjs
```

`http://127.0.0.1:8787` usa um adaptador de QA com identidades **sintéticas**, nunca incluído no pacote. O acesso local simulado não é evidência de login remoto. Dados locais descartáveis em `.wrangler/`; não copie o banco desktop. Não exponha esse adaptador na rede. Os testes de interface usam Edge instalado e perfis temporários.

Em caminhos Windows com `&`, a resolução de shims `.cmd` pode falhar. O comando de migração usa `node node_modules/drizzle-kit/bin.cjs generate`. Build e testes usam `node` diretamente, sem shims.

## Uso

Criar/editar matéria e meta; iniciar foco; pausar, retomar e concluir; importar TXT UTF-8, DOCX e PDF com texto; pesquisar e destacar ocorrências; selecionar um trecho e salvar anotação vinculada; revisar notas, histórico e evolução. Tema persistido por conta. Chuva sintetizada e ruído marrom são opcionais e começam por gesto. Não há arquivo WAV web nesta etapa nem medição acústica.

O servidor calcula tempo a partir dos eventos; a tela apenas estima desde a última resposta. Fechar a aba ou perder conexão **mantém o foco em andamento** até uma pausa/conclusão confirmada. Duas abas usam uma versão global da conta: conflito retorna 409 e preserva o rascunho, sem sobrescrever a outra aba. Reenvio exato usa a mesma chave; alteração do corpo com chave antiga é recusada. Rascunhos são por conta, neste dispositivo, não sincronizados, e são removidos ao sair.

Requer internet. Sem service worker, cache privado ou promessa offline. Tutor generativo explicitamente indisponível. Nenhum modelo local, API OpenAI ou servidor do PC é exposto; não há cobrança por chamada de IA. Inferência futura exige servidor próprio ou hospedagem de modelo aberto, com RAM/VRAM, custo e isolamento a avaliar. Aula booleana permanece no desktop; não se anuncia porte que não foi testado.

## Limites do piloto

- 50 matérias, 50 materiais, 500 notas, 500 sessões; meta 0–10080 min/semana.
- Original até 2 MiB; total de originais 20 MiB/conta; texto até 120 mil caracteres; PDF até 100 páginas. Sem OCR e sem execução de JavaScript de documentos.
- DOCX até 512 entradas e 8 MiB **efetivamente descompactados**, com leitura em blocos e abort imediato; XML sem DTD/entidades. PDF roda no isolate Worker com eval desabilitado; os limites do isolate não equivalem a uma quota de expansão de todos os streams PDF. Documentos complexos podem falhar e exigem testes adicionais.
- 240 requests/minuto, 60 mutações/minuto, 6 uploads/minuto, 3 exportações/minuto, 2 restaurações/minuto por conta. Contadores atômicos D1.
- Registros da conta até 1,5 milhão de caracteres JSON. A versão global privilegia consistência no piloto e pode gerar conflitos entre alterações independentes.

## Segurança e armazenamento

Sites permite somente o proprietário inicialmente. Login e cookies HTTPS são da plataforma. O Worker exige identidade do dispatch em todas as APIs e filtra por proprietário. Não o hospede diretamente aceitando headers de identidade de clientes: fora do Sites é necessário um proxy de autenticação confiável equivalente. Origin exata e header customizado protegem mutações; sem CORS amplo. Downloads são autorizados por ID e entregues como anexos privados; originais nunca têm URL pública. Sem log de conteúdo ou credenciais no código.

Originais/texto são objetos imutáveis com chave aleatória sob o proprietário. Uma mutação de upload só fica visível após CAS D1: concorrência não permite exceder a quota confirmada. Uploads concorrentes podem ocupar espaço transitório; compensação remove objetos de operações que falham. Falha abrupta do processo entre R2 e D1 pode deixar objeto órfão, exigindo manutenção operacional futura. Não há exclusão automática de materiais nem limpeza destrutiva nesta etapa.

## Backup, restauração e continuidade

Configurações → Baixar backup completo exporta JSON versionado com snapshot dos registros, originais base64 e SHA-256. Guarde em local seguro: não há criptografia adicional desse arquivo. Arquivos imutáveis mantêm o snapshot consistente. Restauração valida formatos, limites, hashes, âncoras e eventos; remapeia IDs e só confirma se a conta continua vazia no commit. Estado aberto volta pausado no instante exportado; o intervalo até restaurar é excluído dos totais. Até 100 restaurações por sessão aberta. Falha remove os novos objetos e não publica dados parciais.

Este é backup **por conta**, testado em instância separada. Não é sincronização desktop ou garantia de recuperação operacional de todo o Sites. Retenção, exportação administrativa D1/R2, inatividade e SLA dependem da plataforma; nenhuma garantia não verificada é prometida. Faça exportações regulares.

## Publicação e reversão

`.openai/hosting.json` fixa o ID opaco e bindings `DB`/`BUCKET`. Migrações Drizzle versionadas em `drizzle/`, sem seeds ou dados pessoais. Gere novas migrações com `npm run db:generate`; não edite migrações já aplicadas. Build cria `dist/server/index.js`; não inclui `.wrangler`, testes, adaptador de login ou runtime Windows. O helper oficial Sites sincroniza uma cópia sanitizada deste diretório no repositório privado do Site e empacota o **mesmo commit** para publicação. Credenciais só em memória/stdin; não são comandos de deploy para copiar com tokens.

Para atualizar: abrir o Site pelo ID, obter credencial via ferramenta Sites, preparar fonte sanitizada correspondente a um commit GitHub, executar os testes/build, sincronizar e salvar/publicar exatamente esse SHA/arquivo. Para reverter código, reimplantar uma versão salva conhecida; **não reverter migrações aplicadas** nem dados. Restauração de conta vazia é procedimento separado. Veja o relatório de QA em `../docs/web/qa.md` e arquitetura em `../docs/web/architecture.md`.

Nenhum plano pago, domínio ou GPU foi contratado. Franquias Cloudflare consultadas não são SLA ou promessa de limites do produto Sites. Exaustão de quota pode indisponibilizar o piloto; o app mostra erro e não confirma salvamento. Licenças do JavaScript distribuído em `/third-party.txt`; DIST-01 Windows permanece separado e aberto.
