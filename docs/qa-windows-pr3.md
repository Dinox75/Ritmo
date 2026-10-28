# Validação local do pacote Windows — PR #3

## Revalidação do HEAD `ce6df52` em 28/10/2026

Novo pacote PyInstaller: `Ritmo.exe` SHA-256 `0326451c191c71e1b137bdab154f40fae52a2a8321e4b6b1697b4e17a14fcbaf`. Os ensaios usaram `%LOCALAPPDATA%` temporário e `.migration_disabled`, sem ler materiais, notas ou conversas pessoais.

| Cenário | Resultado do novo pacote |
| --- | --- |
| `smoke_windows.py` | Inicialização pronta e encerramento da porta: aprovado. |
| `qa_packaged_windows.py` | Fluxo de pausa/reabertura, materiais, notas, backup e porta: aprovado. |
| `qa_study_atmosphere_packaged.py` | Cronômetro, pausa/retomada, player, volume, lembretes, conclusão, reabertura e janela nativa: aprovados. |
| Estudar e Configurações a 85% | Em 390, 1366 e 1920 px, a página rolou 400 px e a navegação manteve a mesma coordenada vertical. Em 390 px, topo da navegação: 741 → 741; em 1366 e 1920 px: 0 → 0. A camada visual aplicou `rgba(0, 0, 0, 0.15)` e não houve rolagem horizontal. Foram examinadas capturas antes e depois da rolagem. |
| Saída para os alto-falantes | Na janela nativa WebView2, a “Mixagem estéreo” do dispositivo padrão Realtek registrou chuva, ruído marrom e WAV sintético. RMS de base 0,000036; em reprodução: 0,00937, 0,02621 e 0,09088, respectivamente; após parar: no máximo 0,000053. O WAV mostrou pico em 220,7 Hz, compatível com seu tom sintético de 220 Hz. |
| Suíte do repositório | 31 testes aprovados. |

