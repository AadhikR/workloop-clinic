$parent = Join-Path (Split-Path -Parent $PSScriptRoot) "backend"
$postgresPath = Join-Path $parent ".env.postgres"
$apiPath = Join-Path $parent ".env.api"
$migrationPath = Join-Path $parent ".env.migration"

if (-not (Test-Path -LiteralPath $parent)) {
    throw "Expected backend directory was not found."
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
    $migrationLine = [System.IO.File]::ReadLines($postgresPath) | Where-Object {
        $_.StartsWith("WORKLOOP_MIGRATION_PASSWORD=")
    }
    if (-not $migrationLine) {
        throw "$postgresPath does not contain WORKLOOP_MIGRATION_PASSWORD."
    }
    $migrationPassword = $migrationLine.Substring($migrationLine.IndexOf("=") + 1)
}
else {
    $runtimePassword = New-LocalSecret
    $migrationPassword = New-LocalSecret
    $postgresLines = @(
        "POSTGRES_PASSWORD=$(New-LocalSecret)"
        "WORKLOOP_MIGRATION_PASSWORD=$migrationPassword"
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

if (-not (Test-Path -LiteralPath $apiPath)) {
    [System.IO.File]::WriteAllLines(
        $apiPath,
        $apiLines,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

if (-not (Test-Path -LiteralPath $migrationPath)) {
    $migrationLines = @(
        "MIGRATION_DATABASE_URL=postgresql+psycopg://workloop_migration:${migrationPassword}@postgres:5432/workloop"
    )
    [System.IO.File]::WriteAllLines(
        $migrationPath,
        $migrationLines,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

"Local PostgreSQL, API, and migration environment files are ready; no secret values were displayed."
