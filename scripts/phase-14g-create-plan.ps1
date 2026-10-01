param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryRoot,

    [Parameter(Mandatory = $true)]
    [string]$PrivateDirectory,

    [Parameter(Mandatory = $true)]
    [string]$CredentialPath,

    [Parameter(Mandatory = $true)]
    [string]$TargetManifestPath,

    [string]$SourceStateProtectedPath
)

$ErrorActionPreference = 'Stop'
[void][System.Reflection.Assembly]::LoadWithPartialName('System.Security')

function Get-ProtectedValue {
    param([Parameter(Mandatory = $true)][string]$EncryptedValue)

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

function New-RandomBase64Key {
    $bytes = [byte[]]::new(32)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    try {
        return [Convert]::ToBase64String($bytes)
    } finally {
        [Array]::Clear($bytes, 0, $bytes.Length)
    }
}

function Set-OwnerOnlyAccess {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [switch]$Directory
    )

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $grant = if ($Directory) { '{0}:(OI)(CI)(F)' -f $identity } else { '{0}:(F)' -f $identity }
    & icacls.exe $Path /inheritance:r /grant:r $grant | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not restrict access to $Path"
    }
}

function Protect-File {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath,
        [Parameter(Mandatory = $true)][string]$Purpose
    )

    $source = [IO.Path]::GetFullPath($SourcePath)
    $destination = [IO.Path]::GetFullPath($DestinationPath)
    $sourceParent = [IO.Path]::GetFullPath((Split-Path -Parent $source))
    $destinationParent = [IO.Path]::GetFullPath((Split-Path -Parent $destination))
    if ($sourceParent -ne $destinationParent) {
        throw 'Protected output must stay beside its plaintext source.'
    }

    $plainBytes = [IO.File]::ReadAllBytes($source)
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
            [IO.File]::WriteAllText($destination, ($record | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
            Set-OwnerOnlyAccess -Path $destination
        } finally {
            [Array]::Clear($protectedBytes, 0, $protectedBytes.Length)
        }
    } finally {
        [Array]::Clear($plainBytes, 0, $plainBytes.Length)
    }

    [IO.File]::Delete($source)
}

function Unprotect-File {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    $record = Get-Content -Raw -LiteralPath $SourcePath | ConvertFrom-Json
    if ($record.schemaVersion -ne 1 -or -not $record.ciphertext) {
        throw "The protected state record is invalid: $SourcePath"
    }

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
        [Array]::Clear($protectedBytes, 0, $protectedBytes.Length)
    }
}

function Invoke-DockerTerraform {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$LogPath,
        [int[]]$AllowedExitCodes = @(0)
    )

    $output = & docker @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    [IO.File]::WriteAllLines($LogPath, [string[]]$output, [Text.UTF8Encoding]::new($false))
    Set-OwnerOnlyAccess -Path $LogPath
    if ($AllowedExitCodes -notcontains $exitCode) {
        throw "Terraform failed with exit code $exitCode. The restricted log is $LogPath"
    }
    return [ordered]@{ exitCode = $exitCode; output = [string[]]$output }
}

$repository = [IO.Path]::GetFullPath($RepositoryRoot)
$privateRoot = [IO.Path]::GetFullPath($PrivateDirectory)
$credentialFile = [IO.Path]::GetFullPath($CredentialPath)
$targetFile = [IO.Path]::GetFullPath($TargetManifestPath)
$terraformSource = Join-Path $repository 'infra/digitalocean'
$releaseManifestFile = Join-Path $repository 'docs/migration/phase-14/evidence/PART_14G_RELEASE_MANIFEST.json'
$controlScript = Join-Path $repository 'scripts/phase-14g-control.mjs'

foreach ($requiredPath in @($credentialFile, $targetFile, $releaseManifestFile, $controlScript)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required file is missing: $requiredPath"
    }
}

& node $controlScript authorize-apply --target $targetFile | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'The target manifest no longer authorizes an apply.'
}

$target = Get-Content -Raw -LiteralPath $targetFile | ConvertFrom-Json
$release = Get-Content -Raw -LiteralPath $releaseManifestFile | ConvertFrom-Json
$credentialRecord = Get-Content -Raw -LiteralPath $credentialFile | ConvertFrom-Json
$digitalOceanToken = Get-ProtectedValue $credentialRecord.digitalOceanToken
$spacesAccessKey = Get-ProtectedValue $credentialRecord.spacesAccessKey
$spacesSecretKey = Get-ProtectedValue $credentialRecord.spacesSecretKey

