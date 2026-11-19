# Ritmo web Implementation Plan

Goal: publicar piloto privado com autenticação gerenciada e persistência real.
Architecture: Worker independente + D1/R2, conforme architecture.md. Preservar desktop e DIST-01.

- [x] Escrever testes de autorização, tempo e concorrência antes do serviço; demonstrar falha inicial.
- [x] Implementar schema/migração, API de matérias/sessões/notas, cotas e validação.
- [x] Testar e implementar extração limitada TXT/DOCX/PDF e acesso privado.
- [x] Implementar backup/restore e testar em instância distinta, incluindo falhas e sessão aberta.
- [x] Adaptar UI para toque, rascunhos, conflitos, dois temas e áudio opcional.
- [x] Executar integração, segurança e UI responsiva; registrar resultados e limitações.
- [x] Empacotar via helper Sites, publicar privado, verificar proteção HTTPS e reaplicação da versão.
- [ ] Validar login real, importação e persistência de registros após redeploy: host de navegador indisponível nesta sessão.
- [x] Documentar acesso, limites, deploy/rollback; abrir PR #13, verificar regras/checks.
- [ ] Integrar após critérios completos: PR em rascunho enquanto falta QA autenticada remota.

Revisão: atenção a headers de identidade forjados fora do dispatch, timestamps do cliente, race entre quota e upload, replay com outro corpo, referências a material de outra conta, restauração de backup malicioso e mensagem de sucesso antes do commit.
