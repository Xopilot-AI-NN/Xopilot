# Описание: Тот же закреплённый LiteRT SDK для Windows, без Python и MSYS.
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
$temporary = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }
$archive = Join-Path $temporary 'xopilot-litert-capi-1.0.0.zip'
if (-not (Test-Path $archive)) {
    Invoke-WebRequest 'https://github.com/google-ai-edge/LiteRT-LM/releases/download/v0.19.1/litert_lm_c_api-1.0.0.zip' -OutFile $archive
}
$digest = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($digest -ne '1d430d80eaf536f696a4922270ba55eb3d112189ac198c3066d487a45e3b4d4c') { throw 'SHA-256 LiteRT SDK не совпадает' }
New-Item -ItemType Directory -Force App/native/windows_x86_64 | Out-Null
Expand-Archive -Path $archive -DestinationPath App/native/sdk -Force
Copy-Item App/native/sdk/lib/windows_x86_64/bin/litert-lm.dll App/native/windows_x86_64/litert-lm.dll -Force
Compress-Archive -Path App/native/sdk/LICENSE,App/native/sdk/licenses -DestinationPath App/native/runtime-licenses.zip -Force
