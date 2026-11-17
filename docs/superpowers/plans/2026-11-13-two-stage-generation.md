# Geração em duas etapas — continuação da PR9

Executar nesta worktree isolada, sem treino, cobrança ou alteração da instalação.
Preservar integralmente validated.json de0/12, proof.json e execução local anterior.

- [x] Construção determinística de dez famílias de raciocínio, três intervenções
  por família; exercício, árvore/gabarito, exemplo contrastante e tentativa de
  aluno com fato correto e transformação equivocada coerentes.
- [x] Modelo recebe tarefa pronta e gera somente intervention/verification_question.
  Triagem de cada campo, lógica, spoilers, utilidade/contexto da pergunta e juiz
  independente; nenhum conserto por inclusão de interrogação.
- [x] Separação de famílias/AST e documentos; prova histórica intocada. Fonte
  de expressões Python separada para a validação, com licença/hash verificados.
- [x] Comparação pareada local entre prompt antigo recuperado de8d02ce1 e novo,
  mesmos30 casos/fontes/parâmetros/modelos, rubrica comum e bruto preservado.
  Nenhum teste da prova usado como entrada da geração.
- [x] Painel com tabela família×intervenção, principais descartes e exemplos
  reais, comparação das abordagens sem confundir com treino base/adaptador.
- [x] Testes regressivos/controlados, piloto real, captura nas três larguras,
  hashes históricos conferidos, relatório e atualização da própria PR9.

Não baixar/treinar pesos. Não reduzir200/30/30. A recomendação final dependerá
das respostas e das falhas encontradas, inclusive falsos positivos do juiz.

Resultado observado: estrutura melhor, 0/30 aprovados nas duas abordagens; corrigir pedagogia/avaliacao antes de ampliar. Nenhum treino.
