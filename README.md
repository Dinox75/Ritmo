<p align="center"><img src="web/icon.svg" alt="Ícone do Ritmo" width="80"></p>

# Ritmo

**Distribuição em preparação:** a [PR #11](https://github.com/Dinox75/Ritmo/pull/11)
trata os bloqueios da primeira prévia. Consulte [distribuição](docs/distribuicao.md),
[segurança e reporte privado](SECURITY.md) e os relatórios antes de usar um pacote
de teste sobre dados existentes.

**Um espaço de estudo pessoal para organizar matérias, manter o foco e praticar com retorno sobre o raciocínio.** O aplicativo executa e guarda seus dados no computador.

[Começar](#começar) · [Gerar o aplicativo](#gerar-o-aplicativo) · [Como funciona](#como-funciona) · [Documentação](docs/README.md) · [Roadmap](docs/roadmap.md)

## Começar

1. Crie uma matéria e defina uma meta semanal.
2. Inicie uma sessão e importe um PDF com texto, DOCX ou TXT. Busque no material e anote o trecho relevante.
3. Pause, retome e conclua. Confira as sessões e a evolução; tempo de pausa fica separado.
4. Se quiser, ative o som ambiente ou configure o tutor local por matéria.

Para rodar o **código** no Windows, instale Python 3.11 e WebView2. Na raiz do repositório:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe desktop.py
```

O modo navegador usa `python main.py serve` e abre em [127.0.0.1:8765](http://127.0.0.1:8765). As dependências de sensores são opcionais; veja [instalação e uso](docs/uso.md).

## Gerar o aplicativo

O perfil padrão `preview` exige **Python 3.14.10 x64** e não inclui câmera
nem presença por webcam. A interface informa essa limitação; o estudo e os
sensores opcionais de janela e entrada permanecem disponíveis. A cadeia antiga
MediaPipe → protobuf fica restrita ao perfil de desenvolvimento `full` (Python
3.11), que ainda não está aprovado para distribuição pública. Nenhum desses
comandos altera a instalação sem `-Install`.

No Windows, este comando compila e testa o executável com dados temporários. O pacote fica em **`build/RitmoStage-<id>/Ritmo/`** por padrão:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

Mantenha a pasta `_internal` junto ao `Ritmo.exe`. Use `-Install` somente quando quiser substituir a instalação e atualizar o atalho, após os testes. O pacote local não é assinado. Veja [compilação, testes e recuperação](docs/desenvolvimento.md).

## Como funciona

| Área | O que você pode usar |
| --- | --- |
| Estudo | Sessões, pausas, metas, evolução, tema, intensidade da janela, player e lembretes opcionais |
| Materiais | Leitor, busca, anotações e referência ao excerto quando localizado com segurança |
| Tutor local | Dúvidas e aula guiada por matéria/sessão; requer um modelo instalado e pode errar mesmo com citações |
| Aula booleana experimental | Dica sem resposta, nova tentativa, correção específica e exercício em outro contexto; desligada por padrão e sem modelo |
| Laboratório | Preparação, avaliação e painel privado. Nenhum adaptador foi treinado ou aprovado |

A interface chama uma API local, que guarda sessões e notas em SQLite e busca trechos com FTS5. Se você instalar um modelo, o Ritmo usa llama.cpp e Qwen3 locais, sem chave de API. A consulta à Wikipédia só envia a consulta revisada quando você a solicita. Os sensores começam desligados; a prévia não contém o recurso de câmera.

Veja [dados, backups e limites](docs/uso.md), [arquitetura e fundamentos](docs/arquitetura.md) e [resultados de validação](docs/qa/README.md). Testes de software e ensaios de modelos não comprovam aprendizagem com estudantes.

O Ritmo se originou do WorkWatch e hoje mantém um repositório independente. [Licença MIT](LICENSE).
