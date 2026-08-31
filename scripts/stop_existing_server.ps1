param(
    [Parameter(Mandatory = $true)]
    [int]$Port,

    [Parameter(Mandatory = $true)]
    [string]$Workspace
)

$ErrorActionPreference = 'Stop'

try {
    $workspacePath = (Resolve-Path -LiteralPath $Workspace).Path.TrimEnd('\')
} catch {
    Write-Host "Workspace path was not found: $Workspace"
    exit 1
}

function Get-ListeningProcessIds {
    param([int]$LocalPort)

    $ids = @()
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        $ids += @(Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique)
    }

    $rows = netstat -ano -p tcp | Select-String "LISTENING"
    foreach ($row in $rows) {
        $text = $row.Line.Trim()
        if ($text -match "^\s*TCP\s+\S+:$LocalPort\s+\S+\s+LISTENING\s+(\d+)\s*$") {
            $ids += [int]$Matches[1]
        }
    }
    return @($ids | Select-Object -Unique)
}

$processIds = @(Get-ListeningProcessIds -LocalPort $Port | Where-Object { $_ -and $_ -gt 0 })
if (-not $processIds.Count) {
    exit 0
}

$safeToStop = @()
$unsafe = @()
$workspaceVenv = Join-Path $workspacePath '.venv'

foreach ($processId in $processIds) {
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
    $processDetails = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $processInfo) {
        $processInfo = [pscustomobject]@{
            Name = if ($processDetails) { "$($processDetails.ProcessName).exe" } else { "unknown" }
            CommandLine = ''
            ExecutablePath = if ($processDetails) { [string]$processDetails.Path } else { '' }
        }
    }

    $commandLine = [string]$processInfo.CommandLine
    $executablePath = [string]$processInfo.ExecutablePath
    $isPython = $processInfo.Name -match '^pythonw?\.exe$'
    $fromWorkspaceVenv = $executablePath.StartsWith($workspaceVenv, [StringComparison]::OrdinalIgnoreCase)
    $mentionsWorkspace = $commandLine.IndexOf($workspacePath, [StringComparison]::OrdinalIgnoreCase) -ge 0
    $mentionsAppPy = $commandLine -match '(^|\s|\\|")app\.py("|\s|$)'

    if ($isPython -and ($fromWorkspaceVenv -or $mentionsWorkspace -or ($fromWorkspaceVenv -and $mentionsAppPy))) {
        $safeToStop += $processId
    } else {
        $unsafe += [pscustomobject]@{
            ProcessId = $processId
            Name = $processInfo.Name
            CommandLine = $commandLine
        }
    }
}

if ($unsafe.Count) {
    Write-Host "Port $Port is held by a process that does not look like this app:"
    foreach ($entry in $unsafe) {
        Write-Host "  PID $($entry.ProcessId) $($entry.Name)"
    }
    exit 2
}

foreach ($processId in ($safeToStop | Select-Object -Unique)) {
    Write-Host "Stopping older server process PID $processId"
    Stop-Process -Id $processId -Force -ErrorAction Stop
}

$deadline = (Get-Date).AddSeconds(6)
do {
    Start-Sleep -Milliseconds 250
    $remaining = @(Get-ListeningProcessIds -LocalPort $Port | Where-Object { $_ -and $_ -gt 0 })
    if (-not $remaining.Count) {
        exit 0
    }
} while ((Get-Date) -lt $deadline)

Write-Host "Port $Port is still in use after stopping the older server."
exit 3
