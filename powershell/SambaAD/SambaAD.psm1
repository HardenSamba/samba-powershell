Set-StrictMode -Version Latest

$script:BackendCommand = if ($env:SAMBA_POWERSHELL_BACKEND) {
    $env:SAMBA_POWERSHELL_BACKEND
} else {
    'samba-ad-backend'
}

# Runs one isolated backend request and returns its JSON response envelope.
function Invoke-SambaADBackend {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [hashtable]$Request
    )

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
        throw "Unable to run '$script:BackendCommand': $($_.Exception.Message)"
    } finally {
        $process.Dispose()
    }

    if ([string]::IsNullOrWhiteSpace($output)) {
        throw "The backend returned no JSON response. $diagnostic"
    }
    try {
        $response = $output | ConvertFrom-Json -Depth 8
    } catch {
        throw 'The backend returned an invalid JSON response.'
    }
    if (
        -not $response.PSObject.Properties['version'] -or
        -not $response.PSObject.Properties['ok'] -or
        $response.version -ne 1 -or
        $response.ok -isnot [bool]
    ) {
        throw 'The backend returned an invalid protocol envelope.'
    }
    $expectedExitCode = if ($response.ok) { 0 } else { 1 }
    if ($exitCode -ne $expectedExitCode) {
        throw "The backend response did not match exit code $exitCode. $diagnostic"
    }
    return $response
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
    if (-not $response.ok) {
        $Caller.WriteError((New-SambaADErrorRecord $response.error))
        return
    }
    $result = [pscustomobject]$response.result.properties
    $result.PSObject.TypeNames.Insert(0, [string]$response.result.type)
    Write-Output $result
}

# Retrieves one user by distinguished name through the Samba ADWS endpoint.
function Get-ADUser {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline)]
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

# Retrieves one computer by distinguished name through the Samba ADWS endpoint.
function Get-ADComputer {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline)]
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

# Retrieves one group by distinguished name through the Samba ADWS endpoint.
function Get-ADGroup {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline)]
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

# Retrieves one object of any class by distinguished name.
function Get-ADObject {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline)]
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
