# Usar o Ritmo

## Pré-requisitos e compatibilidade

Pacote Windows x64, com WebView2 instalado. O QA local foi executado no Windows
build 26300 com Edge/WebView2 e GPU NVIDIA GTX 1660 SUPER. Isso não demonstra
compatibilidade com qualquer máquina. Os modelos não estão no ZIP: o catálogo
atual usa llama.cpp Windows CUDA 12.4 e requer hardware compatível; estudo manual
e aula booleana estruturada não exigem modelo. Android não está incluído nesta prévia.
O programa ainda não tem assinatura digital. Leia [segurança](../SECURITY.md).

No desktop, a janela se autoriza automaticamente. No modo navegador, informe o
código de uso único mostrado no lançador/terminal. Reiniciar exige nova autorização;
um cliente HTTP sem credencial não consegue ler seus dados.

## Recuperar uma cópia de segurança

O backup inclui SQLite consistente, originais e a configuração efetivamente
usada. Pesos/runtime e áudio escolhido não entram. Antes de apagar dados, copie
o ZIP para outra pasta/disco: backups internos também são apagados.

Para restaurar, feche o Ritmo e preserve a pasta de dados atual. Extraia o ZIP
numa pasta temporária separada e confira `database/ritmo.db`, `materials/` e
`config/config.json`. No pacote, copie o banco para a pasta de dados efetiva e
os originais para `materials/`; copie a configuração para `config.json` nessa
pasta. No desenvolvimento, o destino da configuração é `config/local.json`
no checkout, não `storage/config.json`. Confirme o diretório em Diagnóstico.
Abra, confira matérias, notas, materiais e uma sessão; teste pausa/retomada antes
de substituir a cópia de recuperação. Não abra o SQLite de dentro do ZIP.
Não existe sincronização automática com outro computador ou celular.

Em **Estudar**, selecione a matéria, defina a meta semanal e inicie o foco. Pause quando precisar: só o tempo de foco entra na meta. A sessão em andamento é lembrada ao reabrir. Use o leitor para buscar e anotar trechos de PDF, DOCX e TXT de até 5 MB. PDFs digitalizados sem texto precisam de OCR externo.

Em **Configurações → Ambiente de estudo**, ajuste tema, intensidade da janela, volume e lembretes. Chuva e ruído marrom são gerados localmente; também é possível escolher áudio do computador. O arquivo de áudio não entra no backup. O som só começa quando você clicar em reproduzir.

Em **Configurações → Tutor local**, selecione o modelo e clique em **Instalar modelo escolhido**. Os downloads são explícitos e verificados pelo [catálogo](../local_ai/models.json); reserve espaço para pesos, runtime e pelo menos 1 GB adicional. O runtime do catálogo é Windows CUDA 12.4. O Qwen3 4B é o candidato principal; o 1.7B permanece experimental. Você pode estudar mesmo sem pesos ou câmera.

Na aula guiada, use **Continuar para exercício**, envie a tentativa e, após a correção, use **Aprofundar**. Uma **Nova pergunta** durante a espera preserva o exercício. Abra as citações para conferir o excerto; a referência mostra o material recuperado, sem garantir que ele sustente a resposta. A pesquisa externa opcional envia só a consulta revisada à Wikipédia e usa os resultados que você selecionar.

A [aula booleana experimental](qa/qa-boolean-lesson.md) usa gabarito calculado para exercícios previstos. Ela trabalha conceito, exemplo, tentativa, dica, nova tentativa, correção e transferência. A configuração vem desligada. Para abrir uma instância separada com dados próprios, na raiz do repositório execute:

```powershell
.\.venv\Scripts\python.exe scripts/open_boolean_lesson.py --run ../Laboratorio/aula-isolada --port 8771
```

Se essa porta estiver em uso por outra instância, escolha uma porta livre. O modo consegue verificar representações booleanas suportadas; não avalia prosa livre nem outros temas.

## Dados e recuperação

No código, o padrão é `storage/ritmo.db` e `config/local.json`. O executável padrão guarda dados em `%LOCALAPPDATA%\Ritmo`. Se o seu ambiente já usa um lançador que redireciona a pasta de dados, preserve a configuração do lançador: o local do executável, sozinho, não determina o local do banco. Confira o caminho em **Configurações → Diagnóstico** antes de qualquer cópia.

**Criar backup** gera um ZIP com cópia consistente do banco, configuração e originais importados. Pesos e runtime ficam de fora. Para restaurar, feche o Ritmo, copie a pasta atual para outro local e restaure banco, configuração e materiais no diretório de dados correto. Abra o aplicativo e confira as matérias e os materiais. Nunca misture dois bancos copiando apenas seus arquivos auxiliares.

Câmera, detecção de janela e ociosidade são opcionais e começam desligadas. O Ritmo não usa tempo ou presença para deduzir emoção, capacidade ou aprendizagem.
