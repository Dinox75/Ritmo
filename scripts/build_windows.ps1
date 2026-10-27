param([switch]$SkipShortcut, [switch]$SkipBrowserQA)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $projectRoot
if (Get-Process Ritmo -ErrorAction SilentlyContinue) { throw 'Feche o Ritmo antes de atualizar o executável.' }
$python = Join-Path $projectRoot '.buildvenv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    py -3.11 -m venv (Join-Path $projectRoot '.buildvenv')
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 não disponível para o build.' }
}
& $python -m pip install --no-index --disable-pip-version-check --no-cache-dir -r requirements-desktop.txt -r requirements-windows.txt -r requirements-qa.txt
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install --disable-pip-version-check --no-cache-dir -r requirements-desktop.txt -r requirements-windows.txt -r requirements-qa.txt
    if ($LASTEXITCODE -ne 0) { throw 'Instalação das dependências falhou.' }
}
& $python scripts/make_icon.py
if ($LASTEXITCODE -ne 0) { throw 'Geração do ícone falhou.' }
$localRoot = (Resolve-Path -LiteralPath $env:LOCALAPPDATA).Path
$portableHome = Split-Path -Parent $projectRoot
$portableLayout = (Split-Path -Leaf $projectRoot) -eq 'Codigo' -and
    (Test-Path -LiteralPath (Join-Path $portableHome 'Dados')) -and
    (Test-Path -LiteralPath (Join-Path $portableHome 'Modelos'))
$scratchRoot = if ($env:RITMO_BUILD_ROOT) { [System.IO.Path]::GetFullPath($env:RITMO_BUILD_ROOT) } elseif ($portableLayout) { Join-Path $portableHome 'Build' } else { $localRoot }
New-Item -ItemType Directory -Path $scratchRoot -Force | Out-Null
$scratchRoot = (Resolve-Path -LiteralPath $scratchRoot).Path
$env:TEMP = Join-Path $scratchRoot 'RitmoTemp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
$packageRoot = if ($portableLayout) { Join-Path $portableHome 'Aplicativo' } else { Join-Path $localRoot 'RitmoApp' }
$previousRoot = if ($portableLayout) { Join-Path $portableHome 'Versoes anteriores' } else { $localRoot }
New-Item -ItemType Directory -Path $previousRoot -Force | Out-Null
$previousRoot = (Resolve-Path -LiteralPath $previousRoot).Path
$buildId = (Get-Date -Format 'yyyyMMddHHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 6)
$stageRoot = Join-Path $scratchRoot "RitmoStage-$buildId"
$workRoot = Join-Path $scratchRoot 'RitmoBuild'
& $python -m PyInstaller --noconfirm --distpath $stageRoot --workpath $workRoot Ritmo.spec
if ($LASTEXITCODE -ne 0) { throw 'Empacotamento falhou.' }

$exe = Join-Path $stageRoot 'Ritmo\Ritmo.exe'
$pointer = Join-Path (Split-Path -Parent $exe) 'source_checkout.txt'
[System.IO.File]::WriteAllText($pointer, $projectRoot, (New-Object System.Text.UTF8Encoding($false)))
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
