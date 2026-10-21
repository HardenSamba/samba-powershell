Set-StrictMode -Version Latest

$script:BackendCommand = if ($env:SAMBA_POWERSHELL_BACKEND) {
    $env:SAMBA_POWERSHELL_BACKEND
} else {
    'samba-ad-backend'
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

# Runs one isolated backend request and returns its JSON response envelope,
# or, for a backend that cannot start or answers outside the protocol, the
# typed ErrorRecord to report. Nothing here throws on those paths: a caught
# exception would still land in the caller's -ErrorVariable beside the record.
# The backend's standard error goes to the debug stream, not the message.
function Invoke-SambaADBackend {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [hashtable]$Request
    )

    if (-not (Get-Command -Name $script:BackendCommand -CommandType Application `
            -ErrorAction Ignore)) {
        return New-SambaADFailure -ErrorId 'SambaAD.BackendUnavailable' `
            -Category ResourceUnavailable `
            -Message "The backend '$script:BackendCommand' was not found or is not executable."
    }
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $script:BackendCommand
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
        if (-not $process.Start()) {
            throw 'The backend process did not start.'
        }
        $outputTask = $process.StandardOutput.ReadToEndAsync()
        $diagnosticTask = $process.StandardError.ReadToEndAsync()
        $process.StandardInput.WriteLine(($Request | ConvertTo-Json -Compress -Depth 8))
        $process.StandardInput.Close()
        $process.WaitForExit()
        $output = $outputTask.GetAwaiter().GetResult()
        $diagnostic = $diagnosticTask.GetAwaiter().GetResult()
        $exitCode = $process.ExitCode
    } catch {
        return New-SambaADFailure -ErrorId 'SambaAD.BackendUnavailable' `
            -Category ResourceUnavailable `
            -Message "Unable to run '$script:BackendCommand': $($_.Exception.Message)"
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
    return $output | ConvertFrom-Json -Depth 8
}

# Names what is wrong with a backend answer, or returns nothing when it is a
# version 1 envelope whose ok flag agrees with the exit code.
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
    $response = $Output | ConvertFrom-Json -Depth 8
    if (
        $response -isnot [pscustomobject] -or
        -not $response.PSObject.Properties['version'] -or
        -not $response.PSObject.Properties['ok'] -or
        $response.version -ne 1 -or
        $response.ok -isnot [bool]
    ) {
        return 'invalid envelope'
    }
    $expectedExitCode = if ($response.ok) { 0 } else { 1 }
    if ($ExitCode -ne $expectedExitCode) {
        return "exit code $ExitCode"
    }
}

# Converts a backend error envelope into a native PowerShell ErrorRecord.
function New-SambaADErrorRecord {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [pscustomobject]$ErrorEnvelope
    )

    $category = [System.Management.Automation.ErrorCategory]::NotSpecified
    try {
        $category = [System.Enum]::Parse(
            [System.Management.Automation.ErrorCategory],
            [string]$ErrorEnvelope.category,
            $true
        )
    } catch {
        $category = [System.Management.Automation.ErrorCategory]::NotSpecified
    }
    $exception = [System.InvalidOperationException]::new(
        [string]$ErrorEnvelope.message
    )
    return [System.Management.Automation.ErrorRecord]::new(
        $exception,
        [string]$ErrorEnvelope.error_id,
        $category,
        $ErrorEnvelope.target
    )
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
