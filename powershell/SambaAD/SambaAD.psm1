Set-StrictMode -Version Latest

$script:BackendCommand = if ($env:SAMBA_POWERSHELL_BACKEND) {
    $env:SAMBA_POWERSHELL_BACKEND
} else {
    'samba-ad-backend'
}

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

# Whether the system can execute a file: on Linux at least one execute bit, so
# a backend missing it is refused before Start() throws, which would leave an
# exception in the caller's -ErrorVariable beside the record.
function Test-SambaADExecutable {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    if ($IsWindows) {
        return $true
    }
    $execute = [System.IO.UnixFileMode]'UserExecute, GroupExecute, OtherExecute'
    return ([System.IO.File]::GetUnixFileMode($Path) -band $execute) -ne 0
}

# Runs one isolated backend request and returns its JSON response envelope,
# or, for a backend that cannot start or answers outside the protocol, the
# typed ErrorRecord to report. Those paths return the record rather than throw
# it, because a caught exception would still land in the caller's
# -ErrorVariable; only a backend the system finds executable yet cannot start,
# such as a script whose interpreter is missing, leaves the runtime's own record
# there too. The backend's standard error goes to the debug stream.
function Invoke-SambaADBackend {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [hashtable]$Request
    )

    $command = Get-Command -Name $script:BackendCommand -CommandType Application `
        -ErrorAction Ignore | Select-Object -First 1
    if (-not $command -or -not (Test-SambaADExecutable -Path $command.Source)) {
        return New-SambaADFailure -ErrorId 'SambaAD.BackendUnavailable' `
            -Category ResourceUnavailable `
            -Message "The backend '$script:BackendCommand' was not found or is not executable."
    }
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $command.Source
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

    try {
        $process.Start() | Out-Null
        $outputTask = $process.StandardOutput.ReadToEndAsync()
        $diagnosticTask = $process.StandardError.ReadToEndAsync()
        $process.StandardInput.WriteLine(($Request | ConvertTo-Json -Compress -Depth 8))
        $process.StandardInput.Close()
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
    return $output | ConvertFrom-Json -Depth 8 @script:JsonDateOptions
}

# Names what is wrong with a backend answer, or returns nothing when it is a
# version 1 envelope whose ok flag agrees with the exit code and whose result or
# error carries every field the cmdlets read. It parses into a hashtable, which,
# unlike an object, accepts property names that differ only in case.
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
    $response = $Output | ConvertFrom-Json -AsHashtable -Depth 8
    if (
        $response -isnot [System.Collections.IDictionary] -or
        $response['version'] -ne 1 -or
        $response['ok'] -isnot [bool]
    ) {
        return 'invalid envelope'
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
        $failure['error_id'] -isnot [string]
    ) {
        return 'invalid error'
    }
}

# Names what is wrong with a success envelope's result, or returns nothing: it
# needs a type and properties, and property names that differ by more than case.
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
        $Result['properties'] -isnot [System.Collections.IDictionary]
    ) {
        return 'invalid result'
    }
    $names = @($Result['properties'].Keys | ForEach-Object { ([string]$_).ToLowerInvariant() })
    if (@($names | Select-Object -Unique).Count -ne $names.Count) {
        return 'property names that differ only in case'
    }
}

# Converts a backend error envelope into a native PowerShell ErrorRecord. The
# category and target are optional, and an unknown category is NotSpecified.
function New-SambaADErrorRecord {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [pscustomobject]$ErrorEnvelope
    )

    $fields = $ErrorEnvelope.PSObject.Properties
    $category = [System.Management.Automation.ErrorCategory]::NotSpecified
    $parsed = $null
    if ($fields['category'] -and [System.Enum]::TryParse(
            [System.Management.Automation.ErrorCategory],
            [string]$fields['category'].Value, $true, [ref]$parsed)) {
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
        [string]$this.DistinguishedName
    }
    Write-Output $result
}

# Retrieves one user by distinguished name, GUID, SID or account name through
# the Samba ADWS endpoint. A piped object binds by its DistinguishedName.
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
# the Samba ADWS endpoint. A piped object binds by its DistinguishedName.
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
