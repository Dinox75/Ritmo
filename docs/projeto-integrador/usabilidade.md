# Avaliação prática de usabilidade

## Protocolo preparado (avaliação humana ainda não realizada)

Objetivo: observar se uma pessoa encontra e conclui o fluxo mínimo e compreende o que foi salvo. Usar somente dados sintéticos; explicar que os estudos deste ensaio são descartáveis. Registrar versão, largura/dispositivo, tema, conexão e método de acesso. Não coletar identificação completa no Git. Se apenas o estudante executar, classificar como **autoavaliação**, nunca amostra de usuários ou pesquisa com participantes independentes.

| Tarefa | Instrução ao participante | Condição de conclusão observável |
| --- | --- | --- |
| T1 | Criar uma matéria “Lógica do ensaio” e meta de 60 minutos | Matéria visível; edição de meta salva confirmada |
| T2 | Iniciar, pausar, retomar e concluir uma sessão; encontrá-la no histórico | Estado muda após confirmação e sessão concluída aparece na Evolução |
| T3 | Importar TXT fornecido, localizar uma palavra e criar nota vinculada | Nota aparece, referência abre trecho e destaque seguro |
| T4 | Encontrar exportação de backup e explicar como recuperaria os dados | Localiza controle; explica conta vazia, dados incluídos e sessão restaurada pausada; ensaio de restore só em destino sintético vazio |

Cronometrar do término da leitura da instrução à conclusão ou desistência. Não sugerir caminho antes de observar; registrar ajuda solicitada/oferecida e seu momento. Anotar erros de navegação/validação e tentativas, sem atribuir erro a capacidade da pessoa. Perguntar “o que você acredita que foi salvo?” e “onde buscaria recuperação?”. Comentários devem ser transcritos com consentimento, sem inventar respostas.

| Tarefa | Participação | Concluiu | Tempo humano observado | Erros | Ajuda necessária | Comentário real |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | não realizada | pendente | não medido | não observado | não observado | não coletado |
| T2 | não realizada | pendente | não medido | não observado | não observado | não coletado |
| T3 | não realizada | pendente | não medido | não observado | não observado | não coletado |
| T4 | não realizada | pendente | não medido | não observado | não observado | não coletado |

Essas lacunas não são zeros e não permitem concluir satisfação, aprendizagem ou facilidade para usuários. O manual (p. 2) pede articulação com disciplinas; o conteúdo específico de usabilidade continua a confirmar pela ementa.

## Inspeção e automação técnicas nesta rodada

Foram reproduzidos: status de importação preso em “enviando” após erro; backup bem-sucedido apresentado como alerta de erro; JSON inválido tratado como indisponibilidade; pedido descartado diante de 503 mesmo após possível commit. No ensaio automatizado também houve corrida ao buscar antes de terminar a leitura do material. Foram acrescentados feedback de carregamento e espera da busca pelo texto, sem redesenho. Os testes do status de carregamento foram conferidos com a implementação anterior para distinguir defeito do produto de uma falha inicial no preparo do teste.

As regressões de rascunho, conflito, duas abas, falha/reenvio e teclado da PR #13 foram preservadas. Capturas técnicas reais da execução usam dados sintéticos e não são fotografias de participação acadêmica. Durações `automationMs` do roteiro são tempo da ferramenta, **não** tempo de usuário ou medida de compreensão. Veja [validação](validacao.md) e [evidências](evidencias/README.md).
