param(
    [Parameter(Mandatory)]
    [string]$PythonPath
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$fixture = Join-Path $PSScriptRoot 'fixtures/fake_backend.py'
$temporary = Join-Path ([System.IO.Path]::GetTempPath()) (
    'samba-ad-fake-' + [System.Guid]::NewGuid().ToString('N')
)

# Runs a read under a preference set in this function's own scope, the way a
# script sets 'Stop' at its top, and reports whether the read stopped it.
function Test-PreferenceStops {
    param([string]$Preference)

    $ErrorActionPreference = $Preference
    try {
        Get-ADUser -Identity missing -Server dc1 | Out-Null
        return $false
    } catch {
        return $true
    }
}

try {
    if ($IsWindows) {
        $backend = $temporary + '.cmd'
        Set-Content -LiteralPath $backend -Value (
            '@"' + $PythonPath + '" "' + $fixture + '" %*'
        ) -Encoding Ascii
    } else {
        $backend = $temporary
        Set-Content -LiteralPath $backend -Value (
            "#!/bin/sh`nexec `"$PythonPath`" `"$fixture`" `"`$@`""
        ) -Encoding utf8NoBOM
        & chmod 700 $backend
    }

    $env:SAMBA_POWERSHELL_BACKEND = $backend
    $env:PSModulePath = (Join-Path $repoRoot 'powershell') + (
        [System.IO.Path]::PathSeparator + $env:PSModulePath
    )
    $command = Get-Command Get-ADUser -ErrorAction Stop
    if ($command.Source -ne 'SambaAD') {
        throw 'Get-ADUser did not autoload from SambaAD.'
    }
    $user = Get-ADUser -Identity 'CN=Alice,DC=example,DC=com' -Server dc1
    if ($user.PSObject.TypeNames[0] -ne 'SambaAD.User') {
        throw 'Get-ADUser did not return a SambaAD.User object.'
    }
    if (-not $user.PSObject.Properties['Surname'] -or $null -ne $user.Surname) {
        throw 'A property the backend sent as null did not arrive as a null property.'
    }
    if ("$user" -ne 'CN=Alice,DC=example,DC=com') {
        throw 'A returned object does not convert to its distinguished name.'
    }
    $piped = $user | Get-ADObject -Server dc1
    if ($piped.DistinguishedName -ne 'CN=Alice,DC=example,DC=com') {
        throw 'A piped object did not bind -Identity by its DistinguishedName.'
    }

    $captured = @()
    Get-ADUser -Identity missing -Server dc1 -ErrorAction SilentlyContinue `
        -ErrorVariable captured
    if (
        $captured.Count -ne 1 -or
        $captured[0].FullyQualifiedErrorId -notlike 'SambaAD.IdentityNotFound*' -or
        $captured[0].CategoryInfo.Category -ne 'ObjectNotFound' -or
        $captured[0].TargetObject -ne 'missing' -or
        $captured[0].ToString() -match 'Traceback'
    ) {
        throw 'The missing object did not produce a structured ErrorRecord.'
    }
    if (-not (Test-PreferenceStops -Preference 'Stop')) {
        throw "The caller's `$ErrorActionPreference = 'Stop' did not stop on a missing object."
    }
    if (Test-PreferenceStops -Preference 'SilentlyContinue') {
        throw "The caller's 'SilentlyContinue' preference did not keep the error non-terminating."
    }

    $broken = @()
    Get-ADUser -Identity garbage -Server dc1 -ErrorAction SilentlyContinue `
        -ErrorVariable broken
    if (
        $broken.Count -ne 1 -or
        $broken[0].FullyQualifiedErrorId -notlike 'SambaAD.ProtocolError*' -or
        $broken[0].CategoryInfo.Category -ne 'ProtocolError' -or
        $broken[0].ToString() -match 'Traceback'
    ) {
        throw 'A backend answering outside the protocol did not give a typed ErrorRecord.'
    }

    $env:SAMBA_POWERSHELL_BACKEND = $temporary + '-does-not-exist'
    Import-Module SambaAD -Force
    $absent = @()
    Get-ADUser -Identity 'CN=Alice,DC=example,DC=com' -Server dc1 `
        -ErrorAction SilentlyContinue -ErrorVariable absent
    if ($absent.Count -ne 1 -or $absent[0].FullyQualifiedErrorId -notlike 'SambaAD.BackendUnavailable*') {
        throw 'A backend that cannot start did not give SambaAD.BackendUnavailable.'
    }
    Write-Output 'PowerShell boundary tests passed.'
} finally {
    Remove-Item -LiteralPath ($temporary + '.cmd') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
}
