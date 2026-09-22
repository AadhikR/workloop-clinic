$parent = Join-Path (Split-Path -Parent $PSScriptRoot) "backend"
$postgresPath = Join-Path $parent ".env.postgres"
$apiPath = Join-Path $parent ".env.api"
$migrationPath = Join-Path $parent ".env.migration"
$keycloakPath = Join-Path $parent ".env.keycloak"
$scannerPath = Join-Path $parent ".env.file-scanner"

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

function New-LocalKeyId {
    $bytes = New-Object byte[] 4
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }

    return -join ($bytes | ForEach-Object { $_.ToString("x2") })
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
    $expiryLine = [System.IO.File]::ReadLines($postgresPath) | Where-Object {
        $_.StartsWith("WORKLOOP_EXPIRY_PROCESSING_PASSWORD=")
    }
    if ($expiryLine) {
        $expiryProcessingPassword = $expiryLine.Substring($expiryLine.IndexOf("=") + 1)
    }
    else {
        $expiryProcessingPassword = New-LocalSecret
        $postgresLines = @([System.IO.File]::ReadAllLines($postgresPath)) + @(
            "WORKLOOP_EXPIRY_PROCESSING_PASSWORD=$expiryProcessingPassword"
        )
        [System.IO.File]::WriteAllLines(
            $postgresPath,
            $postgresLines,
            (New-Object System.Text.UTF8Encoding($false))
        )
    }
    $storageReconcilerLine = [System.IO.File]::ReadLines($postgresPath) | Where-Object {
        $_.StartsWith("WORKLOOP_STORAGE_RECONCILER_PASSWORD=")
    }
    if ($storageReconcilerLine) {
        $storageReconcilerPassword = $storageReconcilerLine.Substring(
            $storageReconcilerLine.IndexOf("=") + 1
        )
    }
    else {
        $storageReconcilerPassword = New-LocalSecret
        $postgresLines = @([System.IO.File]::ReadAllLines($postgresPath)) + @(
            "WORKLOOP_STORAGE_RECONCILER_PASSWORD=$storageReconcilerPassword"
        )
        [System.IO.File]::WriteAllLines(
            $postgresPath,
            $postgresLines,
            (New-Object System.Text.UTF8Encoding($false))
        )
    }
    $fileScannerLine = [System.IO.File]::ReadLines($postgresPath) | Where-Object {
        $_.StartsWith("WORKLOOP_FILE_SCANNER_PASSWORD=")
    }
    if ($fileScannerLine) {
        $fileScannerPassword = $fileScannerLine.Substring($fileScannerLine.IndexOf("=") + 1)
    }
    else {
        $fileScannerPassword = New-LocalSecret
        $postgresLines = @([System.IO.File]::ReadAllLines($postgresPath)) + @(
            "WORKLOOP_FILE_SCANNER_PASSWORD=$fileScannerPassword"
        )
        [System.IO.File]::WriteAllLines(
            $postgresPath,
            $postgresLines,
            (New-Object System.Text.UTF8Encoding($false))
        )
    }
    $keycloakDatabaseLine = [System.IO.File]::ReadLines($postgresPath) | Where-Object {
        $_.StartsWith("KEYCLOAK_DB_PASSWORD=")
    }
    if (-not $keycloakDatabaseLine) {
        throw "$postgresPath does not contain KEYCLOAK_DB_PASSWORD."
    }
    $keycloakDatabasePassword = $keycloakDatabaseLine.Substring(
        $keycloakDatabaseLine.IndexOf("=") + 1
    )
}
else {
    $runtimePassword = New-LocalSecret
    $migrationPassword = New-LocalSecret
    $expiryProcessingPassword = New-LocalSecret
    $storageReconcilerPassword = New-LocalSecret
    $fileScannerPassword = New-LocalSecret
    $keycloakDatabasePassword = New-LocalSecret
    $postgresLines = @(
        "POSTGRES_PASSWORD=$(New-LocalSecret)"
        "WORKLOOP_MIGRATION_PASSWORD=$migrationPassword"
        "WORKLOOP_RUNTIME_PASSWORD=$runtimePassword"
        "WORKLOOP_EXPIRY_PROCESSING_PASSWORD=$expiryProcessingPassword"
        "WORKLOOP_STORAGE_RECONCILER_PASSWORD=$storageReconcilerPassword"
        "WORKLOOP_FILE_SCANNER_PASSWORD=$fileScannerPassword"
        "KEYCLOAK_DB_PASSWORD=$keycloakDatabasePassword"
    )
    [System.IO.File]::WriteAllLines(
        $postgresPath,
        $postgresLines,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

$explicitFileScannerPassword = [Environment]::GetEnvironmentVariable(
    "PHASE11B_SCANNER_DB_PASSWORD"
)
if (-not [string]::IsNullOrEmpty($explicitFileScannerPassword)) {
    $fileScannerPassword = $explicitFileScannerPassword
    $postgresLines = [System.IO.File]::ReadAllLines($postgresPath) | ForEach-Object {
        if ($_.StartsWith("WORKLOOP_FILE_SCANNER_PASSWORD=")) {
            "WORKLOOP_FILE_SCANNER_PASSWORD=$fileScannerPassword"
        }
        else {
            $_
        }
    }
    [System.IO.File]::WriteAllLines(
        $postgresPath,
        $postgresLines,
        (New-Object System.Text.UTF8Encoding($false))
    )
}

$apiLines = @(
    "APP_ENV=local"
    "APP_BASE_URL=http://127.0.0.1:8000"
    "FRONTEND_URL=http://127.0.0.1:5174"
    "LOG_LEVEL=INFO"
    "DATABASE_HEALTH_TIMEOUT_SECONDS=5"
    "API_REQUEST_TIMEOUT_SECONDS=15"
    "OIDC_ISSUER=http://127.0.0.1:8080/realms/workloop-dev"
    "OIDC_AUDIENCE=workloop-api"
    "OIDC_JWKS_URL=http://127.0.0.1:8080/realms/workloop-dev/protocol/openid-connect/certs"
    "OIDC_JWKS_CONNECT_TIMEOUT_SECONDS=2"
    "OIDC_JWKS_READ_TIMEOUT_SECONDS=2"
    "OIDC_JWKS_TOTAL_TIMEOUT_SECONDS=5"
    "OIDC_JWKS_CACHE_TTL_SECONDS=300"
    "OIDC_JWKS_REFRESH_COOLDOWN_SECONDS=1"
    "CURSOR_SIGNING_KEY=$(New-LocalSecret)"
    "IDEMPOTENCY_RECOVERY_CURRENT_KEY_ID=$(New-LocalKeyId)"
    "IDEMPOTENCY_RECOVERY_CURRENT_KEY=$(New-LocalSecret)"
    "IDEMPOTENCY_RECOVERY_PREVIOUS_KEYS=[]"
    "STORAGE_BACKEND=synthetic"
    "STORAGE_SIGNING_KEY=$(New-LocalSecret)"
    "ATTACHMENT_OBJECT_KEY_HMAC_KEY=$(New-LocalSecret)"
    "SYNTHETIC_STORAGE_PATH=/var/lib/workloop-storage"
    "DATABASE_URL=postgresql+psycopg://workloop_runtime:${runtimePassword}@postgres:5432/workloop"
)

$reconcilerPath = Join-Path $parent ".env.storage-reconciler"
$reconcilerLines = @(
    "DATABASE_URL=postgresql+psycopg://workloop_storage_reconciler:${storageReconcilerPassword}@postgres:5432/workloop"
    "STORAGE_BACKEND=synthetic"
    "STORAGE_SIGNING_KEY=$($apiLines | Where-Object { $_.StartsWith('STORAGE_SIGNING_KEY=') } | ForEach-Object { $_.Substring($_.IndexOf('=') + 1) })"
    "SYNTHETIC_STORAGE_PATH=/var/lib/workloop-storage"
)
[System.IO.File]::WriteAllLines(
    $reconcilerPath,
    $reconcilerLines,
    (New-Object System.Text.UTF8Encoding($false))
)

$scannerLines = @(
    "DATABASE_URL=postgresql+psycopg://workloop_file_scanner:${fileScannerPassword}@postgres:5432/workloop"
    "STORAGE_BACKEND=synthetic"
    "STORAGE_SIGNING_KEY=$($apiLines | Where-Object { $_.StartsWith('STORAGE_SIGNING_KEY=') } | ForEach-Object { $_.Substring($_.IndexOf('=') + 1) })"
    "ATTACHMENT_OBJECT_KEY_HMAC_KEY=$($apiLines | Where-Object { $_.StartsWith('ATTACHMENT_OBJECT_KEY_HMAC_KEY=') } | ForEach-Object { $_.Substring($_.IndexOf('=') + 1) })"
    "SYNTHETIC_STORAGE_PATH=/var/lib/workloop-storage"
    "MALWARE_SCANNER_BACKEND=synthetic"
    "MALWARE_SCANNER_DEFINITION=synthetic-v1"
    "MALWARE_SCANNER_SIGNING_KEY=$(New-LocalSecret)"
)
[System.IO.File]::WriteAllLines(
    $scannerPath,
    $scannerLines,
    (New-Object System.Text.UTF8Encoding($false))
)

[System.IO.File]::WriteAllLines(
    $apiPath,
    $apiLines,
    (New-Object System.Text.UTF8Encoding($false))
)

$migrationLines = @(
    "MIGRATION_DATABASE_URL=postgresql+psycopg://workloop_migration:${migrationPassword}@postgres:5432/workloop"
)
[System.IO.File]::WriteAllLines(
    $migrationPath,
    $migrationLines,
    (New-Object System.Text.UTF8Encoding($false))
)

if (Test-Path -LiteralPath $keycloakPath) {
    $keycloakExistingLines = [System.IO.File]::ReadAllLines($keycloakPath)
    $keycloakAdminUsername = $keycloakExistingLines | Where-Object {
        $_.StartsWith("KC_BOOTSTRAP_ADMIN_USERNAME=")
    }
    $keycloakAdminPassword = $keycloakExistingLines | Where-Object {
        $_.StartsWith("KC_BOOTSTRAP_ADMIN_PASSWORD=")
    }
    if (-not $keycloakAdminUsername) {
        $keycloakAdminUsername = "KC_BOOTSTRAP_ADMIN_USERNAME=workloop-local-admin"
    }
    if (-not $keycloakAdminPassword) {
        $keycloakAdminPassword = "KC_BOOTSTRAP_ADMIN_PASSWORD=$(New-LocalSecret)"
    }
    $keycloakLines = @(
        "KC_DB_PASSWORD=$keycloakDatabasePassword"
        $keycloakAdminUsername
        $keycloakAdminPassword
    )
}
else {
    $keycloakLines = @(
        "KC_DB_PASSWORD=$keycloakDatabasePassword"
        "KC_BOOTSTRAP_ADMIN_USERNAME=workloop-local-admin"
        "KC_BOOTSTRAP_ADMIN_PASSWORD=$(New-LocalSecret)"
    )
}
[System.IO.File]::WriteAllLines(
    $keycloakPath,
    $keycloakLines,
    (New-Object System.Text.UTF8Encoding($false))
)

"Local PostgreSQL, API, migration, Keycloak, storage reconciler, and file scanner environment files are ready; no secret values were displayed."
