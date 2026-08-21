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
    [Diagnostics.CodeAnalysis.SuppressMessageAttribute(
        'PSUseShouldProcessForStateChangingFunctions', '',
        Justification = 'Builds an ErrorRecord in memory; changes no system state.')]
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

# Runs one write operation, but only once ShouldProcess has agreed, so -WhatIf
# and -Confirm are honoured before anything reaches the backend. -WhatIf stops
# here, in PowerShell: the backend is never started for a run that must not act.
function Invoke-SambaADWrite {
    [Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSShouldProcess', '',
        Justification = 'ShouldProcess is the calling cmdlet''s; this helper delegates to it.')]
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [System.Management.Automation.PSCmdlet]$Caller,

        [Parameter(Mandatory)]
        [string]$Operation,

        [Parameter(Mandatory)]
        [string]$Target,

        [Parameter(Mandatory)]
        [string]$Action,

        [Parameter(Mandatory)]
        [hashtable]$Parameters,

        [Parameter()]
        [switch]$PassThru
    )

    if (-not $Caller.ShouldProcess($Target, $Action)) {
        return
    }
    $request = @{ version = 1; operation = $Operation; parameters = $Parameters }
    $response = Invoke-SambaADBackend -Request $request
    if (-not $response.ok) {
        $Caller.WriteError((New-SambaADErrorRecord $response.error))
        return
    }
    if ($PassThru) {
        $result = [pscustomobject]$response.result.properties
        $result.PSObject.TypeNames.Insert(0, [string]$response.result.type)
        Write-Output $result
    }
}

# Creates one user. The attributes the backend writes are assembled here.
function New-ADUser {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
    param(
        [Parameter(Mandatory, Position = 0)]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter()]
        [string]$SamAccountName,

        [Parameter()]
        [string]$UserPrincipalName,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER,

        [Parameter()]
        [switch]$PassThru
    )

    process {
        $attributes = @{ objectClass = @('user') }
        if ($SamAccountName) { $attributes['sAMAccountName'] = @($SamAccountName) }
        if ($UserPrincipalName) { $attributes['userPrincipalName'] = @($UserPrincipalName) }
        Invoke-SambaADWrite -Caller $PSCmdlet -Operation 'new_ad_object' -Target $Identity `
            -Action 'Create user' -PassThru:$PassThru -Parameters @{
                identity = $Identity; server = $Server; attributes = $attributes
            }
    }
}

# Creates one group.
function New-ADGroup {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
    param(
        [Parameter(Mandatory, Position = 0)]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter()]
        [string]$SamAccountName,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER,

        [Parameter()]
        [switch]$PassThru
    )

    process {
        $attributes = @{ objectClass = @('group') }
        if ($SamAccountName) { $attributes['sAMAccountName'] = @($SamAccountName) }
        Invoke-SambaADWrite -Caller $PSCmdlet -Operation 'new_ad_object' -Target $Identity `
            -Action 'Create group' -PassThru:$PassThru -Parameters @{
                identity = $Identity; server = $Server; attributes = $attributes
            }
    }
}

# Creates one organizational unit.
function New-ADOrganizationalUnit {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
    param(
        [Parameter(Mandatory, Position = 0)]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER,

        [Parameter()]
        [switch]$PassThru
    )

    process {
        Invoke-SambaADWrite -Caller $PSCmdlet -Operation 'new_ad_object' -Target $Identity `
            -Action 'Create organizational unit' -PassThru:$PassThru -Parameters @{
                identity = $Identity; server = $Server
                attributes = @{ objectClass = @('organizationalUnit') }
            }
    }
}

# Replaces or clears the named attributes of one object.
function Set-ADObject {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline)]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter(Mandatory)]
        [hashtable]$Replace,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER,

        [Parameter()]
        [switch]$PassThru
    )

    process {
        Invoke-SambaADWrite -Caller $PSCmdlet -Operation 'set_ad_object' -Target $Identity `
            -Action 'Modify object' -PassThru:$PassThru -Parameters @{
                identity = $Identity; server = $Server; attributes = $Replace
            }
    }
}

