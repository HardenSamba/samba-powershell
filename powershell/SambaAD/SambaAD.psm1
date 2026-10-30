Set-StrictMode -Version Latest

# Install-Module copies the module folder and nothing else, so a module from the
# gallery holds its backend beside itself, and runs it through the interpreter
# the Debian Python packages install for, since unpacking drops execute bits. -E
# keeps a stray PYTHONPATH from loading code out of the current directory.
$script:BundledBackend = Join-Path $PSScriptRoot 'backend/samba_ad_backend.py'
$script:BackendArguments = @()
$script:BackendCommand = if ($env:SAMBA_POWERSHELL_BACKEND) {
    $env:SAMBA_POWERSHELL_BACKEND
} elseif ([System.IO.File]::Exists($script:BundledBackend)) {
    $script:BackendArguments = @('-B', '-E', $script:BundledBackend)
    '/usr/bin/python3'
} else {
    'samba-ad-backend'
}

# The backend path last found executable, so the test -x probe, a process of its
# own, runs once per session rather than once per object.
$script:RunnableBackend = $null

# ConvertFrom-Json turns any text shaped like a date into a DateTime. Where it
# can be told not to, PowerShell 7.5 onwards, only the properties the backend
# lists as times are converted, so a text attribute stays text.
$script:JsonDateOptions = if (
    (Get-Command -Name ConvertFrom-Json).Parameters.ContainsKey('DateKind')
) {
    @{ DateKind = 'String' }
} else {
    @{}
}

# Builds the ErrorRecord for a failure the backend could not describe itself,
# under a stable SambaAD identifier so a script can still tell failures apart.
function New-SambaADFailure {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$ErrorId,

        [Parameter(Mandatory)]
        [System.Management.Automation.ErrorCategory]$Category,

        [Parameter(Mandatory)]
        [string]$Message
    )

    $exception = [System.InvalidOperationException]::new($Message)
    return [System.Management.Automation.ErrorRecord]::new(
        $exception,
        $ErrorId,
        $Category,
        $script:BackendCommand
    )
}

# Whether the calling user may execute a file, asked the way execve judges it,
# through test -x: a missing execute bit, one only others hold, or a dangling
# link is refused before Start() can throw.
function Test-SambaADExecutable {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    if ($IsWindows -or -not [System.IO.File]::Exists('/usr/bin/test')) {
        return $true
    }
    $probeInfo = [System.Diagnostics.ProcessStartInfo]::new('/usr/bin/test')
    $probeInfo.ArgumentList.Add('-x')
    $probeInfo.ArgumentList.Add($Path)
    $probeInfo.UseShellExecute = $false
    $probe = [System.Diagnostics.Process]::Start($probeInfo)
    $probe.WaitForExit()
    $allowed = $probe.ExitCode -eq 0
    $probe.Dispose()
    return $allowed
}

