param(
    [Parameter(Mandatory)]
    [string]$PythonPath,

    [Parameter()]
    [ValidateRange(1, 10000)]
    [int]$Iterations = 100
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Measures real Get-ADUser calls through the process-per-invocation bridge.
function Measure-CmdletProcess {
    [CmdletBinding()]
    param([Parameter(Mandatory)][int]$Count)

    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $null = Get-ADUser -Identity 'CN=Alice,DC=example,DC=com' -Server dc1
    $oneCall = $watch.Elapsed.TotalMilliseconds
    $watch.Restart()
    for ($index = 0; $index -lt $Count; $index++) {
        $null = Get-ADUser -Identity 'CN=Alice,DC=example,DC=com' -Server dc1
    }
    $watch.Stop()
    return [ordered]@{
        one_call_ms = $oneCall
        sequential_calls = $Count
        sequential_total_ms = $watch.Elapsed.TotalMilliseconds
        sequential_mean_ms = $watch.Elapsed.TotalMilliseconds / $Count
    }
}

# Waits until the resident Python process has bound its Unix-domain socket.
function Wait-ResidentSocket {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][System.Diagnostics.Process]$Process
    )

    $deadline = [DateTime]::UtcNow.AddSeconds(5)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($Process.HasExited) {
            throw 'The resident backend exited before binding its socket.'
        }
        if (Test-Path -LiteralPath $Path) {
            return
        }
        Start-Sleep -Milliseconds 1
    }
    throw 'The resident backend did not bind its socket within five seconds.'
}

# Sends one JSON line through an already connected resident transport.
function Invoke-ResidentExchange {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][System.IO.StreamWriter]$Writer,
        [Parameter(Mandatory)][System.IO.StreamReader]$Reader,
        [Parameter(Mandatory)][string]$Payload
    )

    $Writer.WriteLine($Payload)
    $Writer.Flush()
    $response = $Reader.ReadLine()
    if ($response -ne $Payload) {
        throw 'The resident backend returned an unexpected response.'
    }
}

# Measures startup plus one exchange and then repeated warm socket exchanges.
function Measure-ResidentSocket {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Python,
        [Parameter(Mandatory)][string]$Backend,
        [Parameter(Mandatory)][string]$SocketPath,
        [Parameter(Mandatory)][int]$Count
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $Python
    $startInfo.ArgumentList.Add($Backend)
    $startInfo.ArgumentList.Add('serve')
    $startInfo.ArgumentList.Add($SocketPath)
    $startInfo.UseShellExecute = $false
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    if (-not $process.Start()) {
        throw 'The resident backend process did not start.'
    }

    try {
        Wait-ResidentSocket -Path $SocketPath -Process $process
        $endpoint = [System.Net.Sockets.UnixDomainSocketEndPoint]::new($SocketPath)
        $socket = [System.Net.Sockets.Socket]::new(
            [System.Net.Sockets.AddressFamily]::Unix,
            [System.Net.Sockets.SocketType]::Stream,
            [System.Net.Sockets.ProtocolType]::Unspecified
        )
        $socket.Connect($endpoint)
        $stream = [System.Net.Sockets.NetworkStream]::new($socket, $true)
        $encoding = [System.Text.UTF8Encoding]::new($false)
        $writer = [System.IO.StreamWriter]::new($stream, $encoding, 1024, $true)
        $reader = [System.IO.StreamReader]::new($stream, $encoding, $false, 1024, $true)
        $writer.NewLine = "`n"
        $payload = '{"version":1,"operation":"ping","parameters":{}}'
        Invoke-ResidentExchange -Writer $writer -Reader $reader -Payload $payload
        $oneCall = $watch.Elapsed.TotalMilliseconds
        $watch.Restart()
        for ($index = 0; $index -lt $Count; $index++) {
            Invoke-ResidentExchange -Writer $writer -Reader $reader -Payload $payload
        }
        $watch.Stop()
        $writer.WriteLine('__quit__')
        $writer.Flush()
        $writer.Dispose()
        $reader.Dispose()
        $stream.Dispose()
        $process.WaitForExit(5000) | Out-Null
        return [ordered]@{
            one_call_ms = $oneCall
            sequential_calls = $Count
            sequential_total_ms = $watch.Elapsed.TotalMilliseconds
            sequential_mean_ms = $watch.Elapsed.TotalMilliseconds / $Count
        }
    } finally {
        if (-not $process.HasExited) {
            $process.Kill($true)
        }
        $process.Dispose()
    }
}

if (-not $IsLinux) {
    throw 'This benchmark must run in the Debian acceptance environment.'
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$fixture = Join-Path $repoRoot 'tests/fixtures/fake_backend.py'
$echoBackend = Join-Path $PSScriptRoot 'echo_backend.py'
$temporary = Join-Path ([System.IO.Path]::GetTempPath()) (
    'samba-ad-benchmark-' + [System.Guid]::NewGuid().ToString('N')
)
$wrapper = $temporary + '-backend'
$socketPath = $temporary + '.sock'
$oldBackend = $env:SAMBA_POWERSHELL_BACKEND
$oldModulePath = $env:PSModulePath

try {
    Set-Content -LiteralPath $wrapper -Value (
        "#!/bin/sh`nexec `"$PythonPath`" `"$fixture`" `"`$@`""
    ) -Encoding utf8NoBOM
    & chmod 700 $wrapper
    $env:SAMBA_POWERSHELL_BACKEND = $wrapper
    $env:PSModulePath = (Join-Path $repoRoot 'powershell') + (
        [System.IO.Path]::PathSeparator + $env:PSModulePath
    )
    Import-Module SambaAD -Force
    $processResult = Measure-CmdletProcess -Count $Iterations
    $socketResult = Measure-ResidentSocket -Python $PythonPath `
        -Backend $echoBackend -SocketPath $socketPath -Count $Iterations
    [ordered]@{
        environment = [ordered]@{
            os = (Get-Content /etc/os-release | Select-String '^PRETTY_NAME=').Line
            powershell = $PSVersionTable.PSVersion.ToString()
            python = (& $PythonPath --version)
        }
        process_per_cmdlet = $processResult
        resident_unix_socket = $socketResult
    } | ConvertTo-Json -Depth 5
} finally {
    $env:SAMBA_POWERSHELL_BACKEND = $oldBackend
    $env:PSModulePath = $oldModulePath
    Remove-Item -LiteralPath $wrapper -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $socketPath -Force -ErrorAction SilentlyContinue
}
