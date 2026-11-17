# Pacote Windows da PR #10 — 17/11/2026

Base conferida: PR #10, branch `chore/ritmo-repository-organization`, commit
`66793462bc33a810a2a93541c87f069ee0c74c01`, destinada à `main` em `13f1f19`.
Os checkouts anteriores estavam limpos. Nenhum `AGENTS.md` aplicável foi encontrado.
Foi criado o worktree `A:\Projetos & Estudos\Ritmo\PackageValidation10`, sem trocar
a branch do checkout principal. `docs/IMPLEMENTACAO.md` não existe nesta versão;
foram lidos README, `docs/desenvolvimento.md` e o script de build.

## Pacote

Compilado **sem `-Install`**, sem pular o QA de navegador:

```powershell
git fetch origin
git worktree add 'A:/Projetos & Estudos/Ritmo/PackageValidation10' -b chore/ritmo-repository-organization origin/chore/ritmo-repository-organization
$env:TEMP='A:\Projetos & Estudos\Ritmo\Laboratorio\tmp-two-stage'
$env:TMP=$env:TEMP
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

Saída do executável:
`A:\Projetos & Estudos\Ritmo\PackageValidation10\build\RitmoStage-20261117101128-b7f304\Ritmo\Ritmo.exe`.
Manter a pasta `_internal` ao lado. Não é instalador nem pacote assinado.

- SHA-256 do EXE: `6caf49617915661255dbdcf2c37abc42ce95de0f61f357e2422c743017e8a1e6`.
- EXE: 24.550.677 bytes; pasta do aplicativo: 652.850.038 bytes, 2.675 arquivos.
- Windows x64, build 26300; Python 3.11.9, PyInstaller 6.22.3,
  pywebview 6.2.1 e Playwright 1.64.0, Edge/WebView2 instalado.
- PyInstaller concluiu em 99,871 s, fora a preparação das dependências.
- Dependências resolvidas registradas em [dependencies.txt](windows-pr10/dependencies.txt).

O build tentou primeiro o cache sem índice; faltavam dependências e o próprio
script fez a instalação no novo `.buildvenv`. Houve avisos de plataformas
opcionais não disponíveis (por exemplo, Android), sem erro de compilação.
Os commits desta rodada alteram scripts de QA e documentação, sem modificar
o código executável compilado em `6679346`.
Revisão independente focada não encontrou bloqueadores. Duas observações menores
foram atendidas no QA booleano: registrar caminho/hash do EXE no próprio JSON e
capturar erros JavaScript desde a primeira navegação, inclusive com o modo
desligado. Os nove fluxos foram repetidos após essas melhorias, novamente OK.

## Comandos e resultados

Com `$py='.buildvenv\Scripts\python.exe'`, `$exe` apontando para o pacote acima e
`$qa='A:\Projetos & Estudos\Ritmo\Laboratorio\pr10-packaged'`:

```powershell
& $py -m unittest discover -s tests -q
# Estes dois comandos também são executados pelo build:
& $py scripts/smoke_windows.py $exe "$qa\smoke.json"
& $py scripts/qa_packaged_windows.py $exe
& $py scripts/qa_study_atmosphere_packaged.py $exe "$qa\screens" "$qa\atmosphere.json"
& $py scripts/qa_study_sources_packaged.py $exe "$qa\sources.json"
& $py scripts/qa_boolean_packaged.py $exe "$qa\boolean"
& $py scripts/qa_packaged_audio_output.py $exe "$qa\audio.json" --loopback-input 31
git diff --check
```

| Verificação | Resultado observado |
| --- | --- |
| Suíte no venv existente | 102 testes, 50,214 s, OK, sem skips |
| Suíte com dependências do build | 102 testes, 38,867 s, OK, sem skips |
| Smoke do executável | `ready=true`, SQLite temporário, processo encerrou e porta liberada |
| Fluxo empacotado | Matéria, sessão vinculada à conversa, ausência de modelo explicada sem perder rascunho, memória explícita, material TXT, busca, original preservado, notas, backup ZIP, pausa persistida após reabrir, conclusão e porta liberada |
| Ambiente | Janela WebView2 real; foco avança, pausa congela foco/áudio, retomada continua, conclusão para áudio e gera toque opcional, lembretes e tema persistem |
| 390/1366/1920 px | Estudar e Configurações a 85%, rolagem com navegação fixa, sem overflow; capturas inspecionadas |
| Player no navegador controlado | Chuva e ruído marrom iniciam/param e variam ganho; WAV local em loop e volume zero |
| Referências | Excerto único destacado; ambíguo abre bloco com aviso; busca, seleção e notas continuam funcionando |
| Pesquisa opcional | Nada enviado ao editar; só consulta revisada + `confirmed=true` no clique; cinco resultados reais da Wikipédia com links e acesso |
| Aula booleana no EXE | Desligada por padrão; nove fluxos (três cenários × três larguras), dica/retry/correção/transferência, teclado, reload durante espera, fora de escopo e porta liberada |
| Saída de áudio Realtek/WebView2 | Chuva, ruído marrom e WAV aprovados por mixagem estéreo, sem mudar os critérios |

O novo `qa_boolean_packaged.py` testa a API e interface **do executável**, não
um servidor Python substituto. Usa tarefas sintéticas existentes para as tentativas.
Os testes de fontes usam uma resposta sintética persistida para testar a referência;
os cinco resultados de pesquisa vieram da rede, sem simular a busca.

## Correção no teste de áudio

A primeira execução do script antigo falhou porque o player está recolhido no
layout compacto. Corrigido o roteiro: abrir `#session-audio summary` se necessário
e aguardar o volume visível antes de interagir. Não houve mudança no aplicativo.

