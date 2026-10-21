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
        $captured[0].FullyQualifiedErrorId -notlike 'SambaAD.ObjectNotFound*' -or
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

    $malformedCases = 'noresult', 'noerror', 'casedupe', 'envdupe', 'emptykey', 'dtnull',
        'typeempty', 'nodn', 'stringversion'
    foreach ($malformed in $malformedCases) {
        $shapeless = @()
        $leaked = Get-ADUser -Identity $malformed -Server dc1 -ErrorAction SilentlyContinue `
            -ErrorVariable shapeless
        if ($null -ne $leaked -or $shapeless.Count -ne 1 -or
                $shapeless[0].FullyQualifiedErrorId -notlike 'SambaAD.ProtocolError*') {
            throw "A malformed envelope ($malformed) did not give exactly one ProtocolError."
        }
        $stopped = $false
        try {
            Get-ADUser -Identity $malformed -Server dc1 -ErrorAction Stop | Out-Null
        } catch {
            $stopped = $_.FullyQualifiedErrorId -like 'SambaAD.ProtocolError*'
        }
        if (-not $stopped) {
            throw "Under -ErrorAction Stop, a malformed envelope ($malformed) gave another error."
        }
    }
    $deep = @()
    $nested = Get-ADUser -Identity deep -Server dc1 -ErrorAction SilentlyContinue -ErrorVariable deep
    if ($deep.Count -ne 0 -or $nested.DistinguishedName -ne 'a') {
        throw 'A deeply nested but valid answer was not read.'
    }
    $categorised = @()
    Get-ADUser -Identity numcategory -Server dc1 -ErrorAction SilentlyContinue `
        -ErrorVariable categorised
    if (
        $categorised.Count -ne 1 -or
        $categorised[0].FullyQualifiedErrorId -notlike 'SambaAD.Fake*' -or
        $categorised[0].CategoryInfo.Category -ne 'NotSpecified' -or
        $categorised[0].Exception.Message -ne '2026-01-01T10:00:00Z'
    ) {
        throw 'A numeric category or a date-shaped message was not kept as sent.'
    }

    if ($user.whenCreated -isnot [datetime]) {
        throw 'A property the backend lists as a time did not arrive as a DateTime.'
    }
    if ((Get-Command ConvertFrom-Json).Parameters.ContainsKey('DateKind') -and
            $user.info -isnot [string]) {
        throw 'Text that only looks like a date did not stay text.'
    }
    $bound = $false
    try {
        Get-ADUser -Identity 'CN=Alice,DC=example,DC=com' -Server dc1 -Properties $null
    } catch {
        $bound = $_.FullyQualifiedErrorId -like 'ParameterArgumentValidationError*'
    }
    if (-not $bound) {
        throw 'A null -Properties was not refused at parameter binding, as on Windows.'
    }

    if (-not $IsWindows) {
        $early = $temporary + '-exits-early'
        Set-Content -LiteralPath $early -Value (
            "#!/bin/sh`necho 'ModuleNotFoundError: no module named samba_powershell' >&2`nexit 1"
        ) -Encoding utf8NoBOM
        & chmod 700 $early
        $env:SAMBA_POWERSHELL_BACKEND = $early
        Import-Module SambaAD -Force
        $quick = @()
        $debugRecords = Get-ADUser -Identity 'CN=Alice,DC=example,DC=com' -Server dc1 -Debug `
            -ErrorAction SilentlyContinue -ErrorVariable quick 5>&1
        Remove-Item -LiteralPath $early -Force
        $diagnostics = @($debugRecords | Where-Object { "$_" -like '*ModuleNotFoundError*' })
        if ($quick.Count -ne 1 -or $quick[0].FullyQualifiedErrorId -notlike 'SambaAD.ProtocolError*' -or
                $diagnostics.Count -ne 1) {
            throw 'A backend exiting before it reads the request lost its diagnostic or its id.'
        }

        $dangling = $temporary + '-dangling'
        & ln -s ($temporary + '-nowhere') $dangling
        $env:SAMBA_POWERSHELL_BACKEND = $dangling
        Import-Module SambaAD -Force
        $broken = @()
        Get-ADUser -Identity 'CN=Alice,DC=example,DC=com' -Server dc1 `
            -ErrorAction SilentlyContinue -ErrorVariable broken
        Remove-Item -LiteralPath $dangling -Force
        if ($broken.Count -ne 1 -or $broken[0].FullyQualifiedErrorId -notlike 'SambaAD.BackendUnavailable*') {
            throw 'A dangling backend link did not give exactly one BackendUnavailable.'
        }

        $plain = $temporary + '-not-executable'
        Set-Content -LiteralPath $plain -Value "#!/bin/sh`nexit 0" -Encoding utf8NoBOM
        & chmod 600 $plain
        $env:SAMBA_POWERSHELL_BACKEND = $plain
        Import-Module SambaAD -Force
        $unrunnable = @()
        Get-ADUser -Identity 'CN=Alice,DC=example,DC=com' -Server dc1 `
            -ErrorAction SilentlyContinue -ErrorVariable unrunnable
        Remove-Item -LiteralPath $plain -Force
        if ($unrunnable.Count -ne 1 -or $unrunnable[0].FullyQualifiedErrorId -notlike 'SambaAD.BackendUnavailable*') {
            throw 'A backend without an execute bit did not give exactly one BackendUnavailable.'
        }
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