A captura de áudio foi feita no retorno digital da saída Realtek, sem gravar as amostras ou captar o microfone. Ela confirma sinal encaminhado ao dispositivo padrão e seu silêncio após parar; não substitui uma medição acústica externa dos alto-falantes. O ensaio usa um índice de “Mixagem estéreo” específico deste computador. A [documentação de depuração do WebView2](https://learn.microsoft.com/en-us/microsoft-edge/webview2/how-to/debug-visual-studio-code) descreve a porta local de depuração usada apenas durante esse teste.

Com as dependências Windows e QA instaladas, os comandos adicionais foram:

```powershell
.\.venv\Scripts\python.exe scripts\qa_packaged_audio_output.py <caminho-do-Ritmo.exe> <relatorio-temporario.json> --loopback-input 31
```

O script de áudio usa um WAV gerado em memória, descarta as amostras da mixagem após calcular as métricas e remove a pasta temporária. O índice `31` corresponde à “Mixagem estéreo” Realtek deste computador e precisa ser escolhido novamente em outra máquina. O pacote não foi assinado nem publicado como release.

Após a aprovação do pacote preparado, foi feito um novo backup SQLite consistente do banco pessoal (`PRAGMA integrity_check=ok`) e da configuração. A instalação anterior foi preservada. O executável instalado manteve o SHA-256 acima; os hashes do banco e da configuração não mudaram durante a troca. No caminho instalado, `smoke_windows.py`, `qa_packaged_windows.py`, o teste de ambiente e a captura de áudio passaram novamente com dados temporários. Na captura instalada, o RMS em reprodução foi 0,00943 (chuva), 0,02580 (ruído marrom) e 0,09083 (WAV), voltando a no máximo 0,000053 depois da parada.

Uma execução inicial do teste de ambiente no caminho instalado parou antes da rolagem porque o foco do controle de intensidade se perdeu ao enviar a tecla Home para a página. O teste passou a enviar a tecla diretamente ao controle; duas execuções posteriores passaram. O executável não foi alterado por esse ajuste do teste.

## Ensaio anterior, antes da correção da navegação

Data: 28/10/2026. Pacote PyInstaller `Ritmo.exe` SHA-256 `02c21628a78fc4e1c8e177e740c4987534ca4667f6c4aa0e42b8eb140c281ce9`. Executado neste computador Windows com WebView2 e Edge, usando uma pasta `%LOCALAPPDATA%` temporária e `.migration_disabled`. O ensaio não leu nem registrou banco, materiais, notas ou conversas pessoais.

## Resultado

| Cenário | Resultado observado |
| --- | --- |
| Telas Estudar e Configurações em 390, 1366 e 1920 px | Seis capturas com dados sintéticos examinadas; sem rolagem horizontal (`scrollWidth` igual à largura em todos os casos). A captura móvel inclui o conteúdo abaixo da primeira dobra. |
| Cronômetro | O foco avançou; durante a pausa ficou estável; a retomada voltou ao estado de foco. |
| Chuva suave e ruído marrom | As duas fontes WebAudio iniciaram em loop, responderam ao volume máximo e pararam pelo controle. |
| Arquivo local | WAV sintético iniciou em loop, respondeu a volume zero, pausou e retomou com a sessão. O arquivo não foi importado para os dados. |
| Lembretes | Avisos de pausa e tempo excedido apareceram após simulação do relógio. O aviso não pausou automaticamente; o botão de pausa pausou. |
| Conclusão | Resumo exibido, áudio ambiente parado e dois osciladores criados para o toque opcional. |
| Reabertura | O processo encerrou com código zero, liberou a porta, reabriu e restaurou a sessão pausada e o tema salvo. |
| Janela nativa | A janela WebView2 ficou visível no processo do Ritmo na abertura e na reabertura. O atalho da Área de Trabalho aponta para o executável instalado. |
| Fluxos gerais do pacote | `smoke_windows.py` e `qa_packaged_windows.py` passaram com dados temporários. |
| Suíte do repositório | 31 testes, todos aprovados. |

O primeiro pacote revelou rótulos pouco legíveis no tema escuro (contraste 1,95:1 no campo de materiais do tutor e 3,01:1 nos rótulos de tempo dos lembretes), além de um painel de histórico claro. A correção em `web/atmosphere.css` foi empacotada novamente. No pacote acima, os dois rótulos medidos atingiram 10,02:1, e o histórico usa fundo escuro. As capturas finais foram feitas com movimento reduzido para evitar registrar a transição de entrada no meio da animação.

O teste de áudio verifica reprodução e volume no navegador, o estado das fontes WebAudio e do elemento de mídia e a criação do toque. Não mede o som que sai fisicamente dos alto-falantes. Os lembretes foram disparados com relógio simulado; não foi necessário aguardar minutos reais. A validação cobre este computador Windows, não outros dispositivos ou versões de WebView2.

Depois que o pacote passou nos testes, foi feito um backup SQLite consistente do banco pessoal, com `PRAGMA integrity_check=ok`, e uma cópia da configuração. A instalação anterior foi preservada em outra pasta. O executável instalado foi novamente ensaiado com dados temporários; o banco e a configuração pessoais permaneceram com os mesmos hashes durante a atualização.

## Reproduzir

Com `.venv` e Edge disponíveis, execute os testes com um pacote já construído:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe scripts\smoke_windows.py <caminho-do-Ritmo.exe> <relatorio-temporario.json>
.\.venv\Scripts\python.exe scripts\qa_packaged_windows.py <caminho-do-Ritmo.exe>
.\.venv\Scripts\python.exe scripts\qa_study_atmosphere_packaged.py <caminho-do-Ritmo.exe> <pasta-de-capturas> <relatorio-temporario.json>
```

O último script cria uma matéria e uma sessão sintéticas, um WAV de um segundo em memória, salva capturas e um JSON de resultados e remove a pasta temporária ao terminar. O modelo local não é instalado nesse ensaio.
