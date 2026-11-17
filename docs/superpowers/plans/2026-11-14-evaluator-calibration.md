# Calibração independente da avaliação

Objetivo: medir falsos positivos/negativos sem treino, sem alterar os 60 brutos,
a referência 0/12 ou a prova final. Execução inline, na branch existente da PR9.

- [x] Registrar por código pares mínimos e expectativas antes das inferências;
  separar desenvolvimento e reserva por família. Não são dados de treino.
- [x] Rodar triagem antiga e juiz antigo em TODOS os casos de desenvolvimento.
- [x] Corrigir com desenvolvimento; congelar hashes de regras/prompt antes da reserva.
- [x] Rodar regras e juiz corrigidos em desenvolvimento e reserva, separadamente.
  Reserva não autoriza ajustes posteriores. Critério prévio: nenhum ruim aceito e
  pelo menos 90% dos bons aceitos, por avaliador, na reserva; sem discordância lógica.
- [x] Reavaliar todos os 60 brutos sem gerar substitutos; registrar mudanças de
  triagem e juiz, incluindo casos recusados pela triagem. Juízo bruto preservado;
  gabarito calculado é autoridade, não voto do modelo.
- [x] Expor calibração e decisões no painel, rodar suíte e QA visual, documentar,
  commit/push e atualizar PR em rascunho. Só gerar novo piloto se passar o critério.

Decisão técnica: referências sintéticas autorais com regras explícitas; medir a
triagem pedagógica isolada de licença/duplicação e reaplicar o screen completo
nos brutos. O juiz recebe tarefa/gabarito/traço, nunca os rótulos esperados.
Não usar a prova selada para escrever a bateria. Hashes protegem arquivos antigos.

Resultado: gate falhou no juiz (0/6 referências boas integrais); nenhum novo piloto. Reavaliação60 concluída, 0 aprovados. 83 testes e QA390/1366/1920 passaram. Regras congeladas preservadas; restauração de fontes é somente correção de entrada, sem novo julgamento.
