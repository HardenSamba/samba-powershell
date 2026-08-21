# shellcheck shell=sh
# Put the SambaAD module shipped by samba-powershell on the PowerShell search
# path. The path entry is the directory that contains the module folder, so
# Import-Module SambaAD resolves /usr/share/samba-powershell/SambaAD.
case ":${PSModulePath}:" in
    *":/usr/share/samba-powershell:"*) ;;
    *) PSModulePath="/usr/share/samba-powershell${PSModulePath:+:${PSModulePath}}"
       export PSModulePath ;;
esac
