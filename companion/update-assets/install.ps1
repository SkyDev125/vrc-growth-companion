$ErrorActionPreference = 'Stop'
$target = $env:MIDSDEN_UPDATE_TARGET
$result = $env:MIDSDEN_UPDATE_RESULT
try {
    if (!(Test-Path -LiteralPath $target)) { throw 'Installed companion was not found.' }
    Set-Content -LiteralPath $env:MIDSDEN_UPDATE_READY -Value 'ready' -Encoding UTF8
    $running = Get-Process -Id ([int]$env:MIDSDEN_UPDATE_PID) -ErrorAction SilentlyContinue
    if ($running) { $running.WaitForExit(120000) | Out-Null; if (!$running.HasExited) { throw 'Companion did not close.' } }
    $installDir = Split-Path -Parent $target
    $arguments = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="' + $installDir + '" /LOG="' + $result + '.setup.log"'
    $setup = Start-Process -FilePath $env:MIDSDEN_UPDATE_PACKAGE -ArgumentList $arguments -PassThru
    $setup.WaitForExit()
    if ($setup.ExitCode -ne 0) { throw ('Setup failed with code ' + $setup.ExitCode) }
    Set-Content -LiteralPath $result -Value 'ok' -Encoding UTF8
} catch {
    Set-Content -LiteralPath $result -Value ('Update failed: ' + $_.Exception.Message) -Encoding UTF8
}
if (Test-Path -LiteralPath $target) {
    if ($env:MIDSDEN_UPDATE_SELF_TEST -eq '1') { Start-Process -FilePath $target -ArgumentList '--self-test' }
    else { Start-Process -FilePath $target -WorkingDirectory (Split-Path -Parent $target) }
}
