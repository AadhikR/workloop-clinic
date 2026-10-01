param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'

function Read-HiddenValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Prompt
    )

    while ($true) {
        Write-Host "$Prompt`: " -NoNewline
        $builder = [System.Text.StringBuilder]::new()

        while ($true) {
            $key = [Console]::ReadKey($true)
            if ($key.Key -eq [ConsoleKey]::Enter) {
                break
            }

            if ($key.Key -eq [ConsoleKey]::Backspace) {
                if ($builder.Length -gt 0) {
                    $null = $builder.Remove($builder.Length - 1, 1)
                    Write-Host "`b `b" -NoNewline
                }
                continue
            }

            if (-not [char]::IsControl($key.KeyChar)) {
                $null = $builder.Append($key.KeyChar)
                Write-Host '*' -NoNewline
            }
        }

        Write-Host ''
        $value = $builder.ToString().Trim()
        if ($value.Length -gt 0) {
            return $value
        }

        Write-Host 'Nothing was pasted. Try again.' -ForegroundColor Yellow
    }
}

try {
    $targetDirectory = Split-Path -Parent $OutputPath
    New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null

    Write-Host ''
    Write-Host 'Phase 14G credential capture'
    Write-Host 'Paste each value from its DigitalOcean tab. Stars confirm that the paste worked.'
    Write-Host ''

    do {
        $digitalOceanTokenText = Read-HiddenValue '1 of 3: DigitalOcean deployment token'
        if (-not $digitalOceanTokenText.StartsWith('dop_v1_')) {
            Write-Host 'That does not look like a DigitalOcean token. Copy the token value and try again.' -ForegroundColor Yellow
        }
    } until ($digitalOceanTokenText.StartsWith('dop_v1_'))

    do {
        $spacesAccessKeyText = Read-HiddenValue '2 of 3: Spaces access key ID'
        if ($spacesAccessKeyText -notmatch '^DO[A-Z0-9]{18}$') {
            Write-Host 'That does not look like the 20-character Spaces access key ID. Try again.' -ForegroundColor Yellow
        }
    } until ($spacesAccessKeyText -match '^DO[A-Z0-9]{18}$')

    do {
        $spacesSecretKeyText = Read-HiddenValue '3 of 3: Spaces secret key'
        if ($spacesSecretKeyText.Length -lt 32 -or $spacesSecretKeyText -eq $spacesAccessKeyText) {
            Write-Host 'That does not look like the longer Spaces secret key. Try again.' -ForegroundColor Yellow
        }
    } until ($spacesSecretKeyText.Length -ge 32 -and $spacesSecretKeyText -ne $spacesAccessKeyText)

    function Protect-OnThisMachine {
        param(
            [Parameter(Mandatory = $true)]
            [string]$Value
        )

        [void][System.Reflection.Assembly]::LoadWithPartialName('System.Security')
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

    $record = [ordered]@{
        schemaVersion = 1
        createdAtUtc = (Get-Date).ToUniversalTime().ToString('o')
        protection = 'Windows local-machine DPAPI with owner-only file access'
        digitalOceanToken = Protect-OnThisMachine $digitalOceanTokenText
        spacesAccessKey = Protect-OnThisMachine $spacesAccessKeyText
        spacesSecretKey = Protect-OnThisMachine $spacesSecretKeyText
    }

    $temporaryPath = "$OutputPath.tmp"
    $record | ConvertTo-Json | Set-Content -LiteralPath $temporaryPath -Encoding utf8
    Move-Item -LiteralPath $temporaryPath -Destination $OutputPath -Force

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    & icacls.exe $OutputPath /inheritance:r /grant:r "${identity}:(F)" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Windows could not restrict the encrypted credential file to the current account.'
    }

    $digitalOceanTokenText = $null
    $spacesAccessKeyText = $null
    $spacesSecretKeyText = $null

    Write-Host ''
    Write-Host 'Saved with Windows account encryption. Return to Codex and type done.' -ForegroundColor Green
} catch {
    Write-Host ''
    Write-Host "Capture failed: $($_.Exception.Message)" -ForegroundColor Red
}

Read-Host 'Press Enter to close this window'
