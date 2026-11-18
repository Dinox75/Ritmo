# PR #11 — janela nativa e componentes distribuídos

Rodada iniciada em `5c21c7a`, usando o [run 44105669895](https://github.com/Dinox75/Ritmo/actions/runs/44105669895). Resultados anteriores permanecem históricos; nenhuma aprovação é transferida entre ZIPs. Instalação, banco, modelos e atalho pessoais preservados.

## Ponto de partida e quatro etapas

O run compilou e publicou o artefato `ritmo-distribuicao` (ID `14338503434`). Seu ZIP tem SHA-256 `bcbc4513225417da6a567806ed97b0ddb630960ba0de90f2ffe9e04a4f86768d`, diferente do candidato local anterior. No job `clean-windows`, extração/verificação e smoke passaram; o QA falhou ao conectar ao CDP. O log antigo confirma servidor iniciado, mas não comprova janela carregada ou autorização. Portanto **não permite atribuir a causa apenas ao CDP**.

O aplicativo agora registra eventos estruturados e restritos: entrada do EXE/backend; importação, criação, apresentação e carregamento da janela; autorização da sessão; entrega privada ao lançador de QA; encerramento. Campos não incluem URLs, códigos, cookies, cabeçalhos ou conteúdo pessoal. O diagnóstico exporta apenas eventos permitidos, nunca o log bruto.

`qa_native_windows.py` verifica hashes do ZIP e de todos os arquivos extraídos antes de lançar. A aceitação usa UI Automation na própria janela, **sem código do lançador, CDP, navegador externo ou POST de QA para autorizar a janela**. Cria matéria sintética, confirma a escrita no banco temporário, percorre os diálogos de apagamento, escolhe exclusivamente “Não”, verifica preservação, fecha a janela pelo caminho nativo e exige encerramento natural e porta livre. Registra separadamente EXE, janela, autorização e conexão UIA, além do diagnóstico CDP e da sessão gráfica.

O QA complementar pode receber seu próprio código de uso único por um pipe anônimo herdado do processo lançador. O código não passa por arquivo, ambiente, URL ou log. Isso remove a dependência de CDP dos testes complementares e **não substitui a aceitação nativa**, que desabilita esse pipe. A promoção exige `native-ui.json` aprovado, sessão gráfica disponível, ações completas e vínculo exato commit/run/ZIP/EXE. Ausência, encerramento forçado ou aprovação de navegador externo são recusados.

O workflow preserva diagnósticos com `if: always()`, inclusive quando o teste nativo falha. O artefato de aprovação contém somente JSONs planos; capturas e relatórios complementares ficam em artefato separado. Não há afrouxamento automático para aceitar uma VM externa sem verificar sua cadeia de evidências.

## Ensaio local histórico de automação nativa

No Windows `10.0.26300`, sessão gráfica 1, `qa_native_windows.py` passou contra o ZIP local de **32ccac40e5eeffab69dd9a468585951381786c7f**:

- ZIP `60f2132035a3bcd213538ca1d5d497cef7bc84fc045a4fcfce7f0cb6363ead7e`;
- EXE `b623faaa9e58773092681839b158f3d3706f38a7f9cd33e5dc31bad92579e7b7`;
- quatro etapas verdadeiras; matéria gravada pela janela; cancelamento preservou matéria e processo; fechamento natural, código 0 e porta liberada;
- capturas restritas à janela do Ritmo; evidência local em `Laboratorio/pr11-native-probe-32ccac4-v3/`.

O primeiro ensaio chegou à escrita, mas não encontrou os diálogos JavaScript embutidos no controle WebView2. A automação foi corrigida para procurar também na árvore UIA da janela; a repetição passou. **Este host não é Windows limpo e este ZIP não é o ZIP do run 44105669895 nem o novo candidato.**

Depois foi baixado o **artefato exato 14338503434** do run 44105669895, com digest de transporte `8d7a68aa4792d8e05cc2acd2ac8b04c0a48274e1f34f40ad8ea797805662258c` conferido antes da extração. O mesmo ensaio nativo passou no ZIP `bcbc4513225417da6a567806ed97b0ddb630960ba0de90f2ffe9e04a4f86768d`, EXE `c58a6e25e0bde020d5381ac5c7f5830ee506a315f5a4e2d6ab2d29d38afbb578`, código do merge sintético `9a3e28e1a0693844b0f81d1db47fe6e1d358a748`, head da PR `5c21c7a`. Quatro etapas, cancelamento, encerramento natural e liberação de porta confirmados. [Relatório integral](pr11-run44105669895-native-host.json) e [janela depois do cancelamento](pr11-run44105669895-native-host.png). O CDP também respondeu neste host; portanto isso demonstra que o ZIP funciona aqui, **sem concluir que a causa no runner foi exclusivamente CDP, nem satisfazer Windows limpo**.

A suíte local após essas alterações executou **164 testes, 59,327 s, OK, sem ignorados**. Uma execução durante a gravação simultânea do novo módulo de scanner falhou na importação daquele arquivo; a execução integral foi repetida após o módulo estar completo. Nenhuma falha foi contada como aprovação.

A verificação final antes de enviar o novo candidato executou **168 testes em 71,341 s, OK, sem ignorados**. Inclui regressões dos diagnósticos de smoke, gate nativo, pipe e inventário/avisos. YAML e sintaxe PowerShell também foram analisados. A revisão independente não encontrou bypass concreto; suas duas lacunas de diagnóstico foram corrigidas com relatório de falha inicial e identificadores fixos de ação, sem texto bruto da exceção.

## DIST-01: decisão de empacotamento

O pacote anterior efetivamente incluía protobuf 4.25.9 e módulos protobuf congelados: não era apenas dependência instalada no ambiente de build. A cadeia de câmera era `monitor.presence_detector` → cvzone/MediaPipe 0.10.21 → protobuf `>=4.25.3,<5`. A análise anterior encontrou PYSEC-2026-1805 nessa versão. Atualizar apenas protobuf violaria o limite do MediaPipe; atualizar toda a cadeia exige revalidar detecção, modelos e API.

O scan foi repetido sobre os **47 componentes comprovados pelo inventário do ZIP do run 44105669895**, com pip-audit 2.10.1, PyPI, `--no-deps --disable-pip --strict`, sem instalar/resolver dependências. [Saída integral](pr11-run44105669895-pip-audit.json): 11 ocorrências reportadas, **6 identificadores únicos em 2 pacotes**, sem skips: protobuf 4.25.9 (PYSEC-2026-1805, correções 5.29.6/6.33.5) e setuptools 65.5.0 (PYSEC-2022-43012, PYSEC-2025-49, PYSEC-2026-1918, PYSEC-2026-3447 e GHSA-xmj3-9gf7-h52w; maior correção indicada 84.1.0). A API devolveu duplicações de alguns IDs, mantidas no bruto e não contadas como CVEs distintos. Esse resultado **não é** o resultado de outro ZIP local nem do candidato novo. No ZIP antigo, protobuf tem 1 arquivo nativo e 31 módulos congelados; MediaPipe tem 594 arquivos e 541 módulos, cvzone 20/13. A análise nativa e de licenças tem escopo adicional ao pip-audit.

A menor mudança é separar a câmera como capacidade de build. O padrão `preview` exclui câmera/MediaPipe/OpenCV/protobuf e dependências científicas. A configuração pessoal não é reescrita; o sensor indisponível não inicia, e UI/API explicam a ausência. O perfil `full` preserva o caminho de desenvolvimento, **sem aprovação pública de sua cadeia antiga**. Testes controlados verificam ambos os caminhos sem acionar hardware.

A prévia usa CPython 3.14.10 x64, com instalador PSF fixado por SHA-256 e assinatura, provisionado somente no runner descartável. O pedido de instalação local do novo Python foi rejeitado pela revisão automática, sem motivo adicional; não houve instalação local desse toolchain. A compatibilidade de Python.NET 3.2.1 com CPython 3.14 consta na [distribuição oficial](https://pypi.org/project/pythonnet/3.2.1/) e será validada no pacote, não presumida pela documentação.

O inventário nativo combina hashes locais da base instalada verificada, SPDX oficial e regras/fontes de origem. O SPDX não contém hashes de cada DLL; não é apresentado como atestação binária do fornecedor. O SDK WebView2 é ligado por hash ao NuGet oficial e inclui seus avisos. O bootloader PyInstaller exige TOC de transformação e hash do resultado. Licenças não resolvidas continuam `NOASSERTION`, com bloqueio de revisão; gerar SBOM não encerra DIST-01.

## Comandos de reprodução

```powershell
.buildvenv\Scripts\python.exe -m unittest discover -s tests -q
./scripts/build_windows.ps1 -Profile preview -SkipBrowserQA
python scripts/release_bundle.py verify --out release-assets --commit <commit> --run-id <run>
python scripts/qa_native_windows.py <Ritmo.exe> --bundle release-assets --output native-evidence --run-id <run> --head-commit <commit>
python scripts/qa_packaged_windows.py <Ritmo.exe>
python scripts/qa_security_packaged.py <Ritmo.exe> security.json
python scripts/qa_accessibility_packaged.py <Ritmo.exe> accessibility
```

Os comandos de build nesta rodada não usam `-Install`. Resultados do novo candidato, scanners, cobertura e bloqueios finais serão registrados abaixo depois da execução. Não há release nem aprovação de publicação enquanto esses critérios estiverem pendentes.

## Histórico dos novos runs

- [44154620521](https://github.com/Dinox75/Ritmo/actions/runs/44154620521), head `7283ca7`: 168 testes, 64,826 s, uma falha na comparação textual do caminho temporário `RUNNER~1` com seu nome Windows canônico `runneradmin`. O runtime já selecionava o caminho canônico correto; o teste agora compara o launcher e o diretório com a raiz resolvida, mantendo os testes de redirecionamento/adulteração. Esse run parou antes de construir o novo ZIP e não fornece aprovação de pacote.
- A CLI real de cve-bin-tool 3.4 foi inspecionada: acrescentado `--report` para produzir evidência também quando não há achados, sem tratar a ausência de arquivo como resultado limpo. O teste do comando falhou antes dessa correção e passou depois.
- [44155283583](https://github.com/Dinox75/Ritmo/actions/runs/44155283583), head `60492c031996ef9d8fbfa25f48d0bb76242a45af`, código de merge sintético `2639ea63658e4a7fd1b6025a3fb0bb034c6e8124`: build e **clean-windows passaram**. ZIP de 21.557.019 bytes, SHA-256 `0dc17d4a621fab5a089c42fef56bcba7ac2822f56c235c390feeb03a2065f880`; EXE `5c3ca1bfc87923c28862cc65375146fbc44be639388fc97fc8b27a07ea5f75a8`. Artefato 14362225068, transporte `2dfe704a6c35d4233be85e8fc43a306769aba12ec000a8682c08df7fb7794a54`.
  - [Aceitação nativa integral](pr11-run44155283583-native-clean.json): Windows 10.0.26100, sessão gráfica 2, EXE/janela/autorização/UIA aprovados, escrita sintética verificada, cancelamento preservado, encerramento natural e porta livre. **CDP não conectou**, enquanto a janela funcionou; agora há evidência da diferença. [Janela real após cancelar](pr11-run44155283583-native-clean.png).
  - Passaram também smoke, sessão/pausa/reabertura/conclusão, materiais/notas, backup/configuração/restauração, Booleano, segurança e contraste/teclado em 390/1366/1920 px. QA também repetido neste host no ZIP baixado. O runner novo tem componentes pré-instalados do Actions; não é alegação de teste em todas as versões de Windows.
  - Artefato QA 14361995595, transporte `36289ac50c013a9a970c69417672a4263c586e7c81d4a70838ccf0bad16d8160`; diagnósticos 14361775868, transporte `00476b9870f1d52dd76c59d5a9f7914352ef505a29119e4b7c02fdd9fc48cf64`.
  - Nenhum nome/arquivo protobuf, MediaPipe, cvzone ou `_upb` no ZIP; capacidade `camera:false`. 19 componentes Python, 192 arquivos, 93 binários. [Pip-audit sem achados](pr11-run44155283583-pip-audit.json). O scanner nativo antigo falhou por timeout do mirror; [relatório/cobertura](pr11-run44155283583-scan.json) preservado. Grype independente depois reportou 26 correspondências e lacunas, registradas no relatório de distribuição. **DIST-01 permaneceu aberto**.
  - Revisão encontrou DLLs API-set/UCRT do Windows copiadas, duas dependências de Tcl sem classificação e falta de aviso do fork libffi do CFFI. As correções subsequentes geram outro ZIP; este hash não recebe a aprovação do próximo e vice-versa.

Após as correções adicionais, a suíte local passou **174 testes em 57,741 s, sem ignorados**. O novo candidato ainda precisa repetir build, inventário, scanners e aceitação nativa.

O run [44206510696](https://github.com/Dinox75/Ritmo/actions/runs/44206510696), head `48502f1`, passou pela suíte e pelo toolchain, mas parou antes do ZIP: o filtro exigia que todo stub API-set/UCRT coletado viesse fisicamente de System32. Esse requisito era mais estreito que a decisão de não redistribuir os contratos fornecidos pelo Windows 10+. O filtro passou a registrar os hashes e a distinção de origem sem atribuir uma origem não comprovada. A aprovação continua exigindo execução real sem essas cópias. Nenhum resultado desse run foi apresentado como pacote aprovado.

O run [44207460719](https://github.com/Dinox75/Ritmo/actions/runs/44207460719), head `5a576d9`, compilou e passou o smoke de build, mas foi recusado antes da inicialização no runner novo: o verificador excluía toda `_internal/release/` da comparação de payload, omitindo o novo `os-prerequisites.json`. A comparação foi corrigida para excluir apenas os três arquivos gerados conhecidos; os demais continuam obrigatoriamente cobertos pelo manifesto e seus hashes. Foi adicionado um teste que falhou antes e passou depois, e `pack` agora verifica imediatamente o próprio ZIP. Essa recusa não foi reportada como falha de WebView2 nem como aprovação nativa.

O run [44208563133](https://github.com/Dinox75/Ritmo/actions/runs/44208563133), head `90dbdf4`, voltou a passar build e **clean-windows**. ZIP `0310391722d5d6b690d3c0ebd1b68b46ecc0272315a6b471f9a01fd84d255df2`, 20.507.355 bytes; EXE `7c6a2203079ba803b54f89a81b468ad0e507e6eb8239e2b8763c6b4b1273c118`, código de merge `2d8658dc20fbdbf94392d3d958b243fdb03affae`. Inventário: 149 arquivos, 49 binários, **zero binário sem correspondência**, 44 DLLs de compatibilidade excluídas e registradas. Isso não encerra a revisão de licenças/vulnerabilidades. O Grype no CI não iniciou porque o script de preparação só exportava seu caminho para o passo seguinte; a exportação foi corrigida também para o processo atual. O erro não foi contado como scan aprovado.

Na repetição nativa no host do ZIP anterior `8d6bc5fd…`, houve falhas da ferramenta após as quatro etapas iniciais passarem. A árvore UIA deste Windows expunha campos de Configurações atrás do diálogo, e o prompt identifica a pergunta no próprio campo Edit, sem nó Text separado. O QA passou a preencher exclusivamente o campo cujo nome começa com “Digite APAGAR”, dentro dos processos próprios; não escreve no primeiro campo de fundo. A recusa IDNO usa UIA Invoke, evitando a dependência de ativação de BM_CLICK. Quatro regressões controladas cobrem seleção, ambiguidade e limite de processos. O ensaio host-v5 passou com escrita, cancelamento, fechamento natural e porta livre. As falhas anteriores foram preservadas e não atribuídas ao aplicativo ou a outro ZIP.

## Candidato de encerramento — distribuição bloqueada

[Run 44210488562](https://github.com/Dinox75/Ritmo/actions/runs/44210488562), head
`a1aac5768ce69fc1f7c95900ea7944df5db548f9`, fonte de merge sintético
`9ceaa6fbdbf67b9124210911ae489fbe6c8564eb`. Somente documentação/evidências
foram acrescentadas depois deste código. [Manifesto completo](pr11-final-build-info.json).

| Identidade | Valor |
| --- | --- |
| ZIP | `Ritmo-v0.1.0-preview.1-windows-x64.zip` · 20.507.869 bytes |
| SHA-256 ZIP | `5a2333e0eacfa371ef3d93c8aa813000d6cba919b5defebd3c72a0c24ebfc766` |
| SHA-256 EXE | `e24c9bf55c68d96912d1c26a51350b2eea33b4b3fd66fa86e7084700307504da` |
| Artefato do build | `14386296233` · transporte `8b66977f0fc539dae3788d2d185c87a4a6490e889eb4a56bf99c9a4478917a9f` |
| Artefato de QA | `14386072525` · transporte `8270b2513d80c8e3d064f3d6b8e95c84805658e5efb5df766cf290023c70f97e` |
| Diagnósticos | `14385713372` · transporte `42d06334a41a20ead14ac3b56401cf7b1155a202160dba72990663bf6391a657` |
| Scans | `14386172339` · transporte `ce138cb217c1c6ea69ff36a2f82ef03812361ae8570b2ecdb3a2a4b12c37bcdc` |

Cópia local conferida e extraída em
`A:\Projetos & Estudos\Ritmo\Laboratorio\pr11-run-44210488562\assets\` e
`..\extracted\Ritmo\Ritmo.exe`. O ZIP local é o baixado do Actions, não uma
recompilação local. Os artefatos do Actions expiram em 02/12/2026; os relatórios
selecionados abaixo ficam preservados no Git, e a cópia local não foi removida.

### O que passou

- **179 testes locais em 51,423 s**, sem ignorados. **179 no Actions em 73,130 s**, OK.
- Build sem `-Install`, smoke e verificação de todos os hashes. Inventário de
  149 arquivos, 49 binários e 19 componentes Python; **zero binário sem origem
  correspondente**. Sem protobuf/MediaPipe/cvzone ou pesos. [Componentes/versões/licenças](pr11-final-components.json).
- `clean-windows`: [aceitação nativa](pr11-final-native-clean.json), Windows
  10.0.26100, sessão gráfica 2. EXE, janela, autorização e UIA verdadeiros;
  matéria criada pela janela; cancelamento manteve dados; WM_CLOSE encerrou
  naturalmente e a porta foi liberada. **CDP indisponível**, sem substituir a
  janela por navegador. [Captura real depois de cancelar](pr11-final-native-clean.png).
- QA complementar do mesmo ZIP: sessão/pausa/retomada/conclusão/reabertura,
  materiais/busca/notas vinculadas a trechos, backup/configuração e restauração numa pasta
  separada, fluxos booleanos, [21 recusas de API e cancelamento](pr11-final-security.json),
  [contraste/teclado](pr11-final-accessibility.json) em 390/1366/1920 e dois temas.
  [Atestado técnico](pr11-final-clean-windows.json), com revisões de distribuição ainda requeridas.
- Neste host, `qa_study_atmosphere_packaged.py` no ZIP final: [12 verificações](pr11-final-atmosphere.json),
  janela WebView2 visível; cronômetro, player de chuva/ruído marrom/WAV, volume,
  pausa/retomada, lembretes, reabertura e conclusão; navegação fixa nas três
  larguras a 85%. É verificação de estado/sinal interno de áudio, sem medição
  física dos alto-falantes nesta rodada.
- Perfil sem câmera testado em UI/API e sem enumerar dispositivos. Perfil com
  câmera testado com provedor controlado, sem capturar imagens nem validar hardware.

### O que impede a publicação

O job `distributed-components` **falhou corretamente**; build e `clean-windows`
passaram. [Pip-audit](pr11-final-pip-audit.json): 19 componentes, nenhum achado,
skip ou ausência. O cve-bin-tool continuou sem obter sua base pelo mirror;
[falha/cobertura preservadas](pr11-final-legacy-scan.json), sem alegar scan nativo completo.

O Grype 0.122.0 **concluiu** com a base de 17/11/2026 e controle positivo
Heartbleed confirmado: **27 correspondências** — SQLite 14, Expat 5, CPython 4,
XZ 3, zlib 1. [Resumo, cobertura e hash do banco](pr11-final-grype-summary.json)
e [respostas completas do scanner](pr11-final-grype.json). O acréscimo sobre o
candidato anterior é zlib 1.3.2, CVE-2026-85091, relacionado a `gz_write()` após
erro de escrita. Não houve supressão automática para obter aprovação.

Permanecem bloqueadores concretos de DIST-01:

1. Revisar os requisitos de exploração dos CVEs do **SQLite 3.50.4/FTS5** e
   **Expat 2.9.0** no fluxo de materiais/DOCX e recuperação. A presença do
   componente não prova exploração do Ritmo, mas testes funcionais benignos
   também não comprovam a ausência de risco. O caso SQLite CLI `.recover` é
   distinto e não é usado como prova de vulnerabilidade no app.
2. Verificar a cobertura do **fork libffi incorporado ao CFFI 2.1.1**: origem e
   aviso MIT registrados, sem inventar uma versão upstream/CPE que não o representa.
3. Concluir as condições aplicáveis de redistribuição de **VCRUNTIME140.dll e
   VCRUNTIME140_1.dll 14.51.36247.0**. Os bytes estão ligados ao instalador PSF
   verificado e os avisos estão incluídos; o inventário mantém `NOASSERTION` e
   as duas pendências, em vez de converter a presença do aviso em aprovação.
4. Classificar os alertas condicionais/restantes, inclusive zlib 1.3.2 e XZ,
   usando as funções/entradas realmente expostas. A ressalva de FIPS em
   CVE-2026-119170 e os casos específicos do CLI não justificam ignorar os demais.

Consequência: **PR #11 permanece em rascunho. Não houve merge, ensaio real de
promoção, tag, Release nem envio a Packages**. A tag `v0.1.0-preview.1` estava
livre na consulta, mas as revisões não foram marcadas como aprovadas. Logo não
há downloads de Releases/Packages para comparar; a igualdade entre canais não
foi simulada. Os resultados anteriores continuam históricos, vinculados aos seus ZIPs.

A instalação pessoal permaneceu com EXE
`0bbf4346bab2ecd8e1237938c20bedbffc6a122f6b715521f94a43b3e35a926c`,
mesmo hash antes/depois da conferência final. Banco, materiais, modelos,
configuração e atalho pessoais não foram atualizados. Sem instalação, não foi
necessário copiar o banco pessoal; todos os ensaios de recuperação usaram dados sintéticos.

### Comandos finais adicionais

```powershell
python scripts/scan_grype_bundle.py --assets <assets-do-run-44210488562> --out <novo-diretorio> --commit 9ceaa6fbdbf67b9124210911ae489fbe6c8564eb --run-id 44210488562 --grype <Grype-0.122.0-verificado>
python scripts/qa_study_atmosphere_packaged.py <EXE-extraido-do-ZIP> <capturas-temporarias> <relatorio.json>
```

O hash fixado do Grype, as opções do pip-audit/cve-bin-tool e a reprodução com
snapshot estão no [relatório de distribuição](dist01-supply-chain.md). Limites:
sem teste de aprendizagem, certificação ISO/WCAG, leitor de tela completo,
hardware de câmera ou todos os sistemas Windows suportados.
