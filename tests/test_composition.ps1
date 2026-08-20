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
    $user = Get-ADUser -Identity 'CN=Alice,DC=example,DC=com' -Server dc1
    if ($user.PSObject.TypeNames[0] -ne 'SambaAD.User') {
        throw 'The real backend did not return a SambaAD.User object.'
    }
    if ($user.DistinguishedName -ne 'CN=Alice,DC=example,DC=com') {
        throw 'The real backend did not carry the requested identity.'
    }
    if ($user.Name -ne [char]0x41 + 'nn' + [char]0xE9 + 'e') {
        throw "The UTF-8 boundary corrupted a non-ASCII value: $($user.Name)"
    }
    if ($user.Server -ne 'dc1') {
        throw 'The real backend did not pass -Server through to the client.'
    }
    $captured = @()
    Get-ADUser -Identity missing -Server dc1 -ErrorAction SilentlyContinue `
        -ErrorVariable captured
    if (
        $captured.Count -ne 1 -or
        [string]::IsNullOrEmpty($captured[0].FullyQualifiedErrorId) -or
        $captured[0].FullyQualifiedErrorId -notlike 'SambaAD.ObjectNotFound*' -or
        $captured[0].CategoryInfo.Category -ne 'ObjectNotFound' -or
        $captured[0].TargetObject -ne 'missing' -or
        $captured[0].ToString() -match 'Traceback'
    ) {
        throw 'The real backend did not produce a structured ErrorRecord.'
    }
    Write-Output 'PowerShell composition tests passed.'
} finally {
    Remove-Item -LiteralPath ($temporary + '.cmd') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
}
