# DIST-01: origem, licenças e scan do candidato Windows

Gerar um SBOM não fecha DIST-01. A revisão usa o ZIP exato, o commit/run de origem, os arquivos efetivamente coletados, os módulos congelados e as bibliotecas nativas. Um scan do ambiente inteiro de build não representa o conteúdo distribuído.

## Microsoft VC runtime

A cadeia pública encontrada tem três partes:

1. O [aviso da PSF para o build Windows, no tag v3.14.10](https://raw.githubusercontent.com/python/cpython/v3.14.10/PC/crtlicense.txt), explica o Microsoft Distributable Code usado pelo interpretador e impõe condições à redistribuição. O texto integral está pinado em `scripts/release_licenses/python-windows-crtlicense.txt`, SHA-256 `3c71b3ae243121f6f227374cd1ef7c59ed07b1969b330d0e947f91a3a1b3fd73`.
2. A seção 4 dos [termos do Visual Studio Community 2022](https://visualstudio.microsoft.com/license-terms/vs2022-ga-community/) permite a distribuição do código listado e contempla distribuidores dos aplicativos. Exige funcionalidade primária e termos protetores para os destinatários. O DOCX oficial consultado tem SHA-256 `41a207b10c8ab91d0d2f10a854715f73dca54509581692d2fe179aa3ffcb8540`.
3. A [lista REDIST do Visual Studio 2022](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution) identifica os componentes distribuíveis e condiciona a permissão aos termos aplicáveis. A [orientação de redistribuição da Microsoft](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files) também condiciona o direito à licença apropriada.

O aviso da PSF pede preservar os avisos de propriedade, não sugerir endosso da Microsoft, respeitar as plataformas permitidas e não usar o código em programas maliciosos, enganosos ou ilegais. As condições se limitam ao código Microsoft; não mudam as licenças do Ritmo e do Python. O ZIP inclui `Ritmo/_internal/release/VC-RUNTIME-TERMS.txt`, com condições protetoras e o aviso PSF integral. O teste automatizado verifica os bytes desse aviso dentro do ZIP.

O [EULA do runtime instalado separadamente](https://visualstudio.microsoft.com/license-terms/vs2022-cruntime/) é um documento distinto e não foi usado como concessão de redistribuição. Não se deve tratar a existência de DLLs numa instalação local como autorização por si só. O catálogo mantém `NOASSERTION` para VC runtime enquanto não estiver concluída a revisão do candidato concreto, sua origem e as condições aplicáveis. Incluir o aviso satisfaz a necessidade de fornecê-lo; não substitui verificar os demais requisitos da cadeia.

O catálogo PSF exige recibo do instalador autenticado e compara hashes dos arquivos da base instalada no runner. O SPDX oficial da PSF tem hashes de pacotes/fontes, não hashes individuais das DLLs. Essa diferença fica registrada. Os componentes de origem desconhecida continuam visíveis.

## Scanner reproduzível

Use um Python de ferramentas já provisionado, separado do runtime do aplicativo, com `pip-audit==2.10.1` e `cve-bin-tool==3.4`. O script não instala nem resolve dependências. A versão 3.4 foi conferida no wheel e na CLI reais: suporta checkers binários e CSV/SBOM, mas não o parser de metadados Windows PE descrito pela documentação de desenvolvimento mais recente. Os metadados PE são evidência separada do inventário.

```powershell
& <python-ferramentas> scripts/release_scan.py `
  --assets <diretorio-dos-assets-do-build> `
  --out <NOVO-diretorio-de-scan> `
  --commit <SHA-completo> --run-id <run-id> `
  --tools-python <python-ferramentas> --timeout 1800
```

O script primeiro verifica o ZIP e todos os hashes pelo manifesto. Depois extrai exatamente esse ZIP, sem executar o aplicativo. Os requisitos precisam coincidir com as distribuições comprovadas pelo inventário; somente entradas `pacote==versão` são aceitas. São executados:

- `pip-audit` com `--no-deps --disable-pip --strict`, contra os requisitos redistribuídos, usando o serviço PyPI. Não há instalação, resolução transitiva ou correção automática. Dependências ausentes ou ignoradas são falhas de cobertura.
- `cve-bin-tool 3.4` sobre os arquivos extraídos, com checkers binários, atualização solicitada dos dados e JSON2/intermediário como evidência.
- `cve-bin-tool 3.4` sobre `native-components.csv`, usando offline o mesmo banco obtido na etapa anterior. São preservados os identificadores e versões dos componentes conhecidos; o relatório mantém as lacunas.

O perfil/cache dos processos filhos fica dentro do diretório de scan; o scanner não usa o cache pessoal. Não lê uma chave NVD do ambiente. O invólucro de isolamento da versão 3.4 é específico para Windows. Não confundir uma atualização solicitada com garantia de que todas as fontes externas estejam atuais: o JSON2 registra as contagens/fontes e a data observada; o banco recebe seu próprio SHA-256.

Para repetir a parte nativa com um snapshot explícito do mesmo banco:

```powershell
& <python-ferramentas> scripts/release_scan.py `
  --assets <mesmos-assets> --out <OUTRO-diretorio-novo> `
  --commit <mesmo-SHA> --run-id <mesmo-run-id> `
  --tools-python <python-ferramentas> `
  --database <snapshot-cve-bin-tool-3.4-cve.db>
```

O snapshot torna repetível a base consultada; o serviço PyPI continua sendo consultado e pode publicar novos avisos entre execuções. Preserve também `pip-audit.json`, os relatórios JSON2, os logs, as versões das ferramentas e os hashes do relatório anterior para comparar mudanças.

## Interpretação e artefatos

`scan-report.json` associa tudo a commit/run/SHA-256 do ZIP e sempre declara `release_approved=false`. Os códigos de saída são:

| Código | Resultado |
| --- | --- |
| 0 | Scans concluídos sem achados reportados, dentro do escopo conhecido. |
| 1 | Achados que precisam de correção ou disposição documentada. |
| 2 | Falha de ferramenta, rede, formato, timeout, dependência não examinada ou cobertura de execução incompleta. |
| 3 | Sem achados reportados, mas com origem nativa, versão ou identificador de consulta pendente. |

Erros de extração, utilitário ausente, saída inválida e falhas de atualização não viram zero CVEs. As saídas brutas ficam preservadas mesmo quando a execução falha. Ausência de correspondência num checker não prova ausência de biblioteca ou vulnerabilidade. Bibliotecas estáticas dentro de wheels, versões com sufixos de empacotamento e componentes sem CPE exigem revisão própria. O parser não transforma essa revisão em aprovação automática.

No CI, arquive os relatórios `*.json`, logs `*.txt` e `scan-report.json` mesmo após falha. Evite enviar recursivamente todo o diretório de scan: ele contém a cópia extraída e o cache de feeds. Se for necessário guardar o banco para reprodução, publique o snapshot como evidência separada, com hash e controle de tamanho. Nenhum desses caches deve entrar no ZIP do aplicativo.

Referências das ferramentas: [pip-audit](https://github.com/pypa/pip-audit), [cve-bin-tool 3.4 no PyPI](https://pypi.org/project/cve-bin-tool/3.4/), [manual do CVE Binary Tool](https://cve-bin-tool.readthedocs.io/en/latest/MANUAL.html). A CLI instalada pinada é a autoridade sobre as opções efetivamente usadas nesta execução.
