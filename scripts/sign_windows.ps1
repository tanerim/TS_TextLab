param(
    [Parameter(Mandatory=$true)][string]$Path,
    [ValidateSet('Sign', 'Verify', 'Inventory')][string]$Mode = 'Sign',
    [string]$Report
)
$ErrorActionPreference = 'Stop'
$enabled = $env:TEXTLAB_WINDOWS_SIGNING_ENABLED -eq 'true'
if ($Mode -eq 'Sign' -and !$enabled) { throw 'Windows signing is not configured' }
$files = @(if (Test-Path -LiteralPath $Path -PathType Container) {
    Get-ChildItem -LiteralPath $Path -Recurse -File | Where-Object { $_.Extension.ToLowerInvariant() -in '.exe', '.dll', '.pyd' }
} else { Get-Item -LiteralPath $Path })
if ($files.Count -eq 0) { throw "No Windows binaries found: $Path" }
$rows = @()
foreach ($file in $files) {
    $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
    $before = $signature.Status.ToString()
    if ($Mode -eq 'Sign' -and $before -eq 'NotSigned') {
        $signArgs = @('sign', '/fd', 'SHA256', '/tr', $env:TEXTLAB_WINDOWS_TIMESTAMP_URL, '/td', 'SHA256')
        if ($env:TEXTLAB_WINDOWS_SIGN_ARGS_JSON) {
            $signArgs += @(ConvertFrom-Json $env:TEXTLAB_WINDOWS_SIGN_ARGS_JSON)
        } else {
            $signArgs += @('/sha1', $env:TEXTLAB_WINDOWS_CERT_THUMBPRINT, '/s', 'My')
        }
        & $env:TEXTLAB_SIGNTOOL @signArgs $file.FullName
        if ($LASTEXITCODE -ne 0) { throw "SignTool failed: $($file.FullName)" }
        $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
        if (!$signature.TimeStamperCertificate) { throw "Missing timestamp: $($file.FullName)" }
    }
    if ($Mode -ne 'Inventory') {
        # Preserve valid upstream signatures; do not hide tampering or trust errors by re-signing.
        if ($signature.Status.ToString() -ne 'Valid') { throw "Invalid signature ($($signature.Status)): $($file.FullName)" }
        & $env:TEXTLAB_SIGNTOOL verify /pa /all $file.FullName
        if ($LASTEXITCODE -ne 0) { throw "Signature verification failed: $($file.FullName)" }
    }
    $rows += [ordered]@{
        path = $file.FullName
        extension = $file.Extension.ToLowerInvariant()
        before = $before
        status = $signature.Status.ToString()
        signer = $(if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { $null })
        timestamped = [bool]$signature.TimeStamperCertificate
        sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    }
}
$counts = [ordered]@{}
foreach ($extension in '.pyd', '.dll', '.exe') { $counts[$extension] = @($rows | Where-Object { $_.extension -eq $extension }).Count }
$result = [ordered]@{ mode = $Mode; signing_enabled = $enabled; counts = $counts; files = $rows }
if ($Report) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Report) | Out-Null
    $result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $Report -Encoding utf8
}
$counts | ConvertTo-Json -Compress | Write-Host