A repetição chegou à medição, mas encontrou áudio significativo com o Ritmo
parado: RMS de fundo 0,07318, chuva ativa 0,09550 e após parar 0,09967.
O critério de sinal ativo acima do fundo recusou o resultado. Nenhum limite foi
afrouxado. O usuário pausou os outros sons para nova medição.

A terceira execução passou, mantendo o mesmo EXE e os mesmos limites:

| Som | RMS ativo | RMS após parar |
| --- | ---: | ---: |
| Chuva | 0,0094264 | 0,0000441 |
| Ruído marrom | 0,0256338 | 0,0000521 |
| WAV | 0,0908385 | 0,0000437 |

Também passaram a frequência de 220 Hz do WAV, predominância de graves no
ruído marrom e encerramento do processo/porta. Os logs das duas falhas iniciais
permanecem locais como `audio-first.log` e `audio-retry.log`; a execução aprovada
está em `audio-final.log` e [audio.json](windows-pr10/audio.json).
Nenhum defeito no código do aplicativo precisou ser corrigido nesta rodada.

## Preservação e limites

Comparados 2.747 arquivos existentes antes/depois: SHA-256, tamanho e data para
instalação/dados; tamanho e data para modelos. Nenhuma alteração encontrada.
A primeira comparação auxiliar precisou normalizar os timestamps ISO que o
PowerShell converte automaticamente para DateTime; hashes já eram iguais.
O manifesto detalhado permanece local, sem publicar nomes de arquivos pessoais.

Instalação e atalho pessoal continuam em `Aplicativo/Ritmo/Ritmo.exe`.
Não houve `-Install`, cópia de banco pessoal, mudança de configuração pessoal,
movimentação ou exclusão de diretórios. Os testes usam `LOCALAPPDATA` temporário
e `.migration_disabled`. Não houve treinamento, ampliação de corpus, download de
pesos, GPU contratada ou release. Resultados e prova selada anteriores preservados.

Os testes validam software nesta máquina, sem comprovar aprendizagem ou
confiabilidade geral do tutor. Não foi repetido benchmark generativo dos Qwen
nesta rodada; as falhas pedagógicas anteriores continuam documentadas.
A pesquisa requer Internet e não comprova a veracidade das páginas. PDF/DOCX
são cobertos pela suíte; a importação feita neste QA empacotado foi TXT.
Não se validou câmera física nem outra máquina. Não houve medição acústica
externa dos alto-falantes; o teste de áudio captura sua saída digital Realtek.

Artefatos em [windows-pr10](windows-pr10/) e logs/capturas completos em
`A:\Projetos & Estudos\Ritmo\Laboratorio\pr10-packaged`.
O [inventário local](inventario-local-2026-11-17.md) apenas recomenda candidatos
a arquivo; nenhuma dessas ações foi executada.

As PRs #3, #7, #8 e #9 são ancestrais desta versão (`git merge-base --is-ancestor`
retornou 0 para as quatro). A #4 não é ancestral e continua fora da consolidação.
As #1/#2/#5/#6 já estavam fechadas antes desta rodada.