# Runs one isolated backend request and returns its JSON response envelope,
# or, for a backend that cannot start or answers outside the protocol, the
# typed ErrorRecord to report. Those paths return the record rather than throw
# it, because a caught exception would still land in the caller's
# -ErrorVariable. The request is written without an API that throws, so a
# backend that exits before reading it is judged by its answer and its standard
# error, which goes to the debug stream. Only a backend the system finds
# executable yet cannot start, such as a script whose interpreter is missing,
# leaves the runtime's own record beside the module's.
function Invoke-SambaADBackend {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [hashtable]$Request
    )

    $command = Get-Command -Name $script:BackendCommand -CommandType Application `
        -ErrorAction Ignore | Select-Object -First 1
    if (-not $command -or ($script:RunnableBackend -ne $command.Source -and
            -not (Test-SambaADExecutable -Path $command.Source))) {
        return New-SambaADFailure -ErrorId 'SambaAD.BackendUnavailable' `
            -Category ResourceUnavailable `
            -Message "The backend '$script:BackendCommand' was not found or is not executable."
    }
    $script:RunnableBackend = $command.Source
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $command.Source
    foreach ($argument in $script:BackendArguments) {
        $startInfo.ArgumentList.Add($argument)
    }
    $startInfo.ArgumentList.Add('request')
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $utf8 = [System.Text.UTF8Encoding]::new($false)
    $startInfo.StandardInputEncoding = $utf8
    $startInfo.StandardOutputEncoding = $utf8
    $startInfo.StandardErrorEncoding = $utf8
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $payload = $utf8.GetBytes(($Request | ConvertTo-Json -Compress -Depth 8) + "`n")

    try {
        $process.Start() | Out-Null
        $outputTask = $process.StandardOutput.ReadToEndAsync()
        $diagnosticTask = $process.StandardError.ReadToEndAsync()
        $stdin = $process.StandardInput.BaseStream
        $writing = $stdin.WriteAsync($payload, 0, $payload.Length)
        $null = [System.Threading.Tasks.Task]::WhenAny($writing).GetAwaiter().GetResult()
        $null = $writing.Exception
        $closing = $stdin.DisposeAsync().AsTask()
        $null = [System.Threading.Tasks.Task]::WhenAny($closing).GetAwaiter().GetResult()
        $null = $closing.Exception
        $process.WaitForExit()
        $output = $outputTask.GetAwaiter().GetResult()
        $diagnostic = $diagnosticTask.GetAwaiter().GetResult()
        $exitCode = $process.ExitCode
    } catch {
        $reason = $_.Exception
        while ($reason.InnerException) {
            $reason = $reason.InnerException
        }
        return New-SambaADFailure -ErrorId 'SambaAD.BackendUnavailable' `
            -Category ResourceUnavailable `
            -Message "Unable to run '$script:BackendCommand': $($reason.Message)"
    } finally {
        $process.Dispose()
    }

    if (-not [string]::IsNullOrWhiteSpace($diagnostic)) {
        Write-Debug "samba-ad-backend standard error: $diagnostic"
    }
    $problem = Test-SambaADEnvelope -Output $output -ExitCode $exitCode
    if ($problem) {
        return New-SambaADFailure -ErrorId 'SambaAD.ProtocolError' -Category ProtocolError `
            -Message ("The backend answered outside the protocol ($problem); run the " +
                'cmdlet with -Debug to see its standard error.')
    }
    return $output | ConvertFrom-Json -NoEnumerate @script:JsonDateOptions
}

# Names what is wrong with a backend answer, or returns nothing when it is a
# version 1 envelope whose ok flag agrees with the exit code, whose names an
# object can hold, and whose result or error carries every field the cmdlets
# read. It parses into a hashtable, which, unlike an object, accepts property
# names that differ only in case, and parses exactly as the final read does.
function Test-SambaADEnvelope {
    [CmdletBinding()]
    param(
        [Parameter()]
        [AllowEmptyString()]
        [string]$Output,

        [Parameter(Mandatory)]
        [int]$ExitCode
    )

    if ([string]::IsNullOrWhiteSpace($Output)) {
        return 'no JSON response'
    }
    if (-not (Test-Json -Json $Output -ErrorAction Ignore)) {
        return 'invalid JSON'
    }
    $response = $Output | ConvertFrom-Json -AsHashtable -NoEnumerate @script:JsonDateOptions
    $version = if ($response -is [System.Collections.IDictionary]) { $response['version'] }
    if (
        $response -isnot [System.Collections.IDictionary] -or
        ($version -isnot [long] -and $version -isnot [int]) -or
        $version -ne 1 -or
        $response['ok'] -isnot [bool]
    ) {
        return 'invalid envelope'
    }
    $names = Test-SambaADKeys -Value $response
    if ($names) {
        return $names
    }
    $expectedExitCode = if ($response['ok']) { 0 } else { 1 }
    if ($ExitCode -ne $expectedExitCode) {
        return "exit code $ExitCode"
    }
    if ($response['ok']) {
        return Test-SambaADResult -Result $response['result']
    }
    $failure = $response['error']
    if (
        $failure -isnot [System.Collections.IDictionary] -or
        $failure['message'] -isnot [string] -or
        $failure['error_id'] -isnot [string] -or
        [string]::IsNullOrWhiteSpace($failure['error_id'])
    ) {
        return 'invalid error'
    }
}

# Names a property name no PowerShell object can hold anywhere in an answer,
# empty or equal to another but for case, or returns nothing. Only nested
# dictionaries and lists are walked; a scalar cannot hold a name.
function Test-SambaADKeys {
    [CmdletBinding()]
    param(
        [Parameter()]
        [AllowNull()]
        [object]$Value
    )

    $children = @()
    if ($Value -is [System.Collections.IDictionary]) {
        $seen = [System.Collections.Generic.HashSet[string]]::new(
            [System.StringComparer]::OrdinalIgnoreCase)
        foreach ($key in $Value.Keys) {
            if ([string]::IsNullOrEmpty([string]$key)) {
                return 'an empty property name'
            }
            if (-not $seen.Add([string]$key)) {
                return 'property names that differ only in case'
            }
        }
        $children = @($Value.Values)
    } elseif ($Value -is [System.Collections.IList]) {
        $children = @($Value)
    }
    foreach ($child in $children) {
        if ($child -is [System.Collections.IDictionary] -or $child -is [System.Collections.IList]) {
            $inner = Test-SambaADKeys -Value $child
            if ($inner) {
                return $inner
            }
        }
    }
}

# Names what is wrong with a success envelope's result, or returns nothing: it
# needs a type, properties with a DistinguishedName, and a datetimes list, if
# any, of property names.
function Test-SambaADResult {
    [CmdletBinding()]
    param(
        [Parameter()]
        [AllowNull()]
        [object]$Result
    )

    if (
        $Result -isnot [System.Collections.IDictionary] -or
        $Result['type'] -isnot [string] -or
        [string]::IsNullOrWhiteSpace($Result['type']) -or
        $Result['properties'] -isnot [System.Collections.IDictionary] -or
        $Result['properties']['DistinguishedName'] -isnot [string]
    ) {
        return 'invalid result'
    }
    if ($Result.Contains('datetimes')) {
        $times = $Result['datetimes']
        $bad = @($times | Where-Object { $_ -isnot [string] -or $_ -eq '' })
        if ($times -isnot [System.Collections.IList] -or $bad.Count) {
            return 'invalid datetimes'
        }
    }
}

# Converts a backend error envelope into a native PowerShell ErrorRecord. The
# category and target are optional, and a category that is not one defined
# name, a number or a combination included, is NotSpecified.
function New-SambaADErrorRecord {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [pscustomobject]$ErrorEnvelope
    )

    $fields = $ErrorEnvelope.PSObject.Properties
    $category = [System.Management.Automation.ErrorCategory]::NotSpecified
    $name = if ($fields['category']) { $fields['category'].Value } else { $null }
    $parsed = $null
    if (
        $name -is [string] -and $name -match '^[A-Za-z]+$' -and
        [System.Enum]::TryParse([System.Management.Automation.ErrorCategory], $name, $true,
            [ref]$parsed)
    ) {
        $category = $parsed
    }
    $target = if ($fields['target']) { $fields['target'].Value } else { $null }
    $exception = [System.InvalidOperationException]::new([string]$ErrorEnvelope.message)
    return [System.Management.Automation.ErrorRecord]::new(
        $exception,
        [string]$ErrorEnvelope.error_id,
        $category,
        $target
    )
}

# Turns the ISO 8601 text the backend sends for a time property into the local
# DateTime Windows shows, value by value; anything else is left as it is.
function ConvertTo-SambaADDateTime {
    [CmdletBinding()]
    param(
        [Parameter()]
        [AllowNull()]
        [object]$Value
    )

    if ($Value -is [System.Array]) {
        return , [object[]]@($Value | ForEach-Object { ConvertTo-SambaADDateTime -Value $_ })
    }
    $parsed = [System.DateTimeOffset]::MinValue
    if (
        $Value -is [string] -and
        [System.DateTimeOffset]::TryParse($Value, [cultureinfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::None, [ref]$parsed)
    ) {
        return $parsed.LocalDateTime
    }
    return $Value
}

# Runs one read operation and emits the typed object, or the backend's error.
# A script module reads $ErrorActionPreference from its own scope rather than
# the caller's, so the caller's preference is brought in unless -ErrorAction
# was given: 'Stop' set at the top of a script must stop on a missing object.
function Invoke-SambaADRead {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [System.Management.Automation.PSCmdlet]$Caller,

        [Parameter(Mandatory)]
        [string]$Operation,

        [Parameter(Mandatory)]
        [string]$Identity,

        [Parameter()]
        [string]$Server = '',

        [Parameter()]
        [string[]]$Properties = @()
    )

    if (-not $Caller.MyInvocation.BoundParameters.ContainsKey('ErrorAction')) {
        $ErrorActionPreference = $Caller.SessionState.PSVariable.GetValue(
            'ErrorActionPreference'
        )
    }
    $request = @{
        version = 1
        operation = $Operation
        parameters = @{
            identity = $Identity
            server = $Server
            properties = $Properties
        }
    }
    $response = Invoke-SambaADBackend -Request $request
    if ($response -is [System.Management.Automation.ErrorRecord]) {
        $Caller.WriteError($response)
        return
    }
    if (-not $response.ok) {
        $Caller.WriteError((New-SambaADErrorRecord $response.error))
        return
    }
    $result = $response.result.properties
    $times = $response.result.PSObject.Properties['datetimes']
    foreach ($name in @(if ($times) { $times.Value })) {
        $property = $result.PSObject.Properties[[string]$name]
        if ($property) {
            $property.Value = ConvertTo-SambaADDateTime -Value $property.Value
        }
    }
    $result.PSObject.TypeNames.Insert(0, [string]$response.result.type)
    $result | Add-Member -MemberType ScriptMethod -Name ToString -Force -Value {
        $dn = $this.PSObject.Properties['DistinguishedName']
        if ($dn) { [string]$dn.Value } else { '' }
    }
    Write-Output $result
}

# Retrieves one user by distinguished name, GUID, SID or account name through
# LDAP. A piped object binds by its DistinguishedName.
function Get-ADUser {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline, ValueFromPipelineByPropertyName)]
        [Alias('DistinguishedName')]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER,

        [Parameter()]
        [Alias('Property')]
        [ValidateNotNullOrEmpty()]
        [string[]]$Properties = @()
    )

    process {
        Invoke-SambaADRead -Caller $PSCmdlet -Operation 'get_ad_user' `
            -Identity $Identity -Server $Server -Properties $Properties
    }
}

