# The acceptance boundary: the module, the real backend and the real python-ldap
# against a real domain controller, with a Kerberos ticket obtained beforehand.
# Nothing is written to the directory. tests/README.md says how to run it.
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Server,

    [Parameter(Mandatory)]
    [string]$SamAccountName,

    [Parameter(Mandatory)]
    [string]$ComputerName,

    [Parameter()]
    [string]$BackendCommand,

    [Parameter()]
    [string]$IpAddress
)

$ErrorActionPreference = 'Stop'
$script:failures = [System.Collections.Generic.List[string]]::new()
$script:checks = 0

# Records one check, and keeps going so one run reports every failure.
function Assert-Live {
    param([string]$Name, $Condition, [string]$Detail = '')
    $script:checks++
    if ($Condition -isnot [bool] -or -not $Condition) {
        $script:failures.Add("$Name $Detail")
    }
}

# Runs one failing read and returns the ErrorRecord it stopped with, or nothing
# if it did not fail.
function Get-LiveError {
    param([scriptblock]$Read)
    try {
        & $Read | Out-Null
    } catch {
        return $_
    }
    return $null
}

# Checks a failure's identifier and category, and that no traceback leaks.
function Assert-LiveError {
    param([string]$Name, [scriptblock]$Read, [string]$ErrorId, [string]$Category, [string]$Text = '')
    $record = Get-LiveError -Read $Read
    Assert-Live $Name ($null -ne $record -and
        $record.FullyQualifiedErrorId -like "$ErrorId*" -and
        [string]$record.CategoryInfo.Category -eq $Category -and
        $record.ToString() -notmatch 'Traceback' -and
        $record.ToString() -like "*$Text*") "got: $record / $($record.FullyQualifiedErrorId)"
}

if ($BackendCommand) {
    $env:SAMBA_POWERSHELL_BACKEND = $BackendCommand
}
Import-Module (Join-Path (Split-Path -Parent $PSScriptRoot) 'powershell/SambaAD/SambaAD.psd1') -Force

$user = Get-ADUser $SamAccountName -Server $Server
$dn = $user.DistinguishedName
$domain = ($dn -split ',' | Where-Object { $_ -like 'DC=*' }) -join ','
Assert-Live 'user type' ($user.PSObject.TypeNames[0] -eq 'SambaAD.User')
Assert-Live 'user name' ($user.SamAccountName -eq $SamAccountName)
Assert-Live 'user SID text' ($user.SID -match '^S-1-5-21-\d+-\d+-\d+-\d+$') "got $($user.SID)"
Assert-Live 'user GUID text' ($user.ObjectGUID -match '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$') "got $($user.ObjectGUID)"
Assert-Live 'user Enabled' ($user.Enabled -is [bool])
Assert-Live 'user class' ($user.ObjectClass -eq 'user')

Assert-Live 'by DN' ((Get-ADUser $dn -Server $Server).ObjectGUID -eq $user.ObjectGUID)
Assert-Live 'by SID' ((Get-ADUser $user.SID -Server $Server).DistinguishedName -eq $dn)
Assert-Live 'by GUID' ((Get-ADUser $user.ObjectGUID -Server $Server).DistinguishedName -eq $dn)
Assert-Live 'by pipeline' (($user | Get-ADUser -Server $Server).DistinguishedName -eq $dn)
$env:SAMBA_AD_SERVER = $Server
Assert-Live 'server from the environment' ((Get-ADUser $SamAccountName).DistinguishedName -eq $dn)
Remove-Item Env:SAMBA_AD_SERVER

$typed = Get-ADUser $SamAccountName -Server $Server -Properties memberOf, whenCreated, logonCount,
    pwdLastSet, tokenGroups, msDS-KeyVersionNumber, canonicalName, isCriticalSystemObject
Assert-Live 'whenCreated type' ($typed.whenCreated -is [datetime])
Assert-Live 'logonCount type' ($typed.logonCount -is [long] -or $typed.logonCount -is [int])
Assert-Live 'memberOf shape' ($null -eq $typed.memberOf -or $typed.memberOf -is [array])
Assert-Live 'tokenGroups decoded' (@($typed.tokenGroups).Count -gt 0 -and
    @($typed.tokenGroups | Where-Object { $_ -notmatch '^S-1-' }).Count -eq 0) "got $($typed.tokenGroups)"
Assert-Live 'constructed attribute' ($typed.'msDS-KeyVersionNumber' -is [long] -or $typed.'msDS-KeyVersionNumber' -is [int])
Assert-Live 'canonicalName' (@($typed.canonicalName)[0] -like '*/*')
Assert-Live 'boolean syntax' ($null -eq $typed.isCriticalSystemObject -or $typed.isCriticalSystemObject -is [bool])

$whole = Get-ADUser $SamAccountName -Server $Server -Properties *
Assert-Live 'wildcard reads the object' ($whole.PSObject.Properties.Name -contains 'uSNCreated')
Assert-Live 'wildcard decodes binary' ($whole.objectSid -eq $user.SID) "got $($whole.objectSid)"
$named = Get-ADUser $SamAccountName -Server $Server -Properties *, tokenGroups
Assert-Live 'wildcard with a constructed name' (@($named.tokenGroups).Count -gt 0)

