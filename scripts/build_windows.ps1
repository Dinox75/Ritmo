param(
    [switch]$Install,
    [switch]$SkipShortcut,
    [switch]$SkipBrowserQA,
    [ValidateSet('preview', 'full')][string]$Profile = 'preview',
    [string]$Python = $env:RITMO_BUILD_PYTHON,
    [string]$Venv = $env:RITMO_BUILD_VENV
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $projectRoot
if ($Install -and (Get-Process Ritmo -ErrorAction SilentlyContinue)) { throw 'Feche o Ritmo antes de atualizar o executável.' }
$version = if ($Profile -eq 'preview') { '3.14' } else { '3.11' }
if (-not $Venv) { $Venv = Join-Path $projectRoot $(if ($Profile -eq 'preview') { '.previewvenv' } else { '.buildvenv' }) }
$Venv = [System.IO.Path]::GetFullPath($Venv)
$buildPython = Join-Path $Venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $buildPython)) {
    if ($Python) { & $Python -m venv $Venv } else { & py "-$version" -m venv $Venv }
    if ($LASTEXITCODE -ne 0) { throw "Python $version não disponível para o build $Profile." }
}
$python = $buildPython
$actualVersion = & $python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
if ($LASTEXITCODE -ne 0 -or $actualVersion.Trim() -ne $version) {
    throw "O perfil $Profile exige Python $version; ambiente selecionado: $actualVersion. Use outro -Venv."
}
$requirements = if ($Profile -eq 'preview') { @('-r', 'requirements-preview.txt') } else { @('-r', 'requirements-desktop.txt', '-r', 'requirements-windows.txt') }
if (-not $SkipBrowserQA) { $requirements += @('-r', 'requirements-qa.txt') }
& $python -m pip install --no-index --disable-pip-version-check @requirements
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install --disable-pip-version-check @requirements
    if ($LASTEXITCODE -ne 0) { throw 'Instalação das dependências falhou.' }
}
& $python scripts/make_icon.py
if ($LASTEXITCODE -ne 0) { throw 'Geração do ícone falhou.' }
$localRoot = (Resolve-Path -LiteralPath $env:LOCALAPPDATA).Path
$portableHome = Split-Path -Parent $projectRoot
$portableLayout = (Split-Path -Leaf $projectRoot) -in @('Codigo', 'Repositorio') -and
    (Test-Path -LiteralPath (Join-Path $portableHome 'Dados')) -and
    (Test-Path -LiteralPath (Join-Path $portableHome 'Modelos'))
$scratchRoot = if ($env:RITMO_BUILD_ROOT) { [System.IO.Path]::GetFullPath($env:RITMO_BUILD_ROOT) } else { Join-Path $projectRoot 'build' }
New-Item -ItemType Directory -Path $scratchRoot -Force | Out-Null
$scratchRoot = (Resolve-Path -LiteralPath $scratchRoot).Path
$env:TEMP = Join-Path $scratchRoot 'RitmoTemp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
$packageRoot = if ($portableLayout) { Join-Path $portableHome 'Aplicativo' } else { Join-Path $localRoot 'RitmoApp' }
$previousRoot = if ($portableLayout) { Join-Path $portableHome 'Versoes anteriores' } else { $localRoot }
$buildId = (Get-Date -Format 'yyyyMMddHHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 6)
$stageRoot = Join-Path $scratchRoot "RitmoStage-$buildId"
$workRoot = Join-Path $scratchRoot $(if ($Profile -eq 'preview') { 'RitmoBuild-preview' } else { 'RitmoBuild' })
$env:RITMO_BUILD_PROFILE = $Profile
& $python -m PyInstaller --noconfirm --distpath $stageRoot --workpath $workRoot Ritmo.spec
if ($LASTEXITCODE -ne 0) { throw 'Empacotamento falhou.' }

$exe = Join-Path $stageRoot 'Ritmo\Ritmo.exe'
$report = Join-Path $stageRoot 'ritmo-smoke.json'
& $python scripts/smoke_windows.py $exe $report
if ($LASTEXITCODE -ne 0) { throw 'Executável falhou no teste de inicialização.' }
if (-not (Test-Path -LiteralPath $report)) { throw 'Executável não gerou o relatório de inicialização.' }
$result = Get-Content -LiteralPath $report -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $result.ready) { throw "Executável não iniciou: $($result.error)" }
$listener = Get-NetTCPConnection -LocalPort $result.port -State Listen -ErrorAction SilentlyContinue
if ($listener) { throw "A porta $($result.port) permaneceu aberta após o teste." }
if (-not $SkipBrowserQA) {
    & $python scripts/qa_packaged_windows.py $exe
    if ($LASTEXITCODE -ne 0) { throw 'Executável falhou no fluxo completo com dados temporários.' }
}

if (-not $Install) {
    Write-Output "Pacote validado ($Profile): $exe"
    Write-Output "Relatório: $report"
    return
}

# O caminho do checkout só é necessário para a migração da instalação explícita.
$pointer = Join-Path (Split-Path -Parent $exe) 'source_checkout.txt'
[System.IO.File]::WriteAllText($pointer, $projectRoot, (New-Object System.Text.UTF8Encoding($false)))
New-Item -ItemType Directory -Path $previousRoot -Force | Out-Null
$previousRoot = (Resolve-Path -LiteralPath $previousRoot).Path
# A instalação atual só é movida depois que o pacote novo passou pelos testes.
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null
$packageRoot = (Resolve-Path -LiteralPath $packageRoot).Path
$stageRoot = (Resolve-Path -LiteralPath $stageRoot).Path
$stageFolder = Join-Path $stageRoot 'Ritmo'
$installed = Join-Path $packageRoot 'Ritmo'
$previous = Join-Path $previousRoot "RitmoAppPrevious-$buildId"
$failed = Join-Path $scratchRoot "RitmoAppFailed-$buildId"
if ((Split-Path -Parent (Resolve-Path -LiteralPath $stageFolder).Path) -ne $stageRoot -or
    (Split-Path -Parent $installed) -ne $packageRoot -or
    (Split-Path -Parent $previous) -ne $previousRoot -or
    (Test-Path -LiteralPath $previous)) { throw 'Caminho de instalação fora das pastas esperadas.' }
if (Test-Path -LiteralPath $installed) {
    if ((Split-Path -Parent (Resolve-Path -LiteralPath $installed).Path) -ne $packageRoot) {
        throw 'Instalação existente fora da pasta esperada.'
    }
    Move-Item -LiteralPath $installed -Destination $previous
}
try {
    Move-Item -LiteralPath $stageFolder -Destination $installed
} catch {
    if (Test-Path -LiteralPath $installed) { Move-Item -LiteralPath $installed -Destination $failed }
    if (Test-Path -LiteralPath $previous) { Move-Item -LiteralPath $previous -Destination $installed }
    throw
}
$exe = Join-Path $installed 'Ritmo.exe'

if (-not $SkipShortcut) {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $link = Join-Path $desktop 'Ritmo.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($link)
    $shortcut.TargetPath = $exe
    $shortcut.WorkingDirectory = Split-Path -Parent $exe
    $shortcut.IconLocation = "$exe,0"
    $shortcut.Description = 'Ritmo · estudo pessoal'
    $shortcut.Save()
    Write-Output "Atalho criado: $link"
}
Write-Output "Executável pronto: $exe"
if (Test-Path -LiteralPath $previous) { Write-Output "Instalação anterior preservada: $previous" }
