# Inventário local — 17/11/2026

Levantamento somente de leitura em `A:\Projetos & Estudos\Ritmo`.
Nenhuma pasta foi movida ou apagada. Tamanhos em GiB, aproximados;
ambientes virtuais e arquivos ignorados pelo Git entram no total.
O pacote novo foi contabilizado após a compilação.

| Pasta | GiB | Destinação sugerida |
| --- | ---: | --- |
| Aplicativo | 0,607 | Preservar: instalação pessoal; atalho da Área de Trabalho aponta para `Aplicativo/Ritmo/Ritmo.exe`. |
| Dados | 0,001 | Preservar integralmente: banco, configuração, materiais e backups pessoais. |
| Modelos | 5,805 | Preservar: pesos e runtime locais, separados do executável. |
| Repositorio | 0,898 | Preservar: checkout principal, `.git` compartilhado pelos worktrees e ambiente Python usado no desenvolvimento. Continua na branch de fontes; não foi trocado de branch. |
| PackageValidation10 | 1,589 | Preservar nesta rodada: checkout da PR #10, ambiente de compilação e novo pacote validado. |
| TrainingLab | 0,009 | Worktree limpo da PR #9. Pode ser desativado posteriormente com os comandos próprios do Git, após conferir processos/atalhos que ainda o utilizem. Não mover manualmente. |
| TutorIntegration | 0,002 | Worktree limpo da PR #8; candidato posterior a desativação pelo Git após integração. |
| TrainingLabBaseline8d02ce1 | 0,003 | Baseline detached limpo. Pode ser arquivado após preservar sua identificação e confirmar que scripts de comparação não dependem do caminho. |
| TutorBaseline4ad48e9 | 0,001 | Baseline detached limpo; mesma cautela. |
| AndroidWorktree | 0,001 | Branch Android limpa em `f0b7f18`; manter separado do Windows. Não representa APK concluído. |
| AndroidBuildTools | 8,925 | Ferramentas Android; não são necessárias ao desktop. ZIPs e extrações duplicadas podem ser arquivados após conferir o SDK/JDK efetivamente usados. |
| Codigo | 0,898 | Repositório legado limpo em `30df089`, branch `feat/ritmo-local-tutor`. Candidato a arquivo histórico completo, incluindo `.git`; é histórico diferente do repositório Ritmo. |
| Legado | 7,686 | Cópias da migração anterior de C:/OneDrive. Arquivar somente após comparar arquivos exclusivos; não classificado como descartável. |
| Build | 2,328 | Stages e caches antigos de outubro. Candidatos a arquivo após conservar os relatórios/hashes e confirmar que nenhum atalho aponta para eles. |
| BuildValidation | 1,602 | Pacotes de teste, capturas e relatórios anteriores. Arquivar como evidência por versão; não é instalação pessoal. |
| Versoes anteriores | 6,062 | Recuperação de instalações anteriores. Arquiváveis como pastas completas, preservando pelo menos a versão necessária à recuperação dos dados. Não apagar por serem antigas. |
| Laboratorio | 0,139 após os testes | Brutos, calibração, provas e instâncias sintéticas. Preservar os resultados selados e as referências 0/12/60 textos; execuções concluídas podem ser arquivadas inteiras depois de parar suas próprias instâncias e atualizar lançadores. |

Os worktrees existentes estavam limpos, incluindo Android e os dois baselines.
`Codigo` é outro repositório; não deve ser removido como se fosse worktree do Ritmo.
O diretório `.git` em `Repositorio` sustenta os demais worktrees: não arquivar
essa pasta isoladamente nem mover seus diretórios à mão.

Não há autorização nesta rodada para executar nenhuma das sugestões de arquivo.
Não foi feita varredura recursiva de todo o disco C:; o inventário cobre a árvore
central do projeto em A: e identifica o destino do atalho pessoal existente.
