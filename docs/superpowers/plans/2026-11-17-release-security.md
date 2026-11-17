# Segurança e primeira prévia — plano e aceite prévio

> Execução: superpowers:executing-plans, TDD e revisão antes do merge.

**Goal:** corrigir a auditoria antes de distribuir um ZIP Windows completo.
**Architecture:** sessão efêmera por processo, cookie HttpOnly/SameSite=Strict após
troca de código de uso único, validação integral do motor a partir de ZIPs com
hash fixado no catálogo, backup do caminho efetivo e promoção sem rebuild.
**Tech Stack:** Python 3.11, HTTP loopback, SQLite, WebView2, PyInstaller, Actions/ORAS.
**Spec:** pedido anexado e docs/qa/auditoria-2026-11-17.md.

## Restrições
- Sem -Install, treino, alteração de pesos/instalação/atalhos/dados pessoais.
- PR #11 em rascunho enquanto houver bloqueios; não publicar nem integrar antes dos gates.
- Manter brutos/prova e relatórios antigos; credenciais nunca em URL/log/estático/artefato.
- Decisões técnicas rotineiras delegadas pelo pedido; implementação no worktree isolado.

## Matriz de aceite registrada antes dos novos testes
| ID / referência | Risco | Correção | Teste necessário / condição para passar |
| --- | --- | --- | --- |
| SEG-01 / ASVS5, ISO27001 | Cliente local lê/altera/apaga sem sessão | Credencial aleatória por instância; bootstrap de uso único; Host/Origin; confirmação nativa separada | Sem/errada credencial e origem externa: 401/403 em leitura/mutação/erase com callback inofensivo; cookie legítimo funciona; cancelar não apaga; WebView2 e navegador autorizado funcionam; encerramento invalida sessão |
| SEG-02 / ASVS, ISO25010 | PE/DLL substituída ou redirecionada | Hashes embarcados derivados de ZIPs verificados, caminho fixo, recusa de redirecionamentos | EXE alterado, DLL ausente, PE extra e reparse/symlink recusados antes de Popen; instalação válida inicia/para; versão antiga sem confiança automática |
| REC-01 / ISO25010, ISO26514 | Backup omite preferências | Passar caminho efetivo de config | Dev e frozen: restaurar em pasta nova, integrity_check ok, hashes originais/preferências e sessão usável |
| SEG-04 / ISO25010 | Parser PDF usa tempo/memória ilimitados | Medição sintética e limites proporcionais | Registrar tempo/memória/concorrência/recuperação; diferenciar risco observado de exploração não demonstrada |
| DIST-01 / ISO27001, ISO29110 | Binários/licenças/CVEs desconhecidos | Inventário por arquivo, SBOM, avisos, scan datado e gate | Sem vulnerabilidade prioritária sem tratamento; nativos e limites do scan explícitos; EXE/ZIP íntegros, nenhum segredo/banco/peso/caminho de checkout |
| WIN / ISO25010, ISO9241-11, WCAG2.2 | Falha de uso/compatibilidade | QA isolado do ZIP exato | Suíte/smoke/fluxos; 390/1366/1920; foco/teclado/contraste claro+escuro; porta liberada; Windows limpo ou VM real antes da publicação |
| PUB / ISO29110, ISO26514 | Publica bytes diferentes ou sobrescreve versão | Separar build de promoção, SHA explícito, idempotência | Dry-run antes de publicar; tag no commit do build; baixar Releases+OCI e confrontar SHA; associação/visibilidade verificadas |

As normas são referências de engenharia, não certificação/conformidade integral.
ISO25019/ISO9241-11 exigem contexto real: testes de software não provam usabilidade
com estudantes nem aprendizagem. UX-01 permanece fora de uma alegação de eficácia.

## Etapas
- [ ] Registrar estado/tag/releases/packages/execuções e disponibilidade de Windows limpo.
- [ ] SEG-01: regressões negativas vermelhas, sessão e confirmação nativa, testes verdes.
- [ ] SEG-02: regressões e catálogo confiável, motor legítimo Windows.
- [ ] REC-01 e avaliação PDF sintética com restauração isolada.
- [ ] SBOM/avisos/scan e separar build/promoção sem reconstrução.
- [ ] Suíte, pacote sem instalar, ZIP extraído e QA isolado/VM com evidências.
- [ ] Revisão, PR atualizada; publicar/integrar somente se todos os gates passarem.

## Foco da revisão
Bootstrap não pode autorizar cliente anônimo automaticamente; apagar precisa de
confirmação fora do HTTP; credencial não pode ir ao relatório; DLL search precisa
considerar caminhos/redirecionamentos; aprovação do SHA não pode autorizar rebuild.
