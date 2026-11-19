# Ritmo web Implementation Plan

Goal: publicar piloto privado com autenticação gerenciada e persistência real.
Architecture: Worker independente + D1/R2, conforme architecture.md. Preservar desktop e DIST-01.

- [ ] Escrever testes de autorização, tempo e concorrência antes do serviço; demonstrar falha inicial.
- [ ] Implementar schema/migração, API de matérias/sessões/notas, cotas e validação.
- [ ] Testar e implementar extração limitada TXT/DOCX/PDF e acesso privado.
- [ ] Implementar backup/restore e testar em instância distinta, incluindo falhas e sessão aberta.
- [ ] Adaptar UI para toque, rascunhos, conflitos, dois temas e áudio opcional.
- [ ] Executar integração, segurança e UI responsiva; registrar resultados e limitações.
- [ ] Empacotar via helper Sites, publicar privado, verificar URL e redeploy/persistência quando permitido pela autenticação real.
- [ ] Documentar acesso, limites, deploy/rollback; abrir PR, verificar regras/checks e integrar se critérios cumpridos.

Revisão: atenção a headers de identidade forjados fora do dispatch, timestamps do cliente, race entre quota e upload, replay com outro corpo, referências a material de outra conta, restauração de backup malicioso e mensagem de sucesso antes do commit.