# Deletes one object. On this Samba version the deletion cannot be faithfully
# undone; the confirmation prompt says so, per docs/deletion.md.
function Remove-ADObject {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline)]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER
    )

    process {
        $warning = "Delete $Identity. This cannot be faithfully undone: mail, name " +
            'attributes and every group membership are lost, and reanimating the ' +
            'tombstone restores only an empty shell. Take a samba-domain-backup first.'
        Invoke-SambaADWrite -Caller $PSCmdlet -Operation 'remove_ad_object' -Target $warning `
            -Action 'Remove object' -Parameters @{ identity = $Identity; server = $Server }
    }
}

# Adds one member to a group, and does nothing if it is already a member.
function Add-ADGroupMember {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
    param(
        [Parameter(Mandatory, Position = 0)]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter(Mandatory, Position = 1)]
        [ValidateNotNullOrEmpty()]
        [string]$Member,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER
    )

    process {
        Invoke-SambaADWrite -Caller $PSCmdlet -Operation 'add_ad_group_member' `
            -Target "$Member in $Identity" -Action 'Add group member' -Parameters @{
                identity = $Identity; member = $Member; server = $Server
            }
    }
}

# Removes one member from a group, and does nothing if it is already absent.
function Remove-ADGroupMember {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
    param(
        [Parameter(Mandatory, Position = 0)]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter(Mandatory, Position = 1)]
        [ValidateNotNullOrEmpty()]
        [string]$Member,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER
    )

    process {
        Invoke-SambaADWrite -Caller $PSCmdlet -Operation 'remove_ad_group_member' `
            -Target "$Member in $Identity" -Action 'Remove group member' -Parameters @{
                identity = $Identity; member = $Member; server = $Server
            }
    }
}

# Enables one account by clearing the disabled bit of userAccountControl.
function Enable-ADAccount {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline)]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER
    )

    process {
        Invoke-SambaADWrite -Caller $PSCmdlet -Operation 'enable_ad_account' -Target $Identity `
            -Action 'Enable account' -Parameters @{ identity = $Identity; server = $Server }
    }
}

# Disables one account by setting the disabled bit of userAccountControl.
function Disable-ADAccount {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline)]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER
    )

    process {
        Invoke-SambaADWrite -Caller $PSCmdlet -Operation 'disable_ad_account' -Target $Identity `
            -Action 'Disable account' -Parameters @{ identity = $Identity; server = $Server }
    }
}

# Sets an account's password. The SecureString is converted as late as possible
# and handed to the backend inside the request, which crosses on standard input,
# so the secret never appears on a command line or in the environment.
function Set-ADAccountPassword {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline)]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter(Mandatory)]
        [System.Security.SecureString]$NewPassword,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER
    )

    process {
        if (-not $PSCmdlet.ShouldProcess($Identity, 'Set account password')) {
            return
        }
        $plain = [System.Net.NetworkCredential]::new('', $NewPassword).Password
        try {
            $request = @{
                version = 1
                operation = 'set_ad_account_password'
                parameters = @{ identity = $Identity; server = $Server; password = $plain }
            }
            $response = Invoke-SambaADBackend -Request $request
        } finally {
            $plain = $null
        }
        if (-not $response.ok) {
            $PSCmdlet.WriteError((New-SambaADErrorRecord $response.error))
        }
    }
}

# Moves one object to a new parent.
function Move-ADObject {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline)]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string]$TargetPath,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER
    )

    process {
        $leaf = ($Identity -split '(?<!\\),', 2)[0]
        $newDn = "$leaf,$TargetPath"
        Invoke-SambaADWrite -Caller $PSCmdlet -Operation 'rename_ad_object' -Target $Identity `
            -Action "Move to $TargetPath" -Parameters @{
                identity = $Identity; new_dn = $newDn; server = $Server
            }
    }
}

# Renames one object's leaf, keeping it under the same parent.
function Rename-ADObject {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
    param(
        [Parameter(Mandatory, Position = 0, ValueFromPipeline)]
        [ValidateNotNullOrEmpty()]
        [string]$Identity,

        [Parameter(Mandatory, Position = 1)]
        [ValidateNotNullOrEmpty()]
        [string]$NewName,

        [Parameter()]
        [string]$Server = $env:SAMBA_AD_SERVER
    )

    process {
        $parent = ($Identity -split '(?<!\\),', 2)[1]
        $newDn = "CN=$NewName,$parent"
        Invoke-SambaADWrite -Caller $PSCmdlet -Operation 'rename_ad_object' -Target $Identity `
            -Action "Rename to $NewName" -Parameters @{
                identity = $Identity; new_dn = $newDn; server = $Server
            }
    }
}

Export-ModuleMember -Function @(
    'Get-ADUser',
    'Get-ADComputer',
    'Get-ADGroup',
    'Get-ADObject',
    'New-ADUser',
    'New-ADGroup',
    'New-ADOrganizationalUnit',
    'Set-ADObject',
    'Remove-ADObject',
    'Add-ADGroupMember',
    'Remove-ADGroupMember',
    'Enable-ADAccount',
    'Disable-ADAccount',
    'Set-ADAccountPassword',
    'Move-ADObject',
    'Rename-ADObject'
)
