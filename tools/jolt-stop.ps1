$ErrorActionPreference = "Stop"

$ports = @(8000, 5173)
$owners = foreach ($port in $ports) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1 |
        ForEach-Object {
            [pscustomobject]@{
                Port = $port
                Pid = [int]$_.OwningProcess
            }
        }
}

if (-not $owners) {
    Write-Host "No JOLT port owners found on 8000 or 5173."
    exit 0
}

$uniquePids = $owners.Pid | Sort-Object -Unique
Write-Host "Stopping processes that own JOLT ports 8000/5173..."
foreach ($pidValue in $uniquePids) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $pidValue" -ErrorAction SilentlyContinue
    $portsForPid = ($owners | Where-Object { $_.Pid -eq $pidValue } | ForEach-Object { $_.Port }) -join ","
    if ($process) {
        Write-Host ("Stopping pid={0} process={1} ports={2}" -f $pidValue, $process.Name, $portsForPid)
        if ($process.CommandLine) {
            Write-Host ("  command: {0}" -f $process.CommandLine)
        }
    }
    else {
        Write-Host ("Stopping pid={0} ports={1}" -f $pidValue, $portsForPid)
    }
    Stop-Process -Id $pidValue -Force -ErrorAction Stop
}

Start-Sleep -Milliseconds 500
$remaining = foreach ($port in $ports) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1 |
        ForEach-Object { [pscustomobject]@{ Port = $port; Pid = [int]$_.OwningProcess } }
}

if ($remaining) {
    Write-Host "WARNING: Some JOLT ports are still listening after stop request:"
    $remaining | Format-Table -AutoSize
    exit 1
}

Write-Host "JOLT ports 8000 and 5173 are now free."
exit 0
