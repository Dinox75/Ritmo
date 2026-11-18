# A pinned scanner tool, never part of the application package.
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or -not $env:RUNNER_TEMP) { throw 'Disposable CI runner required.' }
$root=Join-Path $env:RUNNER_TEMP 'ritmo-grype-0.122.0'
New-Item -ItemType Directory -Path $root | Out-Null
$archive=Join-Path $root 'grype_0.122.0_windows_amd64.zip'
Invoke-WebRequest -Uri 'https://github.com/anchore/grype/releases/download/v0.122.0/grype_0.122.0_windows_amd64.zip' -OutFile $archive
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne '617017fbf9078bb9dff57c04c9e59e4dd7b9c93f861640e136fdd5af20263891') { throw 'Official Grype archive checksum mismatch.' }
Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $root 'tool')
$exe=Join-Path $root 'tool/grype.exe'
if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'd4c07a34bfd9aea9846d00f94093e909420bb1e59958a5907708f6b9f28209c3') { throw 'Official Grype executable checksum mismatch.' }
"RITMO_GRYPE=$exe" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
