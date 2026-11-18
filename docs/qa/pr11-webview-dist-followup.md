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
