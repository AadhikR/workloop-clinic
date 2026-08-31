$parent = Join-Path (Split-Path -Parent $PSScriptRoot) "backend"
$postgresPath = Join-Path $parent ".env.postgres"
$apiPath = Join-Path $parent ".env.api"

if (-not (Test-Path -LiteralPath $parent)) {
    throw "Expected backend directory was not found."
}

if (Test-Path -LiteralPath $apiPath) {
    throw "$apiPath already exists; refusing to overwrite it."
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

if (Test-Path -LiteralPath $postgresPath) {
    $runtimeLine = [System.IO.File]::ReadLines($postgresPath) | Where-Object {
        $_.StartsWith("WORKLOOP_RUNTIME_PASSWORD=")
    }
    if (-not $runtimeLine) {
        throw "$postgresPath does not contain WORKLOOP_RUNTIME_PASSWORD."
    }
    $runtimePassword = $runtimeLine.Substring($runtimeLine.IndexOf("=") + 1)
}
else {
    $runtimePassword = New-LocalSecret
    $postgresLines = @(
        "POSTGRES_PASSWORD=$(New-LocalSecret)"
        "WORKLOOP_MIGRATION_PASSWORD=$(New-LocalSecret)"
        "WORKLOOP_RUNTIME_PASSWORD=$runtimePassword"
        "KEYCLOAK_DB_PASSWORD=$(New-LocalSecret)"
    )
    [System.IO.File]::WriteAllLines(
        $postgresPath,
        $postgresLines,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

$apiLines = @(
    "APP_ENV=local"
    "APP_BASE_URL=http://127.0.0.1:8000"
    "FRONTEND_URL=http://127.0.0.1:5173"
    "LOG_LEVEL=INFO"
    "DATABASE_HEALTH_TIMEOUT_SECONDS=5"
    "DATABASE_URL=postgresql+psycopg://workloop_runtime:${runtimePassword}@postgres:5432/workloop"
)

[System.IO.File]::WriteAllLines(
    $apiPath,
    $apiLines,
    (New-Object System.Text.UTF8Encoding($false))
)

"Local PostgreSQL and API environment files are ready; no secret values were displayed."
