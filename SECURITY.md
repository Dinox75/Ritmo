# Segurança do Ritmo

Esta prévia está em preparação; o aplicativo Windows ainda não tem assinatura
digital. SHA-256 permite comparar os bytes baixados, mas não substitui assinatura
digital nem protege um computador já comprometido.

Reporte vulnerabilidades em privado pelo botão **Report a vulnerability** na
[página de segurança](https://github.com/Dinox75/Ritmo/security). Não inclua banco,
materiais, notas, conversas, credenciais ou pesos. Informe versão/commit, Windows,
passos com dados sintéticos, resultado esperado/observado e impacto demonstrado.
Se o botão não estiver disponível, abra uma issue apenas solicitando contato
privado, sem publicar detalhes exploráveis ou dados pessoais.

## Fronteira de proteção

A API escuta apenas em 127.0.0.1 e exige uma credencial efêmera para rotas de
dados/alteração. O status público informa somente prontidão, identificação opaca
da instância e se é pacote. Host e Origin também são validados.
O WebView2 recebe autorização na memória da janela nativa. O navegador exige o
código de uso único exibido pelo lançador/terminal (cinco minutos). O cookie é
HttpOnly e SameSite=Strict; reiniciar o servidor gera outra credencial. Não coloque
o código em comandos, URLs, arquivos, logs ou relatórios. Não habilite depuração
remota de WebView2 no uso pessoal; o QA usa CDP só em instâncias temporárias próprias.

Isso bloqueia clientes HTTP sem credencial, inclusive processos locais. Não
protege de processos que já podem ler arquivos, memória ou perfil do usuário,
modificar o aplicativo ou controlar a janela. Cookies HTTP de loopback não
substituem isolamento do sistema contra outros programas locais. Restrinja
permissões e considere criptografia do disco. Não há criptografia própria do banco/ZIP.

Apagar dados exige também confirmação nativa; enviar APAGAR por HTTP apenas
solicita o diálogo. Cancelar mantém aplicativo e dados. O escopo inclui backups
internos: guarde antes uma cópia externa. Modelos e cópias externas são preservados.

O motor é verificado contra catálogo embarcado derivado de arquivos upstream
com hashes fixados; recibos na pasta de modelos não estabelecem confiança.
Instalações antigas passam pela mesma verificação. Em caso de erro, escolha
uma pasta nova de modelos em Configurações para reinstalar. O instalador recusa
um runtime existente adulterado, sem substituí-lo automaticamente. Não execute
o arquivo suspeito. O controle não elimina corrida contra escrita simultânea
nem protege o catálogo se o próprio aplicativo for modificado.

Materiais, fontes externas e respostas do tutor são dados não confiáveis. O
modelo não recebe ferramentas de comandos/instalação/publicação. Downloads
dependem de ação explícita; pesquisa só envia a consulta revisada.