if (-not $digitalOceanToken.StartsWith('dop_v1_')) { throw 'The DigitalOcean token failed its format check.' }
if ($spacesAccessKey -cnotmatch '^DO[A-Z0-9]{18}$') { throw 'The Spaces access key failed its format check.' }
if ($spacesSecretKey.Length -lt 32) { throw 'The Spaces secret key failed its format check.' }

$digestSuffix = $target.manifestSha256.Substring(7, 12)
$sessionStamp = [DateTimeOffset]::UtcNow.ToString('yyyyMMddHHmmss')
$sessionDirectory = Join-Path $privateRoot "terraform-plan-$digestSuffix-$sessionStamp"
if (Test-Path -LiteralPath $sessionDirectory) {
    throw "The restricted plan directory already exists: $sessionDirectory"
}

[IO.Directory]::CreateDirectory($sessionDirectory) | Out-Null
Set-OwnerOnlyAccess -Path $sessionDirectory -Directory

foreach ($fileName in @('main.tf', 'outputs.tf', 'variables.tf', 'versions.tf', '.terraform.lock.hcl')) {
    [IO.File]::Copy((Join-Path $terraformSource $fileName), (Join-Path $sessionDirectory $fileName), $false)
}

if ($SourceStateProtectedPath) {
    $sourceState = [IO.Path]::GetFullPath($SourceStateProtectedPath)
    if (-not (Test-Path -LiteralPath $sourceState -PathType Leaf)) {
        throw "The protected source state is missing: $sourceState"
    }
    Unprotect-File -SourcePath $sourceState -DestinationPath (Join-Path $sessionDirectory 'terraform.tfstate')
}

$providerSource = Join-Path $terraformSource '.terraform/providers'
$providerDestination = Join-Path $sessionDirectory '.terraform/providers'
[IO.Directory]::CreateDirectory((Split-Path -Parent $providerDestination)) | Out-Null
Copy-Item -LiteralPath $providerSource -Destination $providerDestination -Recurse

$runtimeSecrets = [ordered]@{
    api_storage_signing_key = New-RandomBase64Key
    api_attachment_object_key_hmac_key = New-RandomBase64Key
    api_cursor_signing_key = New-RandomBase64Key
    api_idempotency_current_key_id = ([Guid]::NewGuid().ToString('N').Substring(0, 8))
    api_idempotency_current_key = New-RandomBase64Key
    api_idempotency_previous_keys = '[]'
    scanner_malware_signing_key = New-RandomBase64Key
}

$variables = [ordered]@{
    provisioning_authorized = $true
    configuration_ceiling_usd = 70
    owner_usage_cap_usd = 15
    reviewed_monthly_forecast_usd = 65.15
    maximum_runtime_hours = 72
    reviewed_run_forecast_usd = 12.5
    release_promoted = $false
    release_promotion_approved = $false
    expiry_scopes = @()
    approval = [ordered]@{
        target_manifest_id = $release.releaseId
        owner_approval_reference = $target.approval.ownerApprovalReference
        approved_on = $target.approval.approvedOn
        price_reviewed_on = $target.pricing.checkedOn
        retention_review_due_on = ([DateTimeOffset]$target.temporaryRun.cleanupDeadlineAt).ToString('yyyy-MM-dd')
        state_custodian = $target.custody.stateCustodian
        state_path_reference = $target.custody.statePathReference
        credential_custodian = $target.custody.credentialCustodian
        infrastructure_owner = $target.operatorAccess.operatorName
        security_owner = $target.operatorAccess.operatorName
        application_owner = $target.operatorAccess.operatorName
        incident_owner = $target.operatorAccess.operatorName
        release_reviewer = $target.operatorAccess.operatorName
        backup_custodian = $target.custody.backupCustodian
        variable_charge_owner = $target.custody.variableChargeOwner
        cleanup_manifest_id = $target.manifestId
    }
    operator_access = [ordered]@{
        operator_name = $target.operatorAccess.operatorName
        routine_account_reference = $target.operatorAccess.routineAccountReference
        routine_mfa = $target.operatorAccess.routineMfa
        emergency_account_reference = $target.operatorAccess.emergencyAccountReference
        emergency_mfa = $target.operatorAccess.emergencyMfa
        recovery_material_custody_reference = $target.operatorAccess.recoveryMaterialCustodyReference
        recovery_tested_on = $target.operatorAccess.recoveryTestedOn
        roles = @(
            'infrastructure_custodian',
            'security_custodian',
            'application_operator',
            'incident_operator',
            'release_reviewer'
        )
        separate_review_record = $target.operatorAccess.separateReviewRecord
    }
    runtime_secrets = $runtimeSecrets
    release_manifest = [ordered]@{
        release_id = $release.releaseId
        deployable = $release.deployable
        git_commit = $release.gitCommit
        backend_image = [ordered]@{
            registry_type = $release.backendImage.registryType
            registry = $release.backendImage.registry
            repository = $release.backendImage.repository
            digest = $release.backendImage.digest
        }
        keycloak_image = [ordered]@{
            registry_type = $release.keycloakImage.registryType
            registry = $release.keycloakImage.registry
            repository = $release.keycloakImage.repository
            digest = $release.keycloakImage.digest
        }
        frontend_sha256 = $release.frontendSha256
        frontend_root_sha256 = $release.frontendRootSha256
        dependency_lock_sha256 = [ordered]@{
            frontend = $release.dependencyLockSha256.frontend
            backend = $release.dependencyLockSha256.backend
            backend_dev = $release.dependencyLockSha256.backendDev
        }
        terraform_sha256 = $release.terraformSha256
        app_spec_sha256 = $release.appSpecSha256
        alembic_head = $release.alembicHead
    }
}

