param(
    [Parameter(Mandatory = $true)]
    [string]$CredentialPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
[void][System.Reflection.Assembly]::LoadWithPartialName('System.Security')

function Get-ProtectedValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$EncryptedValue
    )

    $protectedBytes = [Convert]::FromBase64String($EncryptedValue)
    $plainBytes = [System.Security.Cryptography.ProtectedData]::Unprotect(
        $protectedBytes,
        $null,
        [System.Security.Cryptography.DataProtectionScope]::LocalMachine
    )

    try {
        return [System.Text.Encoding]::UTF8.GetString($plainBytes)
    } finally {
        [Array]::Clear($plainBytes, 0, $plainBytes.Length)
    }
}

try {
    $record = Get-Content -Raw -LiteralPath $CredentialPath | ConvertFrom-Json
    $digitalOceanToken = Get-ProtectedValue $record.digitalOceanToken
    $spacesAccessKey = Get-ProtectedValue $record.spacesAccessKey
    $spacesSecretKey = Get-ProtectedValue $record.spacesSecretKey

    $checks = [ordered]@{
        fileReadable = $true
        protection = $record.protection
        digitalOceanTokenValid = $digitalOceanToken.StartsWith('dop_v1_')
        spacesAccessKeyValid = $spacesAccessKey -cmatch '^DO[A-Z0-9]{18}$'
        spacesSecretKeyValid = $spacesSecretKey.Length -ge 32 -and $spacesSecretKey -ne $spacesAccessKey
    }
    $checks.allPassed = $checks.digitalOceanTokenValid -and $checks.spacesAccessKeyValid -and $checks.spacesSecretKeyValid

    $digitalOceanToken = $null
    $spacesAccessKey = $null
    $spacesSecretKey = $null
    $checks | ConvertTo-Json | Set-Content -LiteralPath $OutputPath -Encoding utf8
} catch {
    [ordered]@{
        fileReadable = $false
        allPassed = $false
        error = $_.Exception.Message
    } | ConvertTo-Json | Set-Content -LiteralPath $OutputPath -Encoding utf8
    exit 1
}
