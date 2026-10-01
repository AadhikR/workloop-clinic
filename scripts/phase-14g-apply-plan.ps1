param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryRoot,

    [Parameter(Mandatory = $true)]
    [string]$SessionDirectory,

    [Parameter(Mandatory = $true)]
    [string]$CredentialPath,

    [Parameter(Mandatory = $true)]
    [string]$TargetManifestPath
)

$ErrorActionPreference = 'Stop'
[void][System.Reflection.Assembly]::LoadWithPartialName('System.Security')

function Set-OwnerOnlyAccess {
    param([Parameter(Mandatory = $true)][string]$Path)

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $grant = '{0}:(F)' -f $identity
    & icacls.exe $Path /inheritance:r /grant:r $grant | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not restrict access to $Path" }
}

function Unprotect-Text {
    param([Parameter(Mandatory = $true)][string]$Ciphertext)

    $protectedBytes = [Convert]::FromBase64String($Ciphertext)
    $plainBytes = [System.Security.Cryptography.ProtectedData]::Unprotect(
        $protectedBytes,
        $null,
        [System.Security.Cryptography.DataProtectionScope]::LocalMachine
    )
    try {
        return [Text.Encoding]::UTF8.GetString($plainBytes)
    } finally {
        [Array]::Clear($plainBytes, 0, $plainBytes.Length)
    }
}