$group = Get-ADGroup 'Domain Admins' -Server $Server -Properties member
Assert-Live 'group type' ($group.PSObject.TypeNames[0] -eq 'SambaAD.Group')
Assert-Live 'group category' ($group.GroupCategory -eq 'Security')
Assert-Live 'group scope' ($group.GroupScope -eq 'Global')
Assert-Live 'group members' (@($group.member).Count -gt 0)
$members = @($group.member | Get-ADUser -Server $Server)
Assert-Live 'members piped' ($members.Count -eq @($group.member).Count)
$builtin = Get-ADGroup 'S-1-5-32-544' -Server $Server
Assert-Live 'a SID whose bytes are valid UTF-8' ($builtin.SID -eq 'S-1-5-32-544') "got $($builtin.SID)"

$computer = Get-ADComputer $ComputerName -Server $Server
Assert-Live 'computer type' ($computer.PSObject.TypeNames[0] -eq 'SambaAD.Computer')
Assert-Live 'computer by account name' ((Get-ADComputer "$ComputerName`$" -Server $Server).ObjectGUID -eq $computer.ObjectGUID)

$root = Get-ADObject $domain -Server $Server
Assert-Live 'domain root' ($root.ObjectClass -eq 'domainDNS')
$schema = "CN=User,CN=Schema,CN=Configuration,$domain"
$class = Get-ADObject $schema -Server $Server -Properties objectClassCategory, schemaIDGUID, *
Assert-Live 'schema object integer' ($class.objectClassCategory -is [long] -or $class.objectClassCategory -is [int]) "got $($class.objectClassCategory)"
Assert-Live 'unknown binary is base64' ($class.schemaIDGUID -match '^[A-Za-z0-9+/]+=*$') "got $($class.schemaIDGUID)"
$secured = Get-ADObject $domain -Server $Server -Properties nTSecurityDescriptor
Assert-Live 'security descriptor without SACL rights' ($secured.nTSecurityDescriptor -match '^[A-Za-z0-9+/]+=*$') "got $($secured.nTSecurityDescriptor)"


$missing = "CN=Nobody Here,CN=Users,$domain"
Assert-LiveError 'missing DN' { Get-ADUser $missing -Server $Server -ErrorAction Stop } 'SambaAD.ObjectNotFound' 'ObjectNotFound' $missing
Assert-LiveError 'missing name' { Get-ADUser 'nobody-here' -Server $Server -ErrorAction Stop } 'SambaAD.ObjectNotFound' 'ObjectNotFound'
Assert-LiveError 'missing SID' { Get-ADUser 'S-1-5-21-1-2-3-9' -Server $Server -ErrorAction Stop } 'SambaAD.ObjectNotFound' 'ObjectNotFound'
Assert-LiveError 'missing GUID' { Get-ADUser '00000000-0000-0000-0000-000000000001' -Server $Server -ErrorAction Stop } 'SambaAD.ObjectNotFound' 'ObjectNotFound'
Assert-LiveError 'outside the directory' { Get-ADObject 'CN=x,DC=elsewhere,DC=test' -Server $Server -ErrorAction Stop } 'SambaAD.ObjectNotFound' 'ObjectNotFound'
Assert-LiveError 'wrong class' { Get-ADUser "CN=Domain Admins,CN=Users,$domain" -Server $Server -ErrorAction Stop } 'SambaAD.ObjectNotFound' 'ObjectNotFound'
Assert-LiveError 'unknown property' { Get-ADUser $SamAccountName -Server $Server -Properties notAnAttribute -ErrorAction Stop } 'SambaAD.InvalidProperty' 'InvalidArgument'
Assert-LiveError 'no server' { Get-ADUser $SamAccountName -Server '' -ErrorAction Stop } 'SambaAD.ServerRequired' 'InvalidArgument'
Assert-LiveError 'closed port' { Get-ADUser $SamAccountName -Server "${Server}:3899" -ErrorAction Stop } 'SambaAD.TransportError' 'ConnectionError' 'check the port'
Assert-LiveError 'unknown host' { Get-ADUser $SamAccountName -Server 'no-such-host.invalid' -ErrorAction Stop } 'SambaAD.TransportError' 'ConnectionError' 'does not resolve'
if ($IpAddress) {
    Assert-LiveError 'an address has no principal' { Get-ADUser $SamAccountName -Server $IpAddress -ErrorAction Stop } 'SambaAD.TransportError' 'AuthenticationError' 'DNS host name'
}
$ticket = $env:KRB5CCNAME
$env:KRB5CCNAME = 'FILE:/nonexistent/no-ticket'
Assert-LiveError 'no ticket' { Get-ADUser $SamAccountName -Server $Server -ErrorAction Stop } 'SambaAD.TransportError' 'AuthenticationError' 'kinit'
if ($ticket) { $env:KRB5CCNAME = $ticket } else { Remove-Item Env:KRB5CCNAME }

if ($script:failures.Count -gt 0) {
    $script:failures | ForEach-Object { Write-Output "FAILED: $_" }
    throw "$($script:failures.Count) of $script:checks live checks failed."
}
Write-Output "All $script:checks live checks passed."
