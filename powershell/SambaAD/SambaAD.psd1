@{
    RootModule = 'SambaAD.psm1'
    ModuleVersion = '0.2.0'
    GUID = 'a63914b8-d92b-44ab-9ba6-5187c8395131'
    Author = 'HardenSamba'
    CompanyName = 'HardenSamba'
    Copyright = '(c) HardenSamba contributors'
    Description = 'Active Directory cmdlets on Linux for Samba AD, over Kerberos-authenticated LDAP. Needs the Debian packages python3-ldap and libsasl2-modules-gssapi-mit.'
    PowerShellVersion = '7.4'
    CompatiblePSEditions = @('Core')
    FunctionsToExport = @('Get-ADUser', 'Get-ADComputer', 'Get-ADGroup', 'Get-ADObject')
    CmdletsToExport = @()
    VariablesToExport = @()
    AliasesToExport = @()
    FormatsToProcess = @('SambaAD.Format.ps1xml')
    PrivateData = @{
        PSData = @{
            Tags = @('ActiveDirectory', 'Samba', 'Kerberos', 'LDAP', 'Linux', 'PSEdition_Core')
            ProjectUri = 'https://github.com/HardenSamba/samba-powershell'
            LicenseUri = 'https://github.com/HardenSamba/samba-powershell/blob/main/LICENSE'
        }
    }
}
