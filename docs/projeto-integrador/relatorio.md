# Ritmo - Relatório parcial do Projeto Integrador

Versão técnica sanitizada em elaboração - 23/11/2026. Não é versão final para submissão. Tema e aproveitamento de projeto existente ainda dependem do orientador.

## Identificação

Estudante, matrícula, curso, período, turma e identificação do orientador: preencher na versão privada, fora do Git público. Data da execução técnica registrada: 23/11/2026. Prazo efetivo de entrega e formato da apresentação: pendentes de confirmação no portal e com o orientador. Assinaturas e comprovante de envio: não disponíveis.

Disciplinas informadas pelo estudante: Qualidade e Usabilidade de Software; Desenvolvimento Back-end; Segurança e Auditoria de Sistemas. Ementas oficiais não foram identificadas nos arquivos acadêmicos localizados; as associações curriculares específicas permanecem a confirmar.

## 1. Tema, objetivo e delimitação

Tema provisório: Evolução de uma aplicação de organização de estudos com foco em usabilidade, integridade dos dados e segurança.

O objetivo técnico desta rodada foi produzir uma evolução pequena e demonstrável do Ritmo web privado: manter o fluxo matéria/meta, sessão de foco, pausa, retomada, conclusão e histórico; utilizar um material TXT com anotação vinculada; verificar recuperação; acrescentar auditoria proporcional e corrigir dificuldades reproduzidas. O objetivo acadêmico é relacionar problemas, decisões, verificações e evidências das três disciplinas, sujeito à ementa e à orientação docente.

Não houve reinício do projeto, troca de framework/banco, treinamento de modelo, contratação de GPU, serviço pago, publicação do código novo no Site, merge, release ou alteração da instalação pessoal. O trabalho usa somente o projeto pessoal Ritmo e dados sintéticos. Não foram utilizados sistemas, documentos, imagens ou processos de empresa.

## 2. Justificativa e base acadêmica

Uma aplicação de estudo depende de compreender o que foi salvo e de preservar dados diante de conflito ou perda de rede. O Ritmo já possuía funções locais e um piloto web separado. Por isso, uma evolução delimitada permitiu observar problemas reais de software sem atribuir ao semestre todo o desenvolvimento anterior ou introduzir complexidade apenas para ampliar a apresentação.

O manual fornecido pelo estudante, Projeto Integrador: Guia Completo para o Aluno(a), FASUL, 2026, foi lido integralmente. A p. 2 vincula o projeto às disciplinas vigentes e à orientação do professor; as p. 4-5 estruturam identificação, tema, objetivo, justificativa, execução, resultados e conclusão; as p. 2 e 5-6 exigem ao menos três fotografias; a p. 6 apresenta os pesos 30%, 25%, 20%, 15% e 10%. O cronograma das p. 1 e 3 requer confirmação no portal. Há formulações diferentes sobre apresentação nas p. 3 e 7, devendo o formato ser confirmado com o orientador.

Esse manual sustenta a organização do PI, mas não prova que auditoria transacional, testes ou determinado método de usabilidade fazem parte das ementas deste período. A matriz de rastreabilidade mantém essa ressalva. Não foram declaradas certificação ou conformidade integral com normas, nem previstas notas de avaliação.

## 3. Diagnóstico e distinção do legado

A main foi conferida em 7815c54 e a PR #13 permaneceu aberta em rascunho, no HEAD da0c7d1. Uma branch e worktree de continuação preservaram o checkout original e a PR anterior. O desktop continua baseado em Python, API loopback, SQLite/FTS5 e janela nativa. O web usa Worker JavaScript, autenticação gerenciada Sites/ChatGPT, D1 e R2 privado; não depende do computador pessoal ligado para suas funções de estudo, mas o fluxo remoto autenticado ainda tem validação pendente.

Na base web já existiam snapshots JSON versionados por conta, atualização condicional da versão (CAS), recibos de idempotência, cotas, materiais, busca, notas e recuperação. A sessão única é regra do domínio protegida por CAS, não um índice parcial SQL; essa descrição foi corrigida. A documentação também foi ajustada para os limites efetivos de 500 notas e 500 sessões, sem aumento de cotas. Não se contabilizou como criação desta etapa o que já existia.