function Restore-ProtectedFile {
    param(
        [Parameter(Mandatory = $true)][string]$ProtectedPath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    $record = Get-Content -Raw -LiteralPath $ProtectedPath | ConvertFrom-Json
    $protectedBytes = [Convert]::FromBase64String($record.ciphertext)
    $plainBytes = [System.Security.Cryptography.ProtectedData]::Unprotect(
        $protectedBytes,
        $null,
        [System.Security.Cryptography.DataProtectionScope]::LocalMachine
    )
    try {
        [IO.File]::WriteAllBytes($DestinationPath, $plainBytes)
        Set-OwnerOnlyAccess -Path $DestinationPath
    } finally {
        [Array]::Clear($plainBytes, 0, $plainBytes.Length)
    }
}

function Protect-File {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath,
        [Parameter(Mandatory = $true)][string]$Purpose
    )

    $plainBytes = [IO.File]::ReadAllBytes($SourcePath)
    try {
        $protectedBytes = [System.Security.Cryptography.ProtectedData]::Protect(
            $plainBytes,
            $null,
            [System.Security.Cryptography.DataProtectionScope]::LocalMachine
        )
        try {
            $record = [ordered]@{
                schemaVersion = 1
                protection = 'Windows local-machine DPAPI with owner-only file access'
                purpose = $Purpose
                createdAt = [DateTimeOffset]::UtcNow.ToString('o')
                ciphertext = [Convert]::ToBase64String($protectedBytes)
            }
            [IO.File]::WriteAllText($DestinationPath, ($record | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
            Set-OwnerOnlyAccess -Path $DestinationPath
        } finally {
            [Array]::Clear($protectedBytes, 0, $protectedBytes.Length)
        }
    } finally {
        [Array]::Clear($plainBytes, 0, $plainBytes.Length)
    }
    [IO.File]::Delete($SourcePath)
}

$repository = [IO.Path]::GetFullPath($RepositoryRoot)
$session = [IO.Path]::GetFullPath($SessionDirectory)
$credentialFile = [IO.Path]::GetFullPath($CredentialPath)
$targetFile = [IO.Path]::GetFullPath($TargetManifestPath)
$controlScript = Join-Path $repository 'scripts/phase-14g-control.mjs'
$summaryPath = Join-Path $session 'plan-summary.json'
$planPath = Join-Path $session 'phase14g.tfplan'
$protectedPlanPath = "$planPath.dpapi.json"
$statePath = Join-Path $session 'terraform.tfstate'
$protectedStatePath = "$statePath.dpapi.json"
$applyLogPath = Join-Path $session 'terraform-apply.log'
$applySummaryPath = Join-Path $session 'apply-summary.json'

foreach ($requiredPath in @($credentialFile, $targetFile, $controlScript, $summaryPath, $protectedPlanPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required file is missing: $requiredPath"
    }
}

& node $controlScript authorize-apply --target $targetFile | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'The approved target is no longer inside its preflight window.' }

$target = Get-Content -Raw -LiteralPath $targetFile | ConvertFrom-Json
$summary = Get-Content -Raw -LiteralPath $summaryPath | ConvertFrom-Json
if ($summary.targetManifestSha256 -ne $target.manifestSha256 -or
    $summary.safeToRequestApplyApproval -ne $true -or
    $summary.deletionCount -ne 0 -or
    $summary.exactExpectedManagedSet -ne $true -or
    $summary.exactPlanDetailsMatch -ne $true) {
    throw 'The saved plan summary does not match the approved zero-delete target.'
}

$credentialRecord = Get-Content -Raw -LiteralPath $credentialFile | ConvertFrom-Json
$digitalOceanToken = Unprotect-Text $credentialRecord.digitalOceanToken
$spacesAccessKey = Unprotect-Text $credentialRecord.spacesAccessKey
$spacesSecretKey = Unprotect-Text $credentialRecord.spacesSecretKey

Restore-ProtectedFile -ProtectedPath $protectedPlanPath -DestinationPath $planPath
if (Test-Path -LiteralPath $protectedStatePath -PathType Leaf) {
    Restore-ProtectedFile -ProtectedPath $protectedStatePath -DestinationPath $statePath
}

$planSha256 = 'sha256:' + (Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash.ToLowerInvariant()
$env:DIGITALOCEAN_TOKEN = $digitalOceanToken
$env:SPACES_ACCESS_KEY_ID = $spacesAccessKey
$env:SPACES_SECRET_ACCESS_KEY = $spacesSecretKey
$mount = "type=bind,source=$session,target=/workspace"
$dockerArguments = @(
    'run', '--rm',
    '--env', 'DIGITALOCEAN_TOKEN',
    '--env', 'SPACES_ACCESS_KEY_ID',
    '--env', 'SPACES_SECRET_ACCESS_KEY',
    '--mount', $mount,
    '--workdir', '/workspace',
    'hashicorp/terraform:1.16.1'
)
$startedAt = [DateTimeOffset]::UtcNow
$applySucceeded = $false

try {
    $applyOutput = & docker @dockerArguments apply -input=false -lock=false -auto-approve /workspace/phase14g.tfplan 2>&1
    $applyExitCode = $LASTEXITCODE
    [IO.File]::WriteAllLines($applyLogPath, [string[]]$applyOutput, [Text.UTF8Encoding]::new($false))
    Set-OwnerOnlyAccess -Path $applyLogPath
    if ($applyExitCode -ne 0) {
        throw "Terraform apply failed with exit code $applyExitCode. The restricted log is $applyLogPath"
    }

    $outputText = & docker @dockerArguments output -json 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Terraform applied the plan but could not read its safe outputs.' }
    $outputs = ([string[]]$outputText -join [Environment]::NewLine) | ConvertFrom-Json -Depth 30

    $applySummary = [ordered]@{
        schemaVersion = 1
        targetManifestSha256 = $target.manifestSha256
        planSha256 = $planSha256
        startedAt = $startedAt.ToString('o')
        completedAt = [DateTimeOffset]::UtcNow.ToString('o')
        success = $true
        createdResourceCount = 18
        deletionCount = 0
        maintenanceEnabled = $true
        workersEnabled = $false
        expiryEnabled = $false
        appId = $outputs.app_id.value
        appUrl = $outputs.app_url.value
        databaseClusterId = $outputs.database_cluster_id.value
        spacesBucketName = $outputs.spaces_bucket_name.value
        estimatedMonthlyUsd = $outputs.estimated_monthly_usd.value
        projectedBaseUsageUsd = $outputs.projected_base_usage_usd.value
        operatorAccessReady = $outputs.operator_access_ready.value
        releaseIdentity = $outputs.release_identity.value
    }
    [IO.File]::WriteAllText($applySummaryPath, ($applySummary | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
    Set-OwnerOnlyAccess -Path $applySummaryPath
    $applySucceeded = $true
} finally {
    if (Test-Path -LiteralPath $statePath -PathType Leaf) {
        Protect-File -SourcePath $statePath -DestinationPath $protectedStatePath -Purpose 'Phase 14G Terraform state after approved apply'
    }
    $backupStatePath = "$statePath.backup"
    if (Test-Path -LiteralPath $backupStatePath -PathType Leaf) {
        Protect-File -SourcePath $backupStatePath -DestinationPath "$backupStatePath.dpapi.json" -Purpose 'Phase 14G Terraform state backup after approved apply'
    }
    if (Test-Path -LiteralPath $planPath -PathType Leaf) {
        [IO.File]::Delete($planPath)
    }
    $env:DIGITALOCEAN_TOKEN = $null
    $env:SPACES_ACCESS_KEY_ID = $null
    $env:SPACES_SECRET_ACCESS_KEY = $null
    $digitalOceanToken = $null
    $spacesAccessKey = $null
    $spacesSecretKey = $null
}

if ($applySucceeded) {
    Write-Output 'APPLY_SUCCESS'
    Write-Output "SUMMARY_PATH=$applySummaryPath"
}
