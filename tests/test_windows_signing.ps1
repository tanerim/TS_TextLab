# Exercise trust failures and upstream signature preservation without a private key.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$folder = Join-Path ([IO.Path]::GetTempPath()) ('textlab-sign-test-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $folder | Out-Null
$global:TextLabTestStates = @{}
$global:TextLabTestCalls = @()
function Get-AuthenticodeSignature {
    param([string]$LiteralPath)
    $status = $global:TextLabTestStates[$LiteralPath]
    [pscustomobject]@{
        Status = $status
        SignerCertificate = $(if ($status -eq 'Valid') { [pscustomobject]@{ Subject = 'Test publisher' } } else { $null })
        TimeStamperCertificate = $(if ($status -eq 'Valid') { [pscustomobject]@{} } else { $null })
    }
}
function Invoke-TextLabTestSignTool {
    $global:TextLabTestCalls += ,$args
    if ($args[0] -eq 'sign') { $global:TextLabTestStates[$args[-1]] = 'Valid' }
    $global:LASTEXITCODE = 0
}
try {
    $env:TEXTLAB_WINDOWS_SIGNING_ENABLED = 'true'
    $env:TEXTLAB_SIGNTOOL = 'Invoke-TextLabTestSignTool'
    $env:TEXTLAB_WINDOWS_TIMESTAMP_URL = 'http://timestamp.example.test'
    $env:TEXTLAB_WINDOWS_CERT_THUMBPRINT = '0000000000000000000000000000000000000000'
    $env:TEXTLAB_WINDOWS_SIGN_ARGS_JSON = ''
    $unsigned = Join-Path $folder 'unsigned.pyd'
    $upstream = Join-Path $folder 'upstream.dll'
    Set-Content -LiteralPath $unsigned -Value 'test'
    Set-Content -LiteralPath $upstream -Value 'test'
    $global:TextLabTestStates[$unsigned] = 'NotSigned'
    $global:TextLabTestStates[$upstream] = 'Valid'
    $report = Join-Path $folder 'inventory.json'
    & "$root/scripts/sign_windows.ps1" -Path $folder -Report $report
    $signCalls = @($global:TextLabTestCalls | Where-Object { $_[0] -eq 'sign' })
    if ($signCalls.Count -ne 1 -or $signCalls[0][-1] -ne $unsigned) { throw 'Upstream signature was overwritten or unsigned file was skipped' }
    $inventory = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if ($inventory.counts.'.pyd' -ne 1 -or $inventory.counts.'.dll' -ne 1) { throw 'Wrong binary counts' }
    if (@($inventory.files | Where-Object { $_.status -ne 'Valid' }).Count) { throw 'Unsigned output accepted' }

    $global:TextLabTestStates[$unsigned] = 'HashMismatch'
    $global:TextLabTestCalls = @()
    $failed = $false
    try { & "$root/scripts/sign_windows.ps1" -Path $unsigned } catch { $failed = $true }
    if (!$failed -or $global:TextLabTestCalls.Count) { throw 'Tampered signature was not rejected before signing' }

    $env:TEXTLAB_WINDOWS_SIGNING_ENABLED = 'false'
    $failed = $false
    try { & "$root/scripts/sign_windows.ps1" -Path $upstream -Mode Sign } catch { $failed = $true }
    if (!$failed) { throw 'Unconfigured signing was accepted' }
    Write-Host 'Windows signing trust checks passed'
} finally {
    Remove-Item -LiteralPath $folder -Recurse -Force
    Remove-Variable TextLabTestStates, TextLabTestCalls -Scope Global
}