A linha de base foi reexecutada antes das modificações: 16 testes passaram em 24,481 segundos, sem ignorados, e o roteiro de interface passou com dados sintéticos. Os registros históricos de 179 testes desktop e dos testes web de 19/11 foram mantidos separados e não foram usados como aprovação automática do novo código.

## 4. Etapas de execução e decisões

Primeiro foram produzidos diagnóstico, requisitos, matriz e plano priorizado. As alternativas de apenas escrever mensagens no console ou incluir todo o log no snapshot foram descartadas: a primeira perderia consistência com o commit e a segunda ampliaria consultas e backups dos estudos. Escolheu-se uma tabela pequena de auditoria no mesmo D1, reutilizando o batch transacional existente. Não houve normalização geral ou migração de banco por motivação acadêmica.

Em seguida, testes reproduziram entradas JSON inválidas recebendo 503, upload recusado permanecendo como em andamento e backup bem-sucedido exibido como alerta de erro. As correções validam a estrutura no servidor e distinguem operação sem confirmação, rejeição e sucesso. O ensaio demonstrável também revelou uma corrida entre abertura e busca de material; passou a existir estado explícito de carregamento e espera pelo texto antes de liberar a busca. A regressão foi conferida contra a implementação anterior.

A migração 0001 acrescentou auditoria sem alterar a 0000 aplicada. Cada evento contém ID e instante do servidor, identificador interno da conta, ação, resultado, recurso técnico, correlação e versão. Estado, recibo e evento são confirmados no mesmo batch. Uma atualização de zero linhas não cria evento; repetição idempotente não duplica o negócio. A consulta é da própria conta, paginada em 20 registros por padrão e 50 no máximo, com ordem estável por instante e ID.

A retenção é de até 200 registros recentes por conta, com filtro de 30 dias na consulta. A limpeza física ocorre em novas gravações bem-sucedidas; não existe cron prometido. Exportação registra preparação completa do snapshot na versão exportada, não comprova recebimento de download e não incrementa a versão da conta. A restauração registra a operação no destino sem importar log de outra conta.

Uma revisão independente apontou um problema importante na compensação após falha de resposta: o banco podia confirmar a importação e, durante a recuperação por recibo, o arquivo R2 já referenciado ser removido. A reprodução com batch D1 real confirmou o defeito. A correção preserva chaves referenciadas no estado confirmado e, se a consulta do recibo também falhar, conserva os objetos diante do resultado desconhecido. A interface mantém o pedido e sua chave ao receber 503/429, permitindo reenvio exato.

## 5. Associação às disciplinas

Qualidade e Usabilidade de Software: organização preventiva por requisitos, critérios, linha de base, revisão e protocolo; verificação do produto por regressões de feedback, rascunho, carregamento, conflito, teclado e layout. Foi preparado um protocolo humano de quatro tarefas, mas não houve participante observado nesta rodada.

Desenvolvimento Back-end: validação independente da interface, reaproveitamento de rotas/domínio/store, transições e relógio servidor, CAS e idempotência, contrato dos endpoints, nova migração e ensaio de recuperação. A persistência por snapshot foi mantida e seus limites foram documentados, sem apresentar complexidade adicional como benefício por si só.

Segurança e Auditoria de Sistemas: fronteira confiável do dispatch, controle por conta, dados de arquivos tratados como não confiáveis, minimização dos campos de log, consulta limitada, consistência com o commit e falhas induzidas. Não há registro de textos, nomes de arquivos, email, senhas, cookies, tokens ou headers completos na auditoria. O log não é imutável, inviolável ou trilha forense completa.

Essas relações são propostas técnicas fundamentadas nos artefatos produzidos e continuam a confirmar pelas ementas oficiais. O relatório não afirma acesso a outros chats, projetos acadêmicos ou materiais não recuperados.

## 6. Resultados técnicos executados

O código funcional desta rodada foi registrado no commit 79aa55c. A suíte final local executou 31 testes em 35,767 segundos: 31 aprovados, zero falhas e zero ignorados. Os testes herdados foram preservados e os novos foram vinculados a riscos, sem meta artificial de contagem. Os tempos de suíte não são um benchmark de melhoria de desempenho, pois a composição mudou.

Foram verificados entrada inválida, transições, foco/pausa, proteção de sessão concluída, concorrência, repetição, isolamento de IDs e backup, referências de notas, arquivos inválidos, migração de estado anterior, paginação/retenção e restauração. Falha de auditoria antes do commit reverteu estado/recibo e compensou provisórios. Perda de resposta depois de commit real foi ensaiada em importação e restauração, com recibo legível e indisponível: os originais permaneceram acessíveis e o replay não duplicou eventos.

