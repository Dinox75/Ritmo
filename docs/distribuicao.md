# Distribuição Windows: build, QA e promoção dos mesmos bytes

O [build](../.github/workflows/distribute-windows.yml) só produz evidências. Ele não tem permissão de escrita em Releases/Packages e nunca publica. Em pull requests e execução manual, compila sem `-Install`, testa e arquiva `ritmo-distribuicao`. Um segundo job usa outro runner `windows-2025`, baixa o ZIP já produzido, verifica todos os hashes, extrai para uma pasta nova e executa smoke e QA essencial usando o runtime do EXE. Instala somente ferramentas de QA no Python do runner. Isso é isolamento de runner e dados; não é uma instalação Windows sem componentes pré-instalados de GitHub Actions.

O ZIP contém `Ritmo/Ritmo.exe` e toda a pasta `Ritmo/_internal`. Distribuir só o EXE quebra o aplicativo. O empacotador rejeita nomes privados/perigosos, bancos, logs, ponteiros de checkout, formatos de pesos e caminhos do checkout/perfil embutidos nos arquivos. As verificações não substituem a inspeção do inventário e dos avisos: nenhum banco, preferências pessoais, credencial ou peso de IA deve entrar no ZIP.

Cada build fornece:

- `build-info.json`: commit completo, run ID, versão, SHA-256 distintos do ZIP e do EXE, tamanho/hash de cada arquivo e hashes das evidências.
- `SHA256SUMS.txt`: hashes de todos os arquivos distribuídos como assets.
- `bom.cdx.json`: SBOM CycloneDX 1.6 com cada arquivo redistribuído, inclusive DLL/PYD/EXE, e seu SHA-256.
- `sbom.json`: inventário detalhado, correspondência de bytes e caminhos com RECORD das distribuições Python, proveniência de módulos congelados via TOC do PyInstaller, versões/licenças declaradas, metadados PE disponíveis e binários nativos sem origem/licença resolvida.
- `THIRD-PARTY-NOTICES.txt`: avisos encontrados nas distribuições comprovadamente correspondentes e pendências nativas explícitas.
- `build-dependencies.json`: ambiente de compilação completo, separado do inventário de redistribuição. Um pacote instalado no build não prova sua presença no ZIP; o TOC de compilação permite mapear módulos Python congelados ao RECORD sem publicar caminhos absolutos; correspondências ausentes continuam como não mapeadas, não como prova de dependência exclusiva de build. Essas lacunas ficam explícitas e precisam de revisão.

`license_review=required` não é aprovação. Revise termos das bibliotecas nativas e módulos congelados, acrescente avisos faltantes antes de gerar o candidato final, e execute o scan de vulnerabilidades no ambiente exato do candidato. Não publique com achados de distribuição sem resolução documentada. A auditoria [DIST-01](qa/auditoria-2026-11-17.md) continua aberta enquanto faltarem essas evidências. O pacote ainda não possui assinatura digital; SHA-256 verifica integridade, não identifica o autor como uma assinatura.

## Promover sem recompilar

O [workflow de promoção](../.github/workflows/promote-windows.yml) é separado, manual e executado na `main`. Ele baixa um artefato anterior por **ID e SHA-256 de transporte**, verifica também o digest informado pelo GitHub e os hashes internos. Exige o run bem sucedido do workflow de build manual na main e o artefato `ritmo-clean-windows-qa` do mesmo run, também por ID e digest. O atestado precisa vincular exatamente commit/run/SHA-256 do ZIP e declarar os testes aprovados.

1. Execute o build manual na main com a versão de prévia desejada. Anote run ID, commit completo, ID/digest dos dois artefatos. O build de PR permite validar antes do merge; o candidato publicável exige build manual bem sucedido na main.
2. Revise QA, inventário, licenças/avisos e vulnerabilidades. Informe a identidade responsável em `reviewed_by` e marque `reviews_approved` somente com evidências suficientes. Essa identidade pode ser quem realizou a revisão autorizada; não há exigência adicional de aprovação pessoal do usuário nesta documentação.
3. Execute a promoção com `publish=false`. Ela não cria tags/releases nem envia dados à GHCR. Baixa e verifica todos os bytes e produz `ritmo-promotion-dry-run/dry-run-receipt.json`. Uma licença ou vulnerabilidade ainda pendente impede declarar a revisão aprovada, inclusive para esse ensaio.
4. Revise o recibo e execute novamente com entradas idênticas e `publish=true`, informando `dry_run_artifact` como `ID:SHA256` do artefato do ensaio. O workflow valida que o recibo veio de uma promoção bem sucedida na main e coincide com todos os parâmetros do candidato.
5. A promoção cria/retoma um Release em rascunho, publica o mesmo ZIP e evidências como OCI, baixa pelos dois canais e compara os bytes. Só publica o Release depois de conferir associação do package ao repositório e visibilidade `public`. A tag de código deve apontar diretamente ao commit de origem; tag preexistente divergente impede continuar.

O environment `windows-release` nomeia o destino; suas regras de proteção dependem da configuração real do repositório, não do nome no YAML. O token do job precisa de `contents:write` e `packages:write`; o acesso à API de packages e a associação ao repositório também precisam funcionar. A publicação parcial pode deixar um rascunho ou OCI já enviado. Corrija associação/visibilidade nas configurações do package quando necessário e retome as mesmas entradas: assets e referências existentes só são aceitos se os bytes forem idênticos. O script não usa `--clobber`, não substitui tag e não altera visibilidade automaticamente.

Para conferir localmente um artefato já baixado:

```powershell
python scripts/release_bundle.py verify --out release-assets --commit <SHA-completo> --run-id <run-id>
Get-FileHash release-assets/Ritmo-v0.1.0-preview.1-windows-x64.zip -Algorithm SHA256
```

O mesmo ZIP fica em [Releases](https://github.com/Dinox75/Ritmo/releases) e na GHCR, como `ghcr.io/dinox75/ritmo-windows:<versão>`:

```powershell
oras pull ghcr.io/dinox75/ritmo-windows:v0.1.0-preview.1
Get-FileHash ./Ritmo-v0.1.0-preview.1-windows-x64.zip -Algorithm SHA256
```

É um arquivo Windows em OCI, não uma imagem para `docker run`. Compare com o SHA-256 do ZIP no manifesto. Um package privado exige autenticação; uma publicação destinada ao público permanece bloqueada até visibilidade/associação confirmadas. A execução real desses passos deve constar das evidências antes de afirmar que ambos os canais foram validados.
