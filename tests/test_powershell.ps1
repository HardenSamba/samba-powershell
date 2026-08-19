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
    Write-Output 'PowerShell boundary tests passed.'
} finally {
    Remove-Item -LiteralPath ($temporary + '.cmd') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
}