$variablePath = Join-Path $sessionDirectory 'phase14g.auto.tfvars.json'
[IO.File]::WriteAllText($variablePath, ($variables | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
Set-OwnerOnlyAccess -Path $variablePath

$env:DIGITALOCEAN_TOKEN = $digitalOceanToken
$env:SPACES_ACCESS_KEY_ID = $spacesAccessKey
$env:SPACES_SECRET_ACCESS_KEY = $spacesSecretKey

$mount = "type=bind,source=$sessionDirectory,target=/workspace"
$commonDockerArguments = @(
    'run', '--rm',
    '--env', 'DIGITALOCEAN_TOKEN',
    '--env', 'SPACES_ACCESS_KEY_ID',
    '--env', 'SPACES_SECRET_ACCESS_KEY',
    '--mount', $mount,
    '--workdir', '/workspace',
    'hashicorp/terraform:1.16.1'
)

$initLog = Join-Path $sessionDirectory 'terraform-init.log'
$planLog = Join-Path $sessionDirectory 'terraform-plan.log'
$showLog = Join-Path $sessionDirectory 'terraform-show.log'
$planPath = Join-Path $sessionDirectory 'phase14g.tfplan'
$planProtectedPath = "$planPath.dpapi.json"
$variablesProtectedPath = "$variablePath.dpapi.json"
$summaryPath = Join-Path $sessionDirectory 'plan-summary.json'

try {
    Invoke-DockerTerraform -Arguments ($commonDockerArguments + @(
        'init', '-input=false', '-reconfigure', '-lockfile=readonly', '-backend-config=path=terraform.tfstate'
    )) -LogPath $initLog | Out-Null

    $planResult = Invoke-DockerTerraform -Arguments ($commonDockerArguments + @(
        'plan', '-input=false', '-lock=false', '-detailed-exitcode', '-out=/workspace/phase14g.tfplan', '-var-file=/workspace/phase14g.auto.tfvars.json'
    )) -LogPath $planLog -AllowedExitCodes @(0, 2)

    $showOutput = & docker @commonDockerArguments show -json /workspace/phase14g.tfplan 2>&1
    $showExitCode = $LASTEXITCODE
    if ($showExitCode -ne 0) {
        [IO.File]::WriteAllLines($showLog, [string[]]$showOutput, [Text.UTF8Encoding]::new($false))
        Set-OwnerOnlyAccess -Path $showLog
        throw "Terraform could not read the saved plan. The restricted log is $showLog"
    }

    $planJson = ([string[]]$showOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 100
    $changes = @($planJson.resource_changes | ForEach-Object {
        [ordered]@{
            address = $_.address
            mode = $_.mode
            type = $_.type
            actions = @($_.change.actions)
        }
    })
    $deletions = @($changes | Where-Object { $_.actions -contains 'delete' })
    $creations = @($changes | Where-Object { $_.mode -eq 'managed' -and $_.actions.Count -eq 1 -and $_.actions[0] -eq 'create' })
    $reads = @($changes | Where-Object { $_.mode -eq 'data' -and $_.actions -contains 'read' })

    $expectedManaged = @(
        'terraform_data.phase_14_guard[0]',
        'digitalocean_database_cluster.shared[0]',
        'digitalocean_database_db.workloop[0]',
        'digitalocean_database_db.keycloak[0]',
        'digitalocean_database_user.workloop_migration[0]',
        'digitalocean_database_user.workloop_runtime[0]',
        'digitalocean_database_user.workloop_expiry_processing[0]',
        'digitalocean_database_user.workloop_file_scanner[0]',
        'digitalocean_database_user.workloop_storage_reconciler[0]',
        'digitalocean_database_user.keycloak[0]',
        'digitalocean_spaces_bucket.shared[0]',
        'digitalocean_spaces_key.api[0]',
        'digitalocean_spaces_key.file_scanner[0]',
        'digitalocean_spaces_key.storage_reconciler[0]',
        'digitalocean_spaces_key.object_backup[0]',
        'digitalocean_app.shared[0]',
        'digitalocean_database_firewall.app_only[0]',
        'digitalocean_project_resources.shared[0]'
    )
    $managedAddresses = @($changes | Where-Object { $_.mode -eq 'managed' } | ForEach-Object { $_.address } | Sort-Object)
    $expectedAddresses = @($expectedManaged | Sort-Object)
    $exactManagedSet = ($managedAddresses.Count -eq $expectedAddresses.Count) -and (-not (Compare-Object $managedAddresses $expectedAddresses))

    $databaseAfter = ($planJson.resource_changes | Where-Object { $_.address -eq 'digitalocean_database_cluster.shared[0]' } | Select-Object -First 1).change.after
    $bucketAfter = ($planJson.resource_changes | Where-Object { $_.address -eq 'digitalocean_spaces_bucket.shared[0]' } | Select-Object -First 1).change.after
    $appAfter = ($planJson.resource_changes | Where-Object { $_.address -eq 'digitalocean_app.shared[0]' } | Select-Object -First 1).change.after
    $appSpec = @($appAfter.spec)[0]

    $components = @()
    foreach ($componentKind in @('job', 'service', 'static_site', 'worker')) {
        foreach ($component in @($appSpec.$componentKind)) {
            $componentSize = if ($componentKind -eq 'static_site') { 'included' } else { $component.instance_size_slug }
            $componentCount = if ($componentKind -eq 'static_site') { 1 } else { [int]$component.instance_count }
            $jobKind = if ($componentKind -eq 'job') { $component.kind } else { '' }
            $image = @($component.image)[0]
            $github = @($component.github)[0]
            $components += [ordered]@{
                kind = $componentKind
                name = $component.name
                size = $componentSize
                instances = $componentCount
                jobKind = $jobKind
                imageRepository = $image.repository
                imageDigest = $image.digest
                githubRepository = $github.repo
                githubBranch = $github.branch
                deployOnPush = $github.deploy_on_push
            }
        }
    }

    $componentSignatures = @($components | ForEach-Object {
        '{0}|{1}|{2}|{3}|{4}' -f $_.kind, $_.name, $_.size, $_.instances, $_.jobKind
    } | Sort-Object)
    $expectedComponentSignatures = @(
        'job|database-migrate|apps-s-1vcpu-1gb-fixed|1|PRE_DEPLOY',
        'job|expiry|apps-s-1vcpu-0.5gb|1|UNSPECIFIED',
        'service|api|apps-s-1vcpu-1gb-fixed|1|',
        'service|keycloak|apps-s-1vcpu-2gb|1|',
        'static_site|web|included|1|',
        'worker|file-scanner|apps-s-1vcpu-0.5gb|1|',
        'worker|storage-reconciler|apps-s-1vcpu-0.5gb|1|'
    ) | Sort-Object
    $exactComponentSet = ($componentSignatures.Count -eq $expectedComponentSignatures.Count) -and (-not (Compare-Object $componentSignatures $expectedComponentSignatures))

    $backendDigest = $release.backendImage.digest
    $keycloakDigest = $release.keycloakImage.digest
    $componentArtifactsMatch = $true
    foreach ($component in $components) {
        if ($component.name -eq 'web') {
            $componentArtifactsMatch = $componentArtifactsMatch -and
                $component.githubRepository -eq 'AadhikR/workloop-clinic' -and
                $component.githubBranch -eq $release.gitCommit -and
                $component.deployOnPush -eq $false
        } elseif ($component.name -eq 'keycloak') {
            $componentArtifactsMatch = $componentArtifactsMatch -and
                $component.imageRepository -eq $release.keycloakImage.repository -and
                $component.imageDigest -eq $keycloakDigest
        } else {
            $componentArtifactsMatch = $componentArtifactsMatch -and
                $component.imageRepository -eq $release.backendImage.repository -and
                $component.imageDigest -eq $backendDigest
        }
    }

    $workerFlags = @()
    foreach ($worker in @($appSpec.worker)) {
        $flag = @($worker.env | Where-Object { $_.key -eq 'WORKLOOP_WORKER_PROCESSING_ENABLED' })[0]
        $workerFlags += [ordered]@{ name = $worker.name; enabled = $flag.value }
    }
    $expiryComponent = @($appSpec.job | Where-Object { $_.name -eq 'expiry' })[0]
    $expiryFlag = @($expiryComponent.env | Where-Object { $_.key -eq 'WORKLOOP_EXPIRY_PROCESSING_ENABLED' })[0]
    $workerFlagsMatch = @($workerFlags | Where-Object { $_.enabled -ne 'false' }).Count -eq 0
    $expiryFlagMatches = $expiryFlag.value -eq 'false'

    $databaseUserNames = @($planJson.resource_changes | Where-Object {
        $_.type -eq 'digitalocean_database_user'
    } | ForEach-Object { $_.change.after.name } | Sort-Object)
    $expectedDatabaseUserNames = @(
        'keycloak',
        'workloop_expiry_processing',
        'workloop_file_scanner',
        'workloop_migration',
        'workloop_runtime',
        'workloop_storage_reconciler'
    ) | Sort-Object
    $databaseUsersMatch = ($databaseUserNames.Count -eq $expectedDatabaseUserNames.Count) -and (-not (Compare-Object $databaseUserNames $expectedDatabaseUserNames))

    $spacesKeys = @($planJson.resource_changes | Where-Object {
        $_.type -eq 'digitalocean_spaces_key'
    } | ForEach-Object {
        $grant = @($_.change.after.grant)[0]
        [ordered]@{
            name = $_.change.after.name
            bucket = $grant.bucket
            permission = $grant.permission
        }
    })
    $spacesKeySignatures = @($spacesKeys | ForEach-Object {
        '{0}|{1}|{2}' -f $_.name, $_.bucket, $_.permission
    } | Sort-Object)
    $expectedSpacesKeySignatures = @(
        'workloop-clinic-dev-api|workloop-clinic-dev-634213f9|readwrite',
        'workloop-clinic-dev-file-scanner|workloop-clinic-dev-634213f9|read',
        'workloop-clinic-dev-object-backup|workloop-clinic-dev-634213f9|read',
        'workloop-clinic-dev-storage-reconciler|workloop-clinic-dev-634213f9|readwrite'
    ) | Sort-Object
    $spacesKeysMatch = ($spacesKeySignatures.Count -eq $expectedSpacesKeySignatures.Count) -and (-not (Compare-Object $spacesKeySignatures $expectedSpacesKeySignatures))

    $databaseMatches = (
        $databaseAfter.name -eq 'workloop-clinic-dev-db' -and
        $databaseAfter.engine -eq 'pg' -and
        $databaseAfter.version -eq '16' -and
        $databaseAfter.size -eq 'db-s-1vcpu-1gb' -and
        $databaseAfter.region -eq 'fra1' -and
        [int]$databaseAfter.node_count -eq 1 -and
        [int]$databaseAfter.storage_size_mib -eq 10240 -and
        $databaseAfter.private_network_uuid -eq 'b8b6d17b-eae4-47de-b2b5-9d10baabdd2d' -and
        @($databaseAfter.storage_autoscale).Count -eq 0
    )
    $bucketMatches = (
        $bucketAfter.name -eq 'workloop-clinic-dev-634213f9' -and
        $bucketAfter.region -eq 'fra1' -and
        $bucketAfter.acl -eq 'private' -and
        $bucketAfter.force_destroy -eq $false -and
        @($bucketAfter.versioning)[0].enabled -eq $true
    )
    $appMatches = (
        $appSpec.name -eq 'workloop-clinic-dev' -and
        $appSpec.region -eq 'fra' -and
        @($appSpec.maintenance)[0].enabled -eq $true -and
        $exactComponentSet -and
        $componentArtifactsMatch -and
        $workerFlagsMatch -and
        $expiryFlagMatches
    )
    $targetDetailsMatch = $databaseMatches -and $databaseUsersMatch -and $bucketMatches -and $spacesKeysMatch -and $appMatches

    $summary = [ordered]@{
        schemaVersion = 1
        generatedAt = [DateTimeOffset]::UtcNow.ToString('o')
        targetManifestSha256 = $target.manifestSha256
        releaseId = $release.releaseId
        planHasChanges = $planResult.exitCode -eq 2
        managedCreateCount = $creations.Count
        dataReadCount = $reads.Count
        deletionCount = $deletions.Count
        exactExpectedManagedSet = $exactManagedSet
        changes = $changes
        exactPlanDetailsMatch = $targetDetailsMatch
        reviewedPlan = [ordered]@{
            project = 'workloop-clinic-dev'
            vpc = 'fra1-default'
            app = $appSpec.name
            appRegion = $appSpec.region
            maintenanceEnabled = @($appSpec.maintenance)[0].enabled
            components = $components
            workerFlags = $workerFlags
            expiryEnabled = $expiryFlag.value
            database = [ordered]@{
                name = $databaseAfter.name
                engine = $databaseAfter.engine
                version = $databaseAfter.version
                size = $databaseAfter.size
                region = $databaseAfter.region
                nodes = $databaseAfter.node_count
                storageMiB = $databaseAfter.storage_size_mib
                privateNetworkId = $databaseAfter.private_network_uuid
                storageAutoscaleBlockPresent = @($databaseAfter.storage_autoscale).Count -gt 0
                users = $databaseUserNames
            }
            bucket = [ordered]@{
                name = $bucketAfter.name
                region = $bucketAfter.region
                acl = $bucketAfter.acl
                forceDestroy = $bucketAfter.force_destroy
                versioning = @($bucketAfter.versioning)[0].enabled
                keys = $spacesKeys
            }
            fixedMonthlyUsd = 65.15
            reviewedRunForecastUsd = 12.5
            ownerUsageCapUsd = 15
        }
        safeToRequestApplyApproval = (
            $planResult.exitCode -eq 2 -and
            $deletions.Count -eq 0 -and
            $exactManagedSet -and
            $targetDetailsMatch
        )
    }

    [IO.File]::WriteAllText($summaryPath, ($summary | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
    Set-OwnerOnlyAccess -Path $summaryPath
    Protect-File -SourcePath $planPath -DestinationPath $planProtectedPath -Purpose 'Phase 14G reviewed Terraform plan'
    Protect-File -SourcePath $variablePath -DestinationPath $variablesProtectedPath -Purpose 'Phase 14G approved Terraform input variables'

    if (Test-Path -LiteralPath (Join-Path $sessionDirectory 'terraform.tfstate')) {
        Protect-File -SourcePath (Join-Path $sessionDirectory 'terraform.tfstate') -DestinationPath (Join-Path $sessionDirectory 'terraform.tfstate.dpapi.json') -Purpose 'Phase 14G Terraform state after planning'
    }

    if (-not $summary.safeToRequestApplyApproval) {
        throw "The saved plan did not meet the approved zero-delete resource boundary. Review $summaryPath"
    }

    Write-Output "PLAN_READY"
    Write-Output "SUMMARY_PATH=$summaryPath"
    Write-Output "MANAGED_CREATES=$($creations.Count)"
    Write-Output "DATA_READS=$($reads.Count)"
    Write-Output "DELETIONS=$($deletions.Count)"
} finally {
    $env:DIGITALOCEAN_TOKEN = $null
    $env:SPACES_ACCESS_KEY_ID = $null
    $env:SPACES_SECRET_ACCESS_KEY = $null
    $digitalOceanToken = $null
    $spacesAccessKey = $null
    $spacesSecretKey = $null
    $runtimeSecrets = $null
    $variables = $null
}
