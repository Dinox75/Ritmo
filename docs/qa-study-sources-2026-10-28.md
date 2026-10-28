# Integração do espaço de estudo, referências e pesquisa opcional — 28/10/2026

Branch local `feat/ritmo-study-sources`, derivada de `feat/ritmo-study-atmosphere` (`16c3bb1`). As alterações das PRs em rascunho #5 (`a6a95f0`) e #6 (`3e0f71b`) foram incorporadas por cherry-pick. O único conflito foi o nome do cache do service worker, atualizado para `ritmo-shell-v15` após as mudanças desta rodada. A proposta de logo da PR #4 não entrou. Nenhum merge ou release foi feito.

## Resultado verificado

| Ensaio | Resultado |
| --- | --- |
| Suíte completa | 33 testes aprovados. Inclui consulta externa sem confirmação, fontes contraditórias e indisponíveis, conteúdo hostil, persistência de atribuição e fluxo de navegador. |
| `smoke_windows.py` no pacote novo | Inicialização e fechamento aprovados; porta liberada. |
| `qa_packaged_windows.py` no pacote novo | Pausa/reabertura, materiais, notas e backup com dados temporários aprovados. |
| `qa_study_atmosphere_packaged.py` | Janela WebView2, cronômetro, pausa/retomada, chuva, ruído marrom, WAV, volume, lembretes, conclusão e reabertura aprovados. Em Estudar e Configurações, rolagem a 85% manteve navegação fixa em 390, 1366 e 1920 px; sem rolagem horizontal. Capturas foram examinadas. |
| `qa_study_sources_packaged.py` | Atalho por teclado para pausa/retomada e referência; destaque do excerto único; aviso para duas correspondências e trecho ausente; busca, seleção e nota após abrir referência; nenhuma consulta enviada antes do clique; pesquisa real retornou cinco resultados com links e data de acesso; porta liberada. |
| Qwen3 4B local, caso sintético | 29,44 s. Identificou a regra do material e a contradição com uma fonte **simulada**. Não atribuiu verificação à fonte. A conclusão final recomendou seguir o material com mais certeza que a comparação sustenta; a qualidade da comparação continua experimental. |
| Backup e migração pessoal | Backup SQLite consistente criado em `Dados/backups`. Em cópia temporária, migração 7 → 8 preservou contagens de todas as tabelas existentes, estados das sessões e `integrity_check=ok`. No banco pessoal havia cinco sessões concluídas e nenhuma em andamento. |
| Instalação | A pasta anterior foi guardada em `Versoes anteriores/RitmoAppPrevious-20261028200527`. O banco e a configuração pessoais mantiveram seus hashes durante a troca. Smoke e ensaio de referências/pesquisa passaram também no caminho instalado, com dados temporários. O atalho existente aponta para o novo executável. |

O executável instalado tem SHA-256 `0BBF4346BAB2ECD8E1237938C20BEDBFFC6A122F6B715521F94A43B3E35A926C`. O CSS empacotado `atmosphere.css` tem SHA-256 `CBEB145404437825AD3F0D36355CB7CB5B6FB306412FDAFDB56BC89308B5CDFC`; o hash do executável sozinho não identifica alterações nos recursos externos da pasta PyInstaller. O pacote anterior tinha executável SHA-256 `0326451C191C71E1B137BDAB154F40FAE52A2A8321E4B6B1697B4E17A14FCBAF`.

## Comandos principais

Executados a partir de `A:\Projetos & Estudos\Ritmo\Repositorio` com `.venv` existente:

```powershell
git status --short --branch
git cherry-pick a6a95f0265d28bab2cf17e96a7f31f1e5f0e0f33
git cherry-pick 3e0f71b1fde909d0a66746a5fdcdfbde383dca1e
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath 'A:\Projetos & Estudos\Ritmo\BuildValidation\study-sources-20261028\dist' --workpath 'A:\Projetos & Estudos\Ritmo\BuildValidation\study-sources-20261028\work' Ritmo.spec
$exe = 'A:\Projetos & Estudos\Ritmo\BuildValidation\study-sources-20261028\dist\Ritmo\Ritmo.exe'
.\.venv\Scripts\python.exe scripts\smoke_windows.py $exe 'A:\Projetos & Estudos\Ritmo\BuildValidation\study-sources-20261028\smoke-final.json'
.\.venv\Scripts\python.exe scripts\qa_packaged_windows.py $exe
.\.venv\Scripts\python.exe scripts\qa_study_atmosphere_packaged.py $exe 'A:\Projetos & Estudos\Ritmo\BuildValidation\study-sources-20261028\screens-final' 'A:\Projetos & Estudos\Ritmo\BuildValidation\study-sources-20261028\atmosphere-final.json'
.\.venv\Scripts\python.exe scripts\qa_study_sources_packaged.py $exe 'A:\Projetos & Estudos\Ritmo\BuildValidation\study-sources-20261028\sources.json'
.\.venv\Scripts\python.exe scripts\qa_real_sources.py 'A:\Projetos & Estudos\Ritmo\Modelos\RitmoModels' 'A:\Projetos & Estudos\Ritmo\BuildValidation\study-sources-20261028\real-sources.json'
.\.venv\Scripts\python.exe scripts\verify_backup_migration.py '<backup em Dados/backups>' 'A:\Projetos & Estudos\Ritmo\Dados\ritmo.db'
```

A troca foi feita com `Move-Item` no PowerShell, após verificar processos, caminhos absolutos, backup e hashes do pacote anterior e do novo. O pacote foi ensaiado novamente no caminho instalado. Arquivos de teste, capturas e o caso real sintético ficam em `BuildValidation/study-sources-20261028`, fora do Git.

## Alcance e limites

A pesquisa só envia a consulta revisada, por clique explícito, à Wikipédia em português; o modelo e os materiais continuam locais. São usados até cinco excertos introdutórios e até três podem ser escolhidos para a próxima resposta. Links, fonte, licença informada e data de acesso ficam guardados na resposta; uma data de acesso não é uma data de publicação. Não há busca geral na Web nem confirmação automática de fatos atuais de faculdade ou trabalho. As páginas podem errar ou conter instruções hostis; o tutor recebe esses textos como dados não confiáveis. O ensaio com Qwen3 mostra que essa separação técnica funciona, mas a qualidade da resposta ainda exige revisão humana.

A API da Wikimedia não exige pagamento nem chave neste uso; requer identificação por User-Agent e obedece a [limites variáveis](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits). A [política de reutilização](https://www.mediawiki.org/wiki/Wikimedia_APIs/Content_reuse) exige verificar licença e atribuição por página. A [Brave Search API](https://api-dashboard.search.brave.com/documentation/pricing) foi considerada para busca Web ampla, mas exige conta/configuração de cobrança e informa US$ 5 por 1.000 consultas, com crédito mensal; não foi integrada. O player foi testado no WebView2, mas nesta rodada não houve nova medição acústica física; a medição anterior está em [qa-windows-pr3.md](qa-windows-pr3.md). O pacote é local, não assinado e não foi publicado como release.
