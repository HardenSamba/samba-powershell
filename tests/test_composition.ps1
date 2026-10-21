param(
    [Parameter(Mandatory)]
    [string]$PythonPath
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$stub = Join-Path $PSScriptRoot 'fixtures/stub_adws'
$source = Join-Path $repoRoot 'src'
$separator = [System.IO.Path]::PathSeparator
$temporary = Join-Path ([System.IO.Path]::GetTempPath()) (
    'samba-ad-real-' + [System.Guid]::NewGuid().ToString('N')
)

try {
    $env:PYTHONPATH = $source + $separator + $stub
    if ($IsWindows) {
        $backend = $temporary + '.cmd'
        Set-Content -LiteralPath $backend -Value (
            '@"' + $PythonPath + '" -m samba_powershell.cli %*'
        ) -Encoding Ascii
    } else {
        $backend = $temporary
        Set-Content -LiteralPath $backend -Value (
            "#!/bin/sh`nexec `"$PythonPath`" -m samba_powershell.cli `"`$@`""
        ) -Encoding utf8NoBOM
        & chmod 700 $backend
    }

    $env:SAMBA_POWERSHELL_BACKEND = $backend
    $env:PSModulePath = (Join-Path $repoRoot 'powershell') + (
        $separator + $env:PSModulePath
    )
    $user = Get-ADUser -Identity 'CN=Alice,DC=example,DC=com' -Server dc1 `
        -Properties adwsServer, userAccountControl, memberOf
    if ($user.PSObject.TypeNames[0] -ne 'SambaAD.User') {
        throw 'The real backend did not return a SambaAD.User object.'
    }
    if ($user.DistinguishedName -ne 'CN=Alice,DC=example,DC=com') {
        throw 'The real backend did not carry the requested identity.'
    }
    if ($user.Name -ne [char]0x41 + 'nn' + [char]0xE9 + 'e') {
        throw "The UTF-8 boundary corrupted a non-ASCII value: $($user.Name)"
    }
    if ($user.adwsServer -ne 'dc1') {
        throw 'The real backend did not pass -Server through to the client.'
    }
    if ($user.Enabled -ne $true) {
        throw 'The renderer did not derive Enabled from userAccountControl.'
    }
    if ($user.userAccountControl -isnot [long] -and $user.userAccountControl -isnot [int]) {
        throw 'An Integer-syntax attribute did not arrive as a number.'
    }
    if ($user.memberOf -isnot [array] -or $user.memberOf.Count -ne 1) {
        throw 'A multi-valued attribute holding one value did not arrive as a list.'
    }
    if ($null -ne $user.Surname -or -not $user.PSObject.Properties['Surname']) {
        throw 'An unset default property is not present as null.'
    }

    $byName = Get-ADUser -Identity alice -Server dc1
    if ($byName.DistinguishedName -ne 'CN=Alice,DC=example,DC=com') {
        throw 'An account name did not resolve through the search client.'
    }

    $captured = @()
    Get-ADUser -Identity 'CN=Missing,CN=Users,DC=example,DC=com' -Server dc1 -ErrorAction SilentlyContinue `
        -ErrorVariable captured
    if (
        $captured.Count -ne 1 -or
        [string]::IsNullOrEmpty($captured[0].FullyQualifiedErrorId) -or
        $captured[0].FullyQualifiedErrorId -notlike 'SambaAD.ObjectNotFound*' -or
        $captured[0].CategoryInfo.Category -ne 'ObjectNotFound' -or
        $captured[0].TargetObject -ne 'CN=Missing,CN=Users,DC=example,DC=com' -or
        $captured[0].ToString() -match 'Traceback'
    ) {
        throw 'The real backend did not produce a structured ErrorRecord.'
    }

    $invalid = @()
    Get-ADUser -Identity 'CN=Alice,DC=example,DC=com' -Server dc1 -Properties doesNotExist `
        -ErrorAction SilentlyContinue -ErrorVariable invalid
    if ($invalid.Count -ne 1 -or $invalid[0].FullyQualifiedErrorId -notlike 'SambaAD.InvalidProperty*') {
        throw 'A property the schema does not define was not refused.'
    }
    Write-Output 'PowerShell composition tests passed.'
} finally {
    Remove-Item -LiteralPath ($temporary + '.cmd') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
}
