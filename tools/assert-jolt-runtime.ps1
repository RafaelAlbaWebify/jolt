[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-ApplicationCommand {
    param([Parameter(Mandatory)][string[]]$Names)

    foreach ($name in $Names) {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($null -ne $command) {
            return $command.Source
        }
    }

    throw "Required application '$($Names -join "' or '")' was not found in PATH."
}

function Get-SemanticVersion {
    param(
        [Parameter(Mandatory)][string]$Label,
        [Parameter(Mandatory)][string]$Output
    )

    $match = [regex]::Match($Output, '(?<major>\d+)\.(?<minor>\d+)\.(?<patch>\d+)')
    if (-not $match.Success) {
        throw "Could not parse $Label version from '$Output'."
    }

    return [version]::new(
        [int]$match.Groups['major'].Value,
        [int]$match.Groups['minor'].Value,
        [int]$match.Groups['patch'].Value
    )
}

function Invoke-VersionCommand {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory)][string]$Label
    )

    $output = @(& $FilePath @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0 -or $output.Count -eq 0) {
        throw "$Label version check failed."
    }

    return ($output -join " ").Trim()
}

if (-not $IsWindows) {
    throw "JOLT's supported operator runtime is Windows x64. Current platform is not Windows."
}

$architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
if ($architecture -ne [System.Runtime.InteropServices.Architecture]::X64) {
    throw "JOLT's supported operator runtime is Windows x64. Current architecture is '$architecture'."
}

$osVersion = [System.Environment]::OSVersion.Version
if ($osVersion.Build -lt 19045) {
    throw "Windows 10 22H2 (build 19045) or Windows 11 is required. Current OS version: $osVersion."
}

if ($PSVersionTable.PSVersion -lt [version]'7.4.0') {
    throw "PowerShell 7.4 or later is required. Current version: $($PSVersionTable.PSVersion)."
}

$gitCommand = Resolve-ApplicationCommand -Names @("git.exe", "git")
$uvCommand = Resolve-ApplicationCommand -Names @("uv.exe", "uv")
$nodeCommand = Resolve-ApplicationCommand -Names @("node.exe", "node")
$npmCommand = Resolve-ApplicationCommand -Names @("npm.cmd", "npm")

$gitOutput = Invoke-VersionCommand -FilePath $gitCommand -Arguments @("--version") -Label "Git"
$uvOutput = Invoke-VersionCommand -FilePath $uvCommand -Arguments @("--version") -Label "uv"
$nodeOutput = Invoke-VersionCommand -FilePath $nodeCommand -Arguments @("--version") -Label "Node.js"
$npmOutput = Invoke-VersionCommand -FilePath $npmCommand -Arguments @("--version") -Label "npm"

$gitVersion = Get-SemanticVersion -Label "Git" -Output $gitOutput
$uvVersion = Get-SemanticVersion -Label "uv" -Output $uvOutput
$nodeVersion = Get-SemanticVersion -Label "Node.js" -Output $nodeOutput
$npmVersion = Get-SemanticVersion -Label "npm" -Output $npmOutput

if ($gitVersion -lt [version]'2.40.0') {
    throw "Git 2.40 or later is required. Current version: $gitVersion."
}

if ($uvVersion -lt [version]'0.5.14' -or $uvVersion -ge [version]'1.0.0') {
    throw "uv >=0.5.14 and <1.0.0 is required. Current version: $uvVersion."
}

if ($nodeVersion.Major -ne 22) {
    throw "Node.js 22.x is required. Current version: $nodeVersion."
}

if ($npmVersion.Major -lt 10 -or $npmVersion.Major -ge 12) {
    throw "npm 10.x or 11.x is required. Current version: $npmVersion."
}

$result = [ordered]@{
    platform = "Windows x64"
    powershell = $PSVersionTable.PSVersion.ToString()
    git = $gitVersion.ToString()
    uv = $uvVersion.ToString()
    node = $nodeVersion.ToString()
    npm = $npmVersion.ToString()
    python = "CPython 3.12.x managed by uv"
}

$result | ConvertTo-Json -Depth 3
