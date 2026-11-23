# Roteiro de demonstração

Branch de continuação da PR #13, ambiente local isolado, sem uso da instalação pessoal. Não demonstrar auditoria nova no Site publicado antigo: não houve deploy nesta etapa. O [contrato](endpoints.md) permite explicar cada requisição sem expor credenciais.

## Preparação técnica

No diretório `webapp`, Node 24 e Edge instalado:

```powershell
npm ci
node scripts/build.mjs
node --test --test-concurrency=1 tests/*.test.mjs
node scripts/pi-demo.mjs
```

O roteiro cria D1/R2 e perfil de navegador temporários, usa somente identidades de QA e remove esse ambiente ao terminar. Produz `.qa/pi-demo/` com capturas e JSON de evidência, hash do Worker e commit. Não usar essas identidades ou esse adaptador na internet. O login sintético é exclusivo do loopback e não compõe o Worker distribuído.

Para demonstração interativa local, `node scripts/dev.mjs` em 127.0.0.1:8787 usa `.wrangler/local`, somente dados de ensaio; ao terminar, fechar processo pelo mesmo terminal. Não apontar esse adaptador para bancos ou pastas pessoais. Não abrir porta externa.

## Sequência e explicação

1. Mostrar diagnóstico/base e indicar o que já existia: web separado do desktop, snapshot/CAS, recibos, importação e recuperação. Mostrar ementas como pendentes.
2. Criar matéria/meta. Explicar validação servidor e feedback confirmado. Tentar campo inválido sem “aprovar” a entrada pela interface.
3. Iniciar/pausar/recarregar/retomar/concluir. Mostrar histórico e eventos; fechar a aba não pausa automaticamente. Explicar relógio servidor, estimativa da tela e fuso do dispositivo.
4. Importar TXT sintético, esperar texto, buscar, selecionar e salvar nota. Reabrir a referência. Mostrar que texto com aparência de instrução permanece dado.
5. Em Configurações, consultar atividades próprias. Distinguir ID técnico, ação, resultado, correlação e versão de conteúdo de estudo. Mostrar limite/retenção e esclarecer que o log pode ser alterado por administração do banco.
6. Exportar; destacar `backup.prepared` como preparação, não prova de download. Restaurar em **outra conta/instância sintética vazia**, comparar matéria/nota/histórico e referência. Não restaurar em conta pessoal nem apagar dados para esvaziá-la.
7. Mostrar evidência dos testes: conflito/replay, falha de auditoria abortando commit, resposta perdida depois de commit preservando R2. Explicar por que 503 conserva o pedido para consulta/reenvio exato.
8. Encerrar apresentando limitações e pendências, sem prometer benefício educacional.

## Alternativas e pendências

Se Site/login estiver indisponível, o **web local** demonstra apenas lógica/interface e identidade sintética. O desktop preservado é outra alternativa identificada, com sua própria versão e banco temporário, usando `RITMO_DATA_DIR` apenas conforme documentação desktop; não utilizar a instalação pessoal para produzir os ensaios deste PI. Nenhuma alternativa comprova requisitos remotos do web. Nesta rodada o desktop foi preservado, não revalidado.

Na URL real, futuramente executar login/logout/expiração e fluxo com acesso legítimo. O host de navegador desta sessão retornou indisponível; não se usou token de serviço ou identidade forjada. Persistência após republicação fica **pendente**: requer registros antes/depois e nova autorização de republicar, vedada nesta etapa. Confirmar com o orientador tempo/formato da apresentação e aceite das capturas como fotos.
