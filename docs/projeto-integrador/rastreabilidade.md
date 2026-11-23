# Matriz de rastreabilidade

Esta é a matriz inicial, produzida após diagnóstico e antes da implementação. Coluna de resultado será preenchida por execução; associação curricular **a confirmar pela ementa**. Não é declaração de certificação, benefício educacional ou estudo prévio de uma norma.

| Disciplina informada | Problema | Alteração/atividade planejada | Critério de aceitação | Evidência esperada |
| --- | --- | --- | --- | --- |
| Qualidade e Usabilidade de Software | Status de operação pode contradizer erro/confirmado | Reproduzir e corrigir feedback de upload/backup, manter rascunhos | Falha não mostra envio em andamento/sucesso; confirmação com papel de status | Regressão UI + captura sintética; avaliação humana ainda pendente |
| Qualidade e Usabilidade de Software | Resultados históricos não separam o novo escopo | Requisitos, revisão, baseline e protocolo de quatro tarefas | Cada resultado tem versão, comando/atividade, ambiente e limite | Diagnóstico, requisitos e validação |
| Desenvolvimento Back-end | Entrada JSON inválida pode receber erro de infraestrutura | Validação estrutural na rota existente | `null`/array inválidos retornam 400 sem mutação | Teste de integração e contrato API |
| Desenvolvimento Back-end | Concorrência e tempo são essenciais, já existentes | Validar sem recriar CAS/idempotência/totais/restore | Uma sessão, conflito 409, replay sem duplicar, foco/pausa sem intervalo indevido | Testes herdados reexecutados e ensaio de recuperação |
| Segurança e Auditoria de Sistemas | Falta correlação de operação a evento técnico | Nova migração e auditoria no mesmo commit do estado/recibo | Sem evento em rollback/conflito; replay sem duplicação; sem conteúdo pessoal | Migração preservando estado, falha induzida e inspeção de campos |
| Segurança e Auditoria de Sistemas | Trilha pode expor outras contas ou crescer sem limite | Consulta própria com cursor/limite e retenção proporcional | Conta B não lê A; máximo por página; expurgo definido | Integração D1 real local com duas identidades sintéticas |
| Três disciplinas | Demonstração precisa ser explicável e verificável | Roteiro, endpoints, recuperação e relatório em elaboração | Cada passo corresponde a uma evidência real, sem usuário/foto inventado | Demonstração automatizada técnica; participação humana separada |

## Documentos necessários

Manual do PI localizado e lido integralmente (7 páginas): **FACULDADE FASUL EDUCACIONAL. Projeto Integrador: Guia Completo para o Aluno(a). São Lourenço/MG, 2026**, arquivo fornecido pelo estudante `manual-projeto-integrador.pdf`. Original permanece fora do Git. Faltam as ementas oficiais (versão/período/unidades) de: Qualidade e Usabilidade de Software; Desenvolvimento Back-end; Segurança e Auditoria de Sistemas. Também faltam orientação sobre aproveitamento do projeto, aprovação do tema/escopo, prazo do portal, formato da apresentação e aceitação de capturas em lugar de fotografias.

Os pesos informados foram conferidos na p. 6: relatório 30%, coerência 25%, execução/fotos 20%, apresentação 15%, prazo 10%. Não representam nota prevista.

## Associação documental verificada

| Fonte e local | O que sustenta | Documento/atividade do Ritmo | Limite da associação |
| --- | --- | --- | --- |
| Manual, p. 2, definição e etapas 01/02 | Articulação das disciplinas vigentes, projeto prático e orientação | Esta matriz, escopo e pendências do orientador | Não substitui ementas nem aprova aproveitamento do Ritmo |
| Manual, p. 2, etapa 03; p. 5-6, registro fotográfico | Execução e pelo menos três fotografias reais | Plano de três registros em evidencias/README.md | Capturas são técnicas; equivalência a fotos depende de aceite |
| Manual, p. 3, etapas 04/05; p. 4-5, modelo | Relatório com identificação, disciplinas, tema, objetivo, justificativa, execução, resultados e conclusão, entrega PDF | relatorio.md e PDF parcial sanitizado | Identificação pessoal, turma e assinatura ficam fora do repositório público |
| Manual, p. 1 e p. 3, cronograma | Datas devem ser confirmadas no portal | Pendência de prazo efetivo | Não assumir Junho/Setembro como prazo individual nem declarar atraso |
| Manual, p. 3, apresentação; p. 7, observação final | Apresentação e orientação do professor | Roteiro de demonstração e pergunta ao orientador | Redações sobre obrigatoriedade diferem; confirmar formato/calendário |
| Manual, p. 6, critérios | Pesos da avaliação | Organização dos documentos e evidências | Sem promessa de pontuação ou aprovação |

Os vínculos específicos entre auditoria transacional, testes/feedback e as **três ementas** continuam **a confirmar pela ementa**. O manual sustenta o processo do PI, não o programa detalhado das disciplinas. Nenhuma norma técnica foi usada como certificação ou declaração de conformidade.
