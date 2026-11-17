# Desenvolvimento e distribuição

Use um checkout canônico para o código, com dados e modelos ao lado se você quiser administrar tudo em uma pasta. Essa é uma convenção de organização: confirme o caminho real em **Configurações → Diagnóstico** e no lançador antes de mover dados.

```text
Ritmo/
  Repositorio/        checkout Git; build/ é gerado aqui por padrão
  Aplicativo/Ritmo/  pacote instalado, se você usa esse layout
  Dados/             banco e arquivos, se o lançador aponta para cá
  Modelos/           pesos e runtime escolhidos nas configurações
  Laboratorio/       execuções isoladas; pode ser arquivado separadamente
```

1. Verifique `git status --short` em cada cópia. Commits exclusivos, alterações não commitadas e SQLite ficam fora de uma cópia simples do Git. Preserve-os antes de desativar worktrees antigas.
2. Faça um backup pelo Ritmo, feche o aplicativo e confira os caminhos de banco, modelos e atalho. Preserve a pasta antiga até abrir o novo pacote e validar matérias e materiais. Cópias de QA e históricos de build podem ser arquivados depois.
3. Na raiz do checkout, execute `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_windows.ps1`. O script usa Python 3.11, monta `build/RitmoStage-<id>/Ritmo/`, roda smoke com SQLite temporário e valida o fluxo no Edge. A variável `RITMO_BUILD_ROOT` permite escolher outro disco. `-SkipBrowserQA` pula o fluxo de navegador e mantém o smoke.
4. Para atualizar a instalação, repita com `-Install`. Se o checkout estiver em `Ritmo/Repositorio` ou `Ritmo/Codigo` e existirem `Dados` e `Modelos` ao lado, o pacote instalado fica em `Ritmo/Aplicativo/Ritmo`; senão, fica em `%LOCALAPPDATA%/RitmoApp/Ritmo`. A instalação anterior recebe uma pasta de recuperação. Use `-SkipShortcut` para preservar um atalho já configurado. Isso não muda, por si só, o diretório de dados do executável.

Mantenha o EXE e `_internal` juntos. Se a nova instalação falhar, feche-a e aponte o atalho para a versão anterior ou restaure a pasta anterior inteira. Se já houve migração do SQLite, use a cópia de dados compatível com a versão restaurada.

Para desenvolver sem empacotar, leia [Começar](../README.md#começar). Para sensores no Windows, instale também `requirements-windows.txt`; deixe-os desligados quando não forem necessários.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-qa.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Os testes de interface usam o Edge instalado ou o executável Chromium definido em `RITMO_QA_BROWSER`. Sem Playwright ou navegador, os testes de navegador são ignorados. Os scripts `qa_*.py` e `smoke_windows.py` mantêm seus caminhos; para parâmetros e resultados históricos, consulte [validação](qa/README.md). O laboratório tem [instruções próprias](../training/lab/README.md) e suas dependências não são necessárias para o build do desktop.
