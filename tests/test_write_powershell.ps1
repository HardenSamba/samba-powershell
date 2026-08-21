param(
    [Parameter(Mandatory)]
    [string]$PythonPath
)

# Proves the write cmdlets honour -WhatIf and -Confirm before anything reaches
# the backend, and that -Confirm:$false silences a destructive prompt. The
# backend here is a fixture that RAISES on any call, so a -WhatIf run that
# succeeds proves nothing was started.

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$fixture = Join-Path $PSScriptRoot 'fixtures/raising_backend.py'
$temporary = Join-Path ([System.IO.Path]::GetTempPath()) (
    'samba-ad-write-' + [System.Guid]::NewGuid().ToString('N')
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
    Import-Module SambaAD -Force

    $dn = 'CN=Probe,CN=Users,DC=example,DC=com'

    # -WhatIf must not start the backend: the fixture raises if it is called.
    New-ADUser -Identity $dn -WhatIf
    Set-ADObject -Identity $dn -Replace @{ description = 'x' } -WhatIf
    Remove-ADObject -Identity $dn -WhatIf
    Enable-ADAccount -Identity $dn -WhatIf
    Add-ADGroupMember -Identity 'CN=G,DC=example,DC=com' -Member $dn -WhatIf
    Move-ADObject -Identity $dn -TargetPath 'OU=Staff,DC=example,DC=com' -WhatIf

    # A destructive command with -Confirm:$false does reach the backend, which
    # then raises: catching that failure proves the prompt was skipped and the
    # call attempted, rather than silently short-circuited.
    $reached = $false
    try {
        Remove-ADObject -Identity $dn -Confirm:$false -ErrorAction Stop
    } catch {
        $reached = $true
    }
    if (-not $reached) {
        throw 'Remove-ADObject -Confirm:$false did not attempt the backend call.'
    }

    Write-Output 'PowerShell write ShouldProcess tests passed.'
} finally {
    Remove-Item -LiteralPath ($temporary + '.cmd') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
    Remove-Module SambaAD -Force -ErrorAction SilentlyContinue
}
