# Endpoints da demonstração web

Contrato da continuação local do PI, não do Site publicado antigo. Todos os `/api/*` exigem owner **e email de autenticação injetados pelo dispatch Sites**. O email não entra na auditoria. Exemplos de JSON são sintéticos; **não** enviar headers de identidade manualmente como login remoto. O adaptador loopback usa identidades sintéticas apenas em testes.

POST exige Origin idêntica à URL do serviço e `X-Ritmo-Request: 1`; cookies pertencem ao Sites. Todas as respostas de dados são private/no-store; não há CORS amplo. Datas/instantes JSON são ms Unix UTC de servidor; UI formata no fuso do dispositivo. Código do tutor não é necessário.

| Método e rota | Entrada | Resposta de sucesso | Versão / idempotência |
| --- | --- | --- | --- |
| GET `/api/state` | sem selector de conta | `{version,state,now,user:{email},limits,tutor}` | Retrata snapshot confirmado; leitura pode inicializar conta vazia |
| POST `/api/action` | objeto com `version`, `request_id`, `action` e campos abaixo | `{version,state,now}` e `replayed:true` quando recuperado/repetido | Inteiro esperado da conta, chave 1–80 caracteres `[A-Za-z0-9_-]`; mesmo corpo com mesma chave, sem novo negócio/auditoria |
| POST `/api/upload` | multipart: `version`, `request_id`, `subject`, `file` | novo documento no snapshot, ID opaco | Fingerprint inclui versão, nome e SHA-256 do original; confirmação por CAS/recibo/auditoria |
| GET `/api/documents/{id}` | ID da própria conta | `{id,name,format,blocks,pages}` | Não recebe caminho ou chave R2 do cliente |
| GET `/api/download/{id}` | ID da própria conta | anexo original `application/octet-stream` | Acesso privado; nomes internos não são selectors públicos |
| GET `/api/backup` | sem selector de proprietário | JSON `ritmo-web`, versão 1, snapshot/instante/originais base64 e hashes | Não incrementa versão da conta; audita `backup.prepared` depois da serialização; não comprova recebimento |
| POST `/api/restore` | `{version,request_id,backup}` | estado restaurado com IDs novos, sessão aberta pausada | Só conta vazia no commit; logs antigos não são importados; novo `backup.restore` idempotente |
| GET `/api/audit?limit=20&before=...` | limit 1–50; cursor opaco recebido em `next` | `{events,next,retention}` | Consulta própria; sem `owner` escolhido pelo cliente; rejeita parâmetros desconhecidos/duplicados |

`state.documents` omite `key`/`textKey`; notas vêm somente no snapshot da conta. Não existe endpoint de consulta de nota/backup de outra conta por owner. No backup, parâmetros como owner não mudam o escopo autenticado (não são selector suportado); IDs estrangeiros de arquivo e nota retornam 404.

## Ações e exemplo sintético

- `subject.save`: `id`, `name` 1–100, `goal` inteiro 0–10080.
- `session.start`: `id`, `subject`; sem outra sessão aberta. `session.pause`, `session.resume`, `session.finish`: `id`; transição válida. Até 1000 eventos de alternância; concluir continua permitido no limite.
- `note.save`: `id`, `subject`, `body` 1–10000; livres usam `document:null,block:null,quote:''`; vinculadas exigem material da matéria, bloco inteiro existente e quote até 2000 contida no original. `note.delete`: `id` próprio.
- `theme`: `theme` dark/light.

```json
{"version":3,"request_id":"synthetic-request-4","action":"session.pause","id":"synthetic-session"}
```

Receber 200 confirma o estado e uma nova versão; repetir exatamente esse objeto retorna estado confirmado com `replayed:true`. Reutilizar a chave com corpo diferente gera 409. Versão antiga ou corrida entre abas também gera 409: reler, revisar e só então iniciar outra ação. Não incrementar versão no navegador antecipadamente. Resposta 503/perda de rede pode ocultar commit já concluído: preservar chave/pedido e recuperar, sem remover originais possivelmente referenciados.

## Erros e limites

400 entrada/JSON/cursor inválido; 401 falta identidade; 403 origem/CSRF; 404 recurso não encontrado no owner; 405 método não aceito; 409 versão, transição ou chave conflitante; 413 quota/expansão/estado; 429 taxa; 503 falha de infraestrutura ou resultado não confirmado. Erros são JSON `{error}` sem stack trace, token ou caminho privado. Não há registro no banco garantido quando ele está indisponível.

50 matérias e materiais; 500 notas e sessões; snapshot menor que 1,5 milhão de caracteres. Original até 2 MiB, total 20 MiB; PDF 100 páginas, texto 120 mil caracteres; DOCX 512 entradas/8 MiB efetivamente expandidos. Taxas por minuto/conta: 240 requests, 60 mutações, 6 uploads, 3 preparações de backup, 2 restaurações. Parser PDF/isolate e upload interrompido ainda têm os limites descritos no README web.

## Auditoria, falhas e retenção

Campos: id, owner interno, at, action, result (`committed`/`prepared`), resource, correlation, version. Actions: subject.save, session.start/pause/resume/finish, material.import, note.save/delete, theme, backup.restore/prepared. Mutação gera um evento no mesmo batch do CAS e recibo, condicionado à inserção real; UPDATE de zero linhas não basta. Exportação GET prepara uma cópia a cada invocação e registra essa preparação com correlação servidor nova, não um evento de mudança do estudo nem uma alegação de download. Reenvio idempotente de **mutação** não duplica evento.

Falha de INSERT de auditoria aborta o batch e a confirmação; objetos provisórios são compensados quando se sabe que não houve commit. Em recuperação por recibo, só se removem chaves provisórias que não constam no estado confirmado. Se consulta de recuperação falhar, arquivos ficam preservados para reconciliação futura, podendo haver órfãos. Log não é assinado, imutável, inviolável ou trilha de todas as falhas de acesso. Não registra corpos, notas, textos, nomes de arquivo, email ou credenciais. Máximo 200 por conta; consulta filtra 30 dias mesmo sem novas escritas. Expurgo físico acontece em novas gravações bem-sucedidas, não em um cron inexistente.
