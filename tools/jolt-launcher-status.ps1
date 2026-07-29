$ErrorActionPreference = "Stop"

function Test-HttpEndpoint {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Uri
    )

    try {
        $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 2
        [pscustomobject]@{
            Name = $Name
            Uri = $Uri
            Reachable = $true
            StatusCode = [int]$response.StatusCode
            Detail = "HTTP $($response.StatusCode)"
        }
    }
    catch {
        [pscustomobject]@{
            Name = $Name
            Uri = $Uri
            Reachable = $false
            StatusCode = $null
            Detail = $_.Exception.Message
        }
    }
}

function Get-PortOwner {
    param([Parameter(Mandatory = $true)][int]$Port)

    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1

    if (-not $connection) {
        return [pscustomobject]@{
            Port = $Port
            Listening = $false
            Pid = $null
            ProcessName = ""
            CommandLine = ""
        }
    }

    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue
    [pscustomobject]@{
        Port = $Port
        Listening = $true
        Pid = [int]$connection.OwningProcess
        ProcessName = if ($process) { $process.Name } else { "" }
        CommandLine = if ($process) { $process.CommandLine } else { "" }
    }
}

$backendHealth = Test-HttpEndpoint -Name "backend-health" -Uri "http://127.0.0.1:8000/api/health"
$runtimeIdentity = Test-HttpEndpoint -Name "runtime-identity" -Uri "http://127.0.0.1:8000/api/runtime-identity"
$frontend = Test-HttpEndpoint -Name "frontend" -Uri "http://127.0.0.1:5173"
$owners = @(Get-PortOwner -Port 8000, Get-PortOwner -Port 5173)

Write-Host "JOLT launcher status"
Write-Host "===================="
foreach ($owner in $owners) {
    if ($owner.Listening) {
        Write-Host ("Port {0}: LISTENING pid={1} process={2}" -f $owner.Port, $owner.Pid, $owner.ProcessName)
        if ($owner.CommandLine) {
            Write-Host ("  command: {0}" -f $owner.CommandLine)
        }
    }
    else {
        Write-Host ("Port {0}: not listening" -f $owner.Port)
    }
}

Write-Host ""
foreach ($endpoint in @($backendHealth, $runtimeIdentity, $frontend)) {
    if ($endpoint.Reachable) {
        Write-Host ("{0}: OK {1} ({2})" -f $endpoint.Name, $endpoint.Uri, $endpoint.Detail)
    }
    else {
        Write-Host ("{0}: NOT REACHABLE {1}" -f $endpoint.Name, $endpoint.Uri)
        Write-Host ("  detail: {0}" -f $endpoint.Detail)
    }
}
