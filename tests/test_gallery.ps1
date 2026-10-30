# Publishes the module to a throwaway local repository and installs it from
# there the two ways the gallery is used, Install-PSResource and Install-Module,
# in a throwaway home, so what is proved is what an installation from the gallery
# leaves: a folder that imports and runs its own backend with no package and no
# execute bit. Run it where python3 and PowerShell are, with nothing else needed.
[CmdletBinding()]
param(
    [Parameter()]
    [string]$Server,

    [Parameter()]
    [string]$SamAccountName
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$work = Join-Path ([System.IO.Path]::GetTempPath()) ('sambaad-gallery-' + [guid]::NewGuid().ToString('N'))
$feed = Join-Path $work 'feed'
$stage = Join-Path $work 'stage/SambaAD'
$null = New-Item -ItemType Directory -Force -Path $feed

# Runs a script in a fresh pwsh with its own home, so its module path is empty.
function Invoke-InHome {
    param([string]$HomeName, [string]$Script)
    $homeDirectory = Join-Path $work $HomeName
    $null = New-Item -ItemType Directory -Force -Path $homeDirectory
    $savedHome = $env:HOME
    try {
        $env:HOME = $homeDirectory
        Remove-Item Env:XDG_DATA_HOME, Env:XDG_CONFIG_HOME, Env:XDG_CACHE_HOME -ErrorAction Ignore
        $output = & pwsh -NoProfile -NonInteractive -Command $Script 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "In $HomeName, exit $LASTEXITCODE`: $($output -join "`n")"
        }
        return $output
    } finally {
        $env:HOME = $savedHome
    }
}

# What every installation must then do, whichever command installed it: find the
# module under the home, not start any other backend, and reach the backend's
# first refusal, or a real read when a domain was named.
$check = @"
`$ErrorActionPreference = 'Stop'
Remove-Item Env:SAMBA_POWERSHELL_BACKEND, Env:SAMBA_AD_SERVER -ErrorAction Ignore
Import-Module SambaAD
`$module = Get-Module SambaAD
if (-not `$module.ModuleBase.StartsWith(`$HOME)) { throw "Imported from `$(`$module.ModuleBase)" }
if (-not (Test-Path (Join-Path `$module.ModuleBase 'backend/samba_powershell/cli.py'))) { throw 'No backend inside the module' }
if ((Get-Command Get-ADUser).Source -ne 'SambaAD') { throw 'Get-ADUser is not from SambaAD' }
try {
    Get-ADUser someone -ErrorAction Stop
    throw 'A read with no server did not fail'
} catch {
    if (`$_.FullyQualifiedErrorId -notmatch '^SambaAD\.(ServerRequired|ClientUnavailable)') { throw "Unexpected: `$(`$_.FullyQualifiedErrorId) `$_" }
}
if ('$Server') {
    `$user = Get-ADUser '$SamAccountName' -Server '$Server'
    if (`$user.SamAccountName -ne '$SamAccountName') { throw 'The live read returned the wrong object' }
}
Write-Output "ok `$(`$module.ModuleBase)"
"@

try {
    & sh (Join-Path $repoRoot 'tools/build_gallery_module.sh') $stage | Out-Null
    Register-PSResourceRepository -Name SambaADFeed -Uri $feed -Trusted -ErrorAction Stop
    Publish-PSResource -Path $stage -Repository SambaADFeed -ErrorAction Stop
    if (-not (Get-ChildItem -LiteralPath $feed -Filter 'SambaAD.*.nupkg')) {
        throw 'Publishing left no package in the feed.'
    }
    Invoke-InHome 'psresource' @"
Register-PSResourceRepository -Name SambaADFeed -Uri '$feed' -Trusted -ErrorAction Stop
Install-PSResource -Name SambaAD -Repository SambaADFeed -Scope CurrentUser -TrustRepository -ErrorAction Stop
$check
"@
    Invoke-InHome 'installmodule' @"
Register-PSRepository -Name SambaADFeed -SourceLocation '$feed' -InstallationPolicy Trusted -ErrorAction Stop
Install-Module -Name SambaAD -Repository SambaADFeed -Scope CurrentUser -Force -ErrorAction Stop
$check
"@
    Write-Output 'Gallery installation tests passed.'
} finally {
    Unregister-PSResourceRepository -Name SambaADFeed -ErrorAction Ignore
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction Ignore
}
