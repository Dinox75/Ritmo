# Validação local do pacote Windows — PR #3

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
