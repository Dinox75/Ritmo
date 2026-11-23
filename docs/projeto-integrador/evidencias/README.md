# Índice e plano de evidências

Somente evidências sintéticas sanitizadas podem ser versionadas aqui. Fotos de pessoas, identificação acadêmica completa, manual/ementas integrais, assinaturas e comprovantes ficam fora do Git, em pasta pessoal autorizada. Não gerar imagens simulando execução ou presença.

| Registro | Data / etapa | Situação e relação |
| --- | --- | --- |
| R1 - Diagnóstico/planejamento | 2026-11-23 | Git/PR conferidos; baseline real e matriz versionados. Captura técnica do estado vazio no roteiro, sem pessoa. Fotografia real do estudante trabalhando: pendente |
| R2 - Implementação/verificação | 2026-11-23 | Regressões, migração, auditoria e revisão independente; saída da suíte e captura técnica do log. Fotografia real da atividade: pendente |
| R3 - Demonstração final | rodada técnica 2026-11-23 | Roteiro automatizado com dados sintéticos, capturas de sessão/material e recuperação. Demonstração humana/apresentação e terceira fotografia: pendentes |

O manual, p. 2 e p. 5-6, exige no mínimo três fotos. Estas capturas **não as substituem** sem aceite explícito do orientador. Quando as fotos reais forem obtidas, registrar data, descrição, etapa e consentimento; incluir no relatório privado, não no repositório público.

## Registros técnicos

- `baseline-tests.txt` e `baseline-ui.json`: execução nova da base `da0c7d1`, anterior às alterações (24,481s; 16 testes).
- `tests-final.txt`, `ui-final.json`, `npm-audit.json`: evidências finais da continuação, após correções.
- `demo.json`: tarefas automatizadas, commit e hash do Worker, com métricas humanas explicitamente nulas.
- Capturas `.qa/pi-demo/*.png` e saída completa intermediária `.qa/` permanecem como artefatos locais/CI; cópias selecionadas no diretório pessoal de evidências, sem upload de fotos/identificação.
- Relatório PDF parcial sanitizado é gerado fora do versionamento público; caminho/hash constam no registro local de geração.

Evidências históricas desktop: [PR #11](https://github.com/Dinox75/Ritmo/pull/11) e [relatório](../../qa/pr11-webview-dist-followup.md). Histórico web: [PR #13](https://github.com/Dinox75/Ritmo/pull/13) e [QA 19/11](../../web/qa.md). Nenhum desses aprova código novo por herança.
