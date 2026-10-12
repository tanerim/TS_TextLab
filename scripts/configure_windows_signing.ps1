$ErrorActionPreference = 'Stop'
$pfx = $env:WINDOWS_CERTIFICATE_BASE64
$thumbprint = $env:TEXTLAB_WINDOWS_CERT_THUMBPRINT
$providerArgs = $env:TEXTLAB_WINDOWS_SIGN_ARGS_JSON
$configured = [bool]($pfx -or $thumbprint -or $providerArgs)
if (!$configured) {
    if ($env:REQUIRE_WINDOWS_SIGNING -eq 'true') { throw 'Signed Windows distribution is required. Configure a code-signing certificate/provider first; see docs/windows-signing.md.' }
    'TEXTLAB_WINDOWS_SIGNING_ENABLED=false' | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
    exit 0
}
$signtool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" |
    Sort-Object FullName -Descending | Select-Object -First 1
if (!$signtool) { throw 'Windows SDK x64 signtool.exe not found' }
if ($providerArgs) {
    $parsed = ConvertFrom-Json $providerArgs
    if ($parsed -isnot [array] -or $parsed.Count -eq 0 -or @($parsed | Where-Object { $_ -isnot [string] }).Count) {
        throw 'TEXTLAB_WINDOWS_SIGN_ARGS_JSON must be a nonempty JSON array of strings'
    }
    if ($pfx -or $thumbprint) { throw 'Choose either provider arguments or a certificate, not both' }
} elseif ($pfx) {
    $certPath = Join-Path $env:RUNNER_TEMP 'textlab-signing.pfx'
    try {
        [IO.File]::WriteAllBytes($certPath, [Convert]::FromBase64String($pfx))
        $password = if ($env:WINDOWS_CERTIFICATE_PASSWORD) {
            ConvertTo-SecureString -String $env:WINDOWS_CERTIFICATE_PASSWORD -AsPlainText -Force
        } else { New-Object System.Security.SecureString }
        $cert = Import-PfxCertificate -FilePath $certPath -CertStoreLocation Cert:\CurrentUser\My -Password $password |
            Where-Object { $_.HasPrivateKey } | Select-Object -First 1
        if (!$cert) { throw 'PFX has no private signing key' }
        $thumbprint = $cert.Thumbprint
        "TEXTLAB_WINDOWS_IMPORTED_CERT=$thumbprint" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
    } finally { Remove-Item -LiteralPath $certPath -Force -ErrorAction SilentlyContinue }
}
if (!$providerArgs) {
    if ($thumbprint -notmatch '^[A-Fa-f0-9]{40}$') { throw 'Invalid certificate thumbprint' }
    $cert = Get-Item "Cert:\CurrentUser\My\$thumbprint"
    if (!$cert.HasPrivateKey -or $cert.NotAfter -le (Get-Date) -or $cert.NotBefore -gt (Get-Date)) { throw 'Signing certificate has no usable current private key' }
    if ('1.3.6.1.5.5.7.3.3' -notin $cert.EnhancedKeyUsageList.ObjectId.Value) { throw 'Certificate must allow Code Signing' }
    "TEXTLAB_WINDOWS_CERT_THUMBPRINT=$thumbprint" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
}
"TEXTLAB_SIGNTOOL=$($signtool.FullName)" | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
'TEXTLAB_WINDOWS_SIGNING_ENABLED=true' | Out-File -FilePath $env:GITHUB_ENV -Append -Encoding utf8
