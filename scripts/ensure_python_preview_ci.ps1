# This toolchain is provisioned only inside a disposable Actions runner.
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or -not $env:RUNNER_TEMP) { throw 'Disposable CI runner required.' }
$root = [System.IO.Path]::GetFullPath((Join-Path $env:RUNNER_TEMP 'ritmo-python-3.14.10'))
$runnerRoot = [System.IO.Path]::GetFullPath($env:RUNNER_TEMP)
if ((Split-Path -Parent $root) -ne $runnerRoot) { throw 'Toolchain outside runner temporary directory.' }
New-Item -ItemType Directory -Path $root -Force | Out-Null
$installer = Join-Path $root 'python-3.14.10-amd64.exe'
$url = 'https://www.python.org/ftp/python/3.14.10/python-3.14.10-amd64.exe'
$expected = '92480239264744fe0386a1bd8275786fefa126e3129e56a68e22b52c73329965'
Invoke-WebRequest -Uri $url -OutFile $installer
if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'PSF installer checksum mismatch.' }
$signature = Get-AuthenticodeSignature -LiteralPath $installer
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') { throw 'PSF signature mismatch.' }
$runtime = Join-Path $root 'Runtime'
$result = Start-Process -FilePath $installer -ArgumentList @('/quiet','InstallAllUsers=0',('TargetDir="'+$runtime+'"'),'PrependPath=0','AssociateFiles=0','Include_launcher=0','Include_test=0','Shortcuts=0') -Wait -PassThru -WindowStyle Hidden
if ($result.ExitCode -ne 0) { throw "PSF installer failed: $($result.ExitCode)" }
$python = Join-Path $runtime 'python.exe'
& $python -c "import sys; assert sys.version_info[:3]==(3,14,10); print(sys.version)"
if ($LASTEXITCODE -ne 0) { throw 'Unexpected Python toolchain.' }
$receipt = Join-Path $root 'installer-receipt.json'
$sbom = Join-Path $root 'python-3.14.10-amd64.exe.spdx.json'
Invoke-WebRequest -Uri ($url + '.spdx.json') -OutFile $sbom
if ((Get-FileHash -LiteralPath $sbom -Algorithm SHA256).Hash.ToLowerInvariant() -ne '631d10bf095ea6855a0d20fa0553d2de6f68288fc5b5ca943f1cb74d8dcc0b5c') { throw 'PSF SPDX checksum mismatch.' }
@{installer_sha256=$expected;signature_status='Valid';signer_subject=$signature.SignerCertificate.Subject;source_url=$url;version='3.14.10'} | ConvertTo-Json | Set-Content -LiteralPath $receipt -Encoding utf8
"RITMO_BUILD_PYTHON=$python" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
"RITMO_PYTHON_RECEIPT=$receipt" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
"RITMO_PYTHON_SBOM=$sbom" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
Write-Output 'Verified PSF Python 3.14.10 prepared in the disposable runner.'
