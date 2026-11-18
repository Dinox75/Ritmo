# Only for disposable CI runners. Never called by the local build/install script.
$ErrorActionPreference = 'Stop'
if (-not $env:GITHUB_ACTIONS) { throw 'Este provisionamento so e permitido no runner descartavel do CI.' }
$runtime = Join-Path ${env:ProgramFiles(x86)} 'Microsoft\EdgeWebView\Application'
if (-not (Test-Path -LiteralPath $runtime)) {
    $installer = Join-Path $env:RUNNER_TEMP 'MicrosoftEdgeWebview2Setup.exe'
    Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $installer
    $signature = Get-AuthenticodeSignature -LiteralPath $installer
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
        throw 'Assinatura Microsoft do instalador WebView2 nao conferiu.'
    }
    $result = Start-Process -FilePath $installer -ArgumentList '/silent','/install' -Wait -PassThru -WindowStyle Hidden
    if ($result.ExitCode -ne 0) { throw "Instalacao WebView2 falhou: $($result.ExitCode)" }
}
if (-not (Test-Path -LiteralPath $runtime)) { throw 'WebView2 nao ficou disponivel no runner.' }
Get-ChildItem -LiteralPath $runtime -Directory | Select-Object Name
