$parent = Join-Path (Split-Path -Parent $PSScriptRoot) "backend"
$path = Join-Path $parent ".env.postgres"

if (-not (Test-Path -LiteralPath $parent)) {
    throw "Expected backend directory was not found."
}

if (Test-Path -LiteralPath $path) {
    throw "$path already exists; refusing to overwrite it."
}

function New-LocalSecret {
    $bytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }

    [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

$lines = @(
    "POSTGRES_PASSWORD=$(New-LocalSecret)"
    "WORKLOOP_MIGRATION_PASSWORD=$(New-LocalSecret)"
    "WORKLOOP_RUNTIME_PASSWORD=$(New-LocalSecret)"
    "KEYCLOAK_DB_PASSWORD=$(New-LocalSecret)"
)

[System.IO.File]::WriteAllLines(
    $path,
    $lines,
    (New-Object System.Text.UTF8Encoding($false))
)

"Created backend/.env.postgres with four generated values; no values were displayed."
