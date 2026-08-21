@{
    RootModule = 'SambaAD.psm1'
    ModuleVersion = '0.1.0'
    GUID = 'a63914b8-d92b-44ab-9ba6-5187c8395131'
    Author = 'HardenSamba'
    CompanyName = 'HardenSamba'
    Copyright = '(c) HardenSamba contributors'
    Description = 'Active Directory administration cmdlets for Samba AD.'
    PowerShellVersion = '7.4'
    CompatiblePSEditions = @('Core')
    FunctionsToExport = @(
        'Get-ADUser', 'Get-ADComputer', 'Get-ADGroup', 'Get-ADObject',
        'New-ADUser', 'New-ADGroup', 'New-ADOrganizationalUnit',
        'Set-ADObject', 'Remove-ADObject',
        'Add-ADGroupMember', 'Remove-ADGroupMember',
        'Enable-ADAccount', 'Disable-ADAccount', 'Set-ADAccountPassword',
        'Move-ADObject', 'Rename-ADObject'
    )
    CmdletsToExport = @()
    VariablesToExport = @()
    AliasesToExport = @()
    FormatsToProcess = @('SambaAD.Format.ps1xml')
}
