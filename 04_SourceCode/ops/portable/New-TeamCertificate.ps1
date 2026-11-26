param([Parameter(Mandatory)][string]$Target)
$ErrorActionPreference = 'Stop'
[IO.Directory]::CreateDirectory($Target) | Out-Null
$key = [Security.Cryptography.RSA]::Create(2048)
try {
    $request = [Security.Cryptography.X509Certificates.CertificateRequest]::new(
        'CN=localhost', $key, [Security.Cryptography.HashAlgorithmName]::SHA256,
        [Security.Cryptography.RSASignaturePadding]::Pkcs1)
    $san = [Security.Cryptography.X509Certificates.SubjectAlternativeNameBuilder]::new()
    $san.AddDnsName('localhost')
    $san.AddIpAddress([Net.IPAddress]::Loopback)
    $request.CertificateExtensions.Add($san.Build())
    $cert = $request.CreateSelfSigned([DateTimeOffset]::Now.AddMinutes(-5), [DateTimeOffset]::Now.AddYears(2))
    try {
        [IO.File]::WriteAllText((Join-Path $Target 'localhost.pem'), $cert.ExportCertificatePem())
        [IO.File]::WriteAllText((Join-Path $Target 'localhost-key.pem'), $key.ExportPkcs8PrivateKeyPem())
    } finally { $cert.Dispose() }
} finally { $key.Dispose() }
