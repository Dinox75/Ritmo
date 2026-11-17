# Distribuição: GitHub Releases e Packages

**Releases** é a página para pessoas que querem baixar o pacote Windows. **Packages** recebe o mesmo ZIP como artefato OCI em `ghcr.io/dinox75/ritmo-windows:<tag>`, destinado a distribuição automatizada. O artefato contém um programa Windows; não se executa com `docker run`.

O [workflow de distribuição](../.github/workflows/distribute-windows.yml) é manual. Ele só estará disponível para disparo depois de integrado à branch padrão. No [GitHub Actions](https://github.com/Dinox75/Ritmo/actions):

1. Selecione **Ritmo • distribuição Windows**, branch `main`, e a primeira tag de prévia, por exemplo `v0.1.0-preview.1`. Mantenha **publish** desmarcado para gerar e testar sem publicar.
2. Baixe o artefato `ritmo-distribuicao`, confira o ZIP, o SHA-256, a lista de dependências e o commit do build. Extraia em outra máquina Windows de teste e mantenha `Ritmo.exe` e `_internal` juntos.
3. Após resolver os bloqueios de [auditoria](qa/auditoria-2026-11-17.md), revisar dependências/licenças e validar o pacote, dispare sobre o commit aprovado com **publish** marcado e informe seu SHA completo em **reviewed_sha**. O workflow gera um novo pacote, testa-o, cria um Release em rascunho, publica o ZIP no GHCR, compara o digest da camada OCI com o SHA-256 local e só então publica o Release como prévia. O SHA de um build anterior não vale para o novo ZIP: cada execução emite o próprio manifesto.
4. Confira [Releases](https://github.com/Dinox75/Ritmo/releases) e [Packages](https://github.com/users/Dinox75/packages?repo_name=Ritmo). No GHCR, confirme que a visibilidade corresponde ao público pretendido. A primeira publicação pode ficar privada; alterar a visibilidade é uma decisão separada. Não republique bytes diferentes sob a mesma versão.

Para baixar da GHCR, instale [ORAS](https://oras.land/docs/):

```powershell
oras pull ghcr.io/dinox75/ritmo-windows:v0.1.0-preview.1
Get-FileHash .\Ritmo-v0.1.0-preview.1-windows-x64.zip -Algorithm SHA256
```

Use a tag efetivamente publicada. Um pacote privado requer autenticação com acesso de leitura. Compare com `SHA256SUMS.txt`. O ZIP inclui apenas o aplicativo e as dependências; pesos, banco pessoal e instalação ficam fora. O pacote não tem assinatura digital nesta fase.

Se uma publicação parcial deixar um rascunho ou referência OCI, confira seu hash e status antes de retomar. O próximo disparo não deve sobrescrever a tag existente. Confira também cotas de Actions/Packages e tamanho do pacote antes de ativar distribuições repetidas.

Referências: [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases), [Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry), [ORAS em registries remotos](https://oras.land/docs/how_to_guides/remote_registries/).