A verificação de interface cobriu as seis telas em 390, 768, 1366 e 1920 px, nos temas claro e escuro, sem overflow horizontal ou erros JavaScript observados. Controles, foco e teclado foram exercitados; isto não é uma auditoria completa de acessibilidade ou teste em celular físico. A auditoria npm não apontou vulnerabilidades conhecidas na consulta desta rodada; esse resultado não prova ausência de falhas de segurança.

O roteiro automatizado completou as quatro tarefas: matéria/meta; sessão com pausa, recarregamento, retomada, conclusão e histórico; TXT, busca, nota e referência; exportação e restore em outra conta sintética vazia. Capturas são de execução real com dados sintéticos. O JSON registra tempos da ferramenta, deixando tempo humano, erros do participante, ajuda e comentários como nulos. Não houve entrevista, usuário observado ou medição de aprendizagem.

## 7. Registro fotográfico e evidências

R1 - 23/11/2026, diagnóstico e planejamento: linha de base, matriz e captura técnica do estado inicial. Fotografia real do estudante executando a etapa: pendente.

R2 - 23/11/2026, implementação e verificação: testes de regressão, auditoria, falhas induzidas, revisão e captura técnica do log. Fotografia real da atividade: pendente.

R3 - 23/11/2026, ensaio técnico de demonstração: capturas de histórico, referência em tela pequena e recuperação. Apresentação/avaliação humana final e terceira fotografia: pendentes.

As capturas técnicas não substituem as três fotografias sem aceite do orientador. Fotografias, identificação completa, assinaturas, documentos acadêmicos integrais e comprovantes devem ser mantidos fora do Git público e acrescentados somente ao relatório privado autorizado. Não foram geradas imagens simulando presença ou execução acadêmica.

## 8. Limitações e conclusão técnica provisória

A evolução observada acrescentou uma trilha consistente com as mutações e corrigiu falhas reproduzidas de validação, feedback e recuperação de commit incerto. Os resultados sustentam o funcionamento técnico nos cenários sintéticos executados; não permitem concluir satisfação de usuários, aprendizagem, segurança absoluta ou aprovação curricular.

Não houve alteração do Site publicado nesta etapa. O host de acesso ao navegador estava indisponível; login remoto legítimo, expiração, outro dispositivo e importação sob limites reais da hospedagem permanecem pendentes. Persistência após republicação só poderá ser aprovada com registros antes/depois e nova autorização, não concedida nesta rodada. O desktop preservado é alternativa de demonstração identificada, não comprovação dos requisitos remotos web. DIST-01 permanece questão da distribuição Windows.

PDF complexo pode esgotar recursos do isolate. Resultado de commit desconhecido pode deixar provisórios órfãos em R2; não se arrisca remover um original confirmado nessa incerteza. A trilha pode ser alterada por quem administra o banco, não registra todas as falhas de acesso e não pode garantir um evento no próprio banco indisponível. A recuperação por conta não é ensaio de desastre de todo o provedor.

Próximos passos: obter ementas e aprovação do orientador; preencher identificação e reflexão pessoal em versão privada; realizar autoavaliação humana ou avaliação consentida, sem generalizar uma amostra individual; produzir três fotos reais; verificar acesso remoto legítimo e, em etapa autorizada, persistência após redeploy. A reflexão sobre o que o estudante aprendeu pessoalmente ainda deve ser escrita pelo próprio estudante. A conclusão acadêmica final permanece em elaboração.

## Referências e artefatos

FASUL EDUCACIONAL. Projeto Integrador: Guia Completo para o Aluno(a). São Lourenço/MG, 2026. Documento de 7 páginas fornecido pelo estudante, não redistribuído; páginas associadas em rastreabilidade.md.

Ritmo, repositório Dinox75/Ritmo: base main 7815c54; PR #13 da0c7d1; evolução funcional 79aa55c. Artefatos públicos sanitizados: diagnostico.md, requisitos.md, rastreabilidade.md, plano.md, endpoints.md, validacao.md, usabilidade.md, demonstracao.md e evidencias/. As ementas específicas ainda precisam ser anexadas à análise autorizada. Nenhuma norma foi usada para declarar certificação.
