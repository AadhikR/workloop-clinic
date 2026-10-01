param(
    [Parameter(Mandatory = $true)]
    [string]$CredentialPath,

    [switch]$FromClipboard
)

$ErrorActionPreference = 'Stop'
[void][System.Reflection.Assembly]::LoadWithPartialName('System.Security')

$digitalOceanToken = if ($FromClipboard) {
    (Get-Clipboard -Raw).Trim()
} else {
    [Console]::In.ReadToEnd().Trim()
}
if (-not $digitalOceanToken.StartsWith('dop_v1_')) {
    throw 'The replacement DigitalOcean token failed its format check.'
}

function Protect-OnThisMachine {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
    try {
        $protectedBytes = [System.Security.Cryptography.ProtectedData]::Protect(
            $bytes,
            $null,
            [System.Security.Cryptography.DataProtectionScope]::LocalMachine
        )
        return [Convert]::ToBase64String($protectedBytes)
    } finally {
        [Array]::Clear($bytes, 0, $bytes.Length)
    }
}

$record = Get-Content -Raw -LiteralPath $CredentialPath | ConvertFrom-Json
$record.digitalOceanToken = Protect-OnThisMachine $digitalOceanToken

if ($record.PSObject.Properties.Name -contains 'updatedAtUtc') {
    $record.updatedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
} else {
    $record | Add-Member -NotePropertyName updatedAtUtc -NotePropertyValue ((Get-Date).ToUniversalTime().ToString('o'))
}

$temporaryPath = "$CredentialPath.tmp"
$record | ConvertTo-Json | Set-Content -LiteralPath $temporaryPath -Encoding utf8
Move-Item -LiteralPath $temporaryPath -Destination $CredentialPath -Force

$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe $CredentialPath /inheritance:r /grant:r "${identity}:(F)" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Windows could not restrict the encrypted credential file to the current account.'
}

$digitalOceanToken = $null
[ordered]@{
    updated = $true
    credentialPath = $CredentialPath
} | ConvertTo-Json
