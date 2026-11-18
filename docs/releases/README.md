# Versionamento e etapas de release

O [changelog](../../CHANGELOG.md) lista marcos em ordem de evolução. A [página de Releases](https://github.com/Dinox75/Ritmo/releases) mostra o que foi publicado. Um relatório de teste ou um item do roteiro, sozinho, não é uma release.

| Canal | Formato no Ritmo | Quando usar |
| --- | --- | --- |
| Marco histórico | `v0.1.0-alpha.N.source` | Arquivo do código de um marco real, sem binário. |
| Prévia de código | `v0.1.0-preview.N-source` | Código verificável enquanto a distribuição para instalação ainda está em revisão. Arquivos automáticos Source code do GitHub. |
| Prévia Windows | `v0.1.0-preview.N` | Primeiros pacotes x64 liberados pelo processo de QA e revisão. |
| Candidata/estável | `v0.1.0-rc.N` / `v0.1.0` | Convenção reservada para uma fase posterior. O workflow atual de Windows é de prévia; não aceita automaticamente tags RC ou estáveis. |

Usamos a convenção [SemVer](https://semver.org/lang/pt-BR/): durante `0.x` a estabilidade ainda não é prometida. Aumente o patch para correções compatíveis, a minor para entregas novas compatíveis e reserve a major para mudanças incompatíveis depois da API estável. Para uma nova rodada da mesma prévia, aumente `N`. Não mova tags, substitua arquivos de uma versão publicada nem dê um número novo a uma versão apenas para preencher a página.

1. **Definir escopo.** Escolher versão, canal, mudanças para o usuário e limitações. Preparar notas em português, com evidências específicas para a versão.
2. **Construir.** Fixar commit e identificar ZIP, manifesto, SBOM e hashes. A promoção não recompila.
3. **Validar.** Rodar build, QA nativo e funcional em Windows limpo e revisão de vulnerabilidades/licenças. As evidências precisam corresponder ao mesmo ZIP.
4. **Promover.** Ensaio sem publicar; depois Releases e Packages pelos [workflows de Windows](../distribuicao.md). Conferir os downloads nos dois destinos.
5. **Acompanhar.** Registrar problemas conhecidos e correções. Se mudar o pacote após publicar, gerar nova versão e repetir as verificações pertinentes.

Para releases de **código-fonte**, as notas ficam em arquivos cujo nome é a tag, e o catálogo `catalog.json` fixa o commit de cada marco. O [workflow do histórico](../../.github/workflows/source-release-history.yml) lê o catálogo na `main` e só pode publicar pré-releases sem binários. Mudanças no catálogo ou nas notas versionadas acionam a sincronização; o fluxo também pode ser executado manualmente na `main`. Ele não tem acesso de escrita ao registro de pacotes, não move tags e rejeita entradas que colidam com releases que tenham assets.

Cada nota deve explicar: etapa, mudanças principais, versão/commit, validação e limites, como baixar e comparação com o marco anterior. O ZIP/instalador Windows deve vir apenas pelo fluxo próprio de distribuição.
