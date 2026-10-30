param(
    [Parameter(Mandatory)]
    [string]$ModuleBase,

    [Parameter(Mandatory)]
    [string]$ExpectedErrorId
)

# Run in a fresh pwsh, with no Import-Module: the cmdlets must complete their
# parameter names before anything loaded the module, resolve from the installed
# module alone, be listed where the installation put them, and reach the
# backend, whose first refusal says which half of the installation answered.
$ErrorActionPreference = 'Stop'

if (Get-Module -Name SambaAD) {
    throw 'SambaAD was already imported; the session is not fresh.'
}
$completion = TabExpansion2 -inputScript 'Get-ADUser -' -cursorColumn 12
$offered = @($completion.CompletionMatches.CompletionText)
foreach ($name in '-Identity', '-Server', '-Properties') {
    if ($offered -notcontains $name) {
        throw "Get-ADUser -<Tab> does not offer $name."
    }
}
$command = Get-Command -Name Get-ADUser
if ($command.Source -ne 'SambaAD') {
    throw "Get-ADUser resolved to '$($command.Source)', not to SambaAD."
}
$listed = @(Get-Module -ListAvailable -Name SambaAD)
if ($listed.Count -ne 1 -or $listed[0].ModuleBase -ne $ModuleBase) {
    throw "Get-Module -ListAvailable SambaAD lists '$($listed.ModuleBase -join "', '")', not '$ModuleBase'."
}
$failure = @()
Get-ADUser -Identity 'CN=Nobody,DC=example,DC=com' -ErrorAction SilentlyContinue `
    -ErrorVariable failure
if ($failure.Count -ne 1 -or $failure[0].FullyQualifiedErrorId -notlike "$ExpectedErrorId*") {
    throw "The backend answered '$($failure.FullyQualifiedErrorId -join "', '")', not $ExpectedErrorId."
}
Write-Output "SambaAD at ${ModuleBase}: completion, autoload, listing and backend checked."
