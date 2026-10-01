param(
    [Parameter(Mandatory = $true)]
    [string]$CredentialPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
[void][System.Reflection.Assembly]::LoadWithPartialName('System.Security')

function Unprotect-Text {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Ciphertext
    )

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

$record = Get-Content -Raw -LiteralPath $CredentialPath | ConvertFrom-Json
$digitalOceanToken = Unprotect-Text $record.digitalOceanToken
$headers = @{ Authorization = "Bearer $digitalOceanToken" }
$baseUri = 'https://api.digitalocean.com/v2'
$projectId = '634213f9-2e43-4aea-8f4e-22ddc3ecdac9'
$vpcId = 'b8b6d17b-eae4-47de-b2b5-9d10baabdd2d'

try {
    $project = (Invoke-RestMethod -Headers $headers -Uri "$baseUri/projects/$projectId").project
    $projectResources = (Invoke-RestMethod -Headers $headers -Uri "$baseUri/projects/$projectId/resources?per_page=200").resources
    $vpc = (Invoke-RestMethod -Headers $headers -Uri "$baseUri/vpcs/$vpcId").vpc
    $apps = @((Invoke-RestMethod -Headers $headers -Uri "$baseUri/apps?per_page=200").apps | Where-Object { $null -ne $_ })
    $databases = @((Invoke-RestMethod -Headers $headers -Uri "$baseUri/databases?per_page=200").databases | Where-Object { $null -ne $_ })
    $databaseOptions = Invoke-RestMethod -Headers $headers -Uri "$baseUri/databases/options"
    $registry = (Invoke-RestMethod -Headers $headers -Uri "$baseUri/registry").registry
    $regions = (Invoke-RestMethod -Headers $headers -Uri "$baseUri/regions?per_page=200").regions
    $sizes = (Invoke-RestMethod -Headers $headers -Uri "$baseUri/sizes?per_page=200").sizes

    $result = [ordered]@{
        checkedAt = [DateTimeOffset]::UtcNow.ToString('o')
        project = [ordered]@{
            id = $project.id
            name = $project.name
            purpose = $project.purpose
        }
        projectResourceIds = @($projectResources | ForEach-Object { $_.urn })
        vpc = [ordered]@{
            id = $vpc.id
            name = $vpc.name
            region = $vpc.region
            ipRange = $vpc.ip_range
        }
        apps = @($apps | ForEach-Object {
            [ordered]@{ id = $_.id; name = $_.spec.name; region = $_.region.slug }
        })
        databases = @($databases | ForEach-Object {
            [ordered]@{ id = $_.id; name = $_.name; status = $_.status; region = $_.region; engine = $_.engine; version = $_.version }
        })
        registry = [ordered]@{
            name = $registry.name
            region = $registry.region
            storageUsageBytes = $registry.storage_usage_bytes
        }
        targetRegionAvailable = @($regions | Where-Object { $_.slug -eq 'fra1' -and $_.available }).Count -eq 1
        targetDatabaseSizeAvailable = ($databaseOptions | ConvertTo-Json -Depth 30 -Compress).Contains('db-s-1vcpu-1gb')
    }

    $result | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $OutputPath -Encoding utf8
} finally {
    $digitalOceanToken = $null
    $headers = $null
}
