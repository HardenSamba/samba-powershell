[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Server,

    [Parameter(Mandatory)]
    [string]$Identity,

    [Parameter(Mandatory)]
    [string]$MissingIdentity,

    [Parameter(Mandatory)]
    [string]$ExpectedSamAccountName,

    [Parameter(Mandatory)]
    [string]$BackendCommand,

    [Parameter()]
    [string]$ExpectedErrorId = 'SambaAD.ObjectNotFound'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$moduleRoot = Join-Path $repoRoot 'powershell'
$previousBackend = $env:SAMBA_POWERSHELL_BACKEND
$previousModulePath = $env:PSModulePath

try {
    $env:SAMBA_POWERSHELL_BACKEND = $BackendCommand
    $env:PSModulePath = $moduleRoot + (
        [System.IO.Path]::PathSeparator + $previousModulePath
    )
    Import-Module SambaAD -Force

    $user = Get-ADUser -Identity $Identity -Server $Server -Properties @(
        'sAMAccountName',
        'distinguishedName'
    )
    if ($user.PSObject.TypeNames[0] -ne 'SambaAD.User') {
        throw 'The live result is not typed as SambaAD.User.'
    }
    $memberNames = @(
        $user | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name
    )
    if (
        $memberNames -notcontains 'sAMAccountName' -or
        $memberNames -notcontains 'distinguishedName'
    ) {
        throw 'Get-Member did not expose the requested directory properties.'
    }
    if ($user.sAMAccountName -ne $ExpectedSamAccountName) {
        throw 'The live result has an unexpected sAMAccountName.'
    }
    if (-not [string]::Equals(
        [string]$user.distinguishedName,
        $Identity,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw 'The live result has an unexpected distinguishedName.'
    }

    $captured = @()
    $missing = Get-ADUser -Identity $MissingIdentity -Server $Server `
        -ErrorAction SilentlyContinue -ErrorVariable +captured
    if ($null -ne $missing) {
        throw 'The missing live object unexpectedly returned a result.'
    }
    if (
        $captured.Count -ne 1 -or
        $captured[0].FullyQualifiedErrorId -notlike "$ExpectedErrorId*" -or
        $captured[0].CategoryInfo.Category -ne 'ObjectNotFound' -or
        $captured[0].TargetObject -ne $MissingIdentity -or
        $captured[0].ToString() -match 'Traceback'
    ) {
        throw 'The missing live object did not produce the expected ErrorRecord.'
    }

    Write-Output 'Live Samba ADWS PowerShell acceptance passed.'
} finally {
    Remove-Module SambaAD -Force -ErrorAction SilentlyContinue
    $env:SAMBA_POWERSHELL_BACKEND = $previousBackend
    $env:PSModulePath = $previousModulePath
}
