# Referência didática guiada pelo código

Execução inline na PR9, a partir de d86ae28. Usar planejamento, testes de
regressão e revisão independente; decisões rotineiras delegadas pelo usuário.

- [x] Preservar hashes dos relatórios/brutos/calibração/prova anteriores e conferir PR.
- [x] Construir três famílias novas em relação à calibração: negação de conjunção,
  implicação e equivalência. Três intervenções por família, nove comparações.
- [x] Selecionar excertos pertinentes dos materiais já arquivados, verificar hashes
  e licenças e ligar cada escolha pedagógica ao excerto/linha original.
- [x] Testar referências automáticas, mutações de fatos, spoilers nos dois campos,
  perda do objetivo da pergunta e observador incapaz de alterar decisões.
- [x] Rodar geração atual e reescrita com mesmo Qwen1.7B, amostragem e casos;
  referência é determinística. Juiz4B observa todas as27 saídas, sem voto decisório.
- [x] Mostrar três versões, contagens por família e limites de prova no painel;
  nenhum candidato/corpus de treino exportado, inconclusivos excluídos automaticamente.
- [x] Suíte, QA390/1366/1920, relatório, commit/push e descrição PR, sempre rascunho.

Critérios fixados antes do piloto: erros lógicos explícitos são veto do código;
preservação literal/estrutural demonstra apenas esses fatos. Ausência de erro
detectado não prova correção semântica da prosa. Pergunta útil e spoiler implícito
podem ficar inconclusivos. Observações do4B nunca decidem aceitação. Nenhuma
saída será incorporada ao corpus nesta rodada, mesmo uma referência íntegra.

Resultado: nove referências,18saídas do1.7B e27observações4B.8reescritas idênticas,1inconclusiva;1equivalência falsa do gerador vetada por auditoria suplementar nos mesmos brutos. Tudo fora do corpus.89testes e QA390/1366/1920 passaram; sem treino ou instalação.