# Retrieves one computer by distinguished name, GUID, SID or account name, the
# trailing '$' optional. A piped object binds by its DistinguishedName.
function Get-ADComputer {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline, ValueFromPipelineByPropertyName)]
        [Alias('DistinguishedName')]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER,

        [Parameter()]
        [Alias('Property')]
        [ValidateNotNullOrEmpty()]
        [string[]]$Properties = @()
    )

    process {
        Invoke-SambaADRead -Caller $PSCmdlet -Operation 'get_ad_computer' `
            -Identity $Identity -Server $Server -Properties $Properties
    }
}

# Retrieves one group by distinguished name, GUID, SID or account name through
# LDAP. A piped object binds by its DistinguishedName.
function Get-ADGroup {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline, ValueFromPipelineByPropertyName)]
        [Alias('DistinguishedName')]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER,

        [Parameter()]
        [Alias('Property')]
        [ValidateNotNullOrEmpty()]
        [string[]]$Properties = @()
    )

    process {
        Invoke-SambaADRead -Caller $PSCmdlet -Operation 'get_ad_group' `
            -Identity $Identity -Server $Server -Properties $Properties
    }
}

# Retrieves one object of any class by distinguished name, GUID or SID. A
# piped object binds by its DistinguishedName.
function Get-ADObject {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline, ValueFromPipelineByPropertyName)]
        [Alias('DistinguishedName')]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER,

        [Parameter()]
        [Alias('Property')]
        [ValidateNotNullOrEmpty()]
        [string[]]$Properties = @()
    )

    process {
        Invoke-SambaADRead -Caller $PSCmdlet -Operation 'get_ad_object' `
            -Identity $Identity -Server $Server -Properties $Properties
    }
}

Export-ModuleMember -Function @(
    'Get-ADUser',
    'Get-ADComputer',
    'Get-ADGroup',
    'Get-ADObject'
)
