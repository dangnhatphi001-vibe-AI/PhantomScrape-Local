param(
    [string]$Targets = "",
    [switch]$NoBrowser,
    [string]$InstallDir = "",
    [string]$ConfigHome = ""
)
$ErrorActionPreference = "Stop"

function Get-PhantomPython {
    foreach ($name in @("py", "python3", "python")) {
        $candidate = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $candidate) { continue }
        # Skip the Store redirect stub; it is not an installed interpreter.
        if ($candidate.Source -like "*WindowsApps\python*.exe") { continue }
        $prefix = @()
        if ($name -eq "py") { $prefix = @("-3") }
        try {
            $result = & $candidate.Source @prefix -c "import sys; sys.exit(1) if sys.version_info < (3,11) else print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $result) {
                return ([string]($result | Select-Object -Last 1)).Trim()
            }
        } catch { continue }
    }
    throw "Python 3.11+ is required. Install it from https://www.python.org/downloads/ then run this command again."
}

function Get-PhantomArchive([string]$Url, [string]$Destination) {
    Add-Type -AssemblyName System.Net.Http
    $client = New-Object System.Net.Http.HttpClient
    $response = $null
    $frames = @([char]0x25D0, [char]0x25D3, [char]0x25D1, [char]0x25D2)
    $animated = -not [Console]::IsOutputRedirected
    Write-Host "Downloading PhantomScrape from GitHub..."
    try {
        $task = $client.GetAsync($Url)
        $tick = 0
        while (-not $task.IsCompleted) {
            if ($animated) {
                Write-Host -NoNewline ("`r{0} Downloading from GitHub..." -f $frames[$tick % 4])
                $tick++
            }
            Start-Sleep -Milliseconds 120
        }
        $response = $task.GetAwaiter().GetResult()
        $null = $response.EnsureSuccessStatusCode()
        $bytes = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
        [IO.File]::WriteAllBytes($Destination, $bytes)
        if ($animated) { Write-Host -NoNewline "`r                                           `r" }
        Write-Host "OK: source downloaded."
    } finally {
        if ($response) { $response.Dispose() }
        $client.Dispose()
    }
}

$python = Get-PhantomPython
$source = $null
$temporary = $null
try {
    if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "scripts/install.py"))) {
        $source = $PSScriptRoot
    } else {
        $temporary = Join-Path ([IO.Path]::GetTempPath()) ("phantom-" + [Guid]::NewGuid().ToString("N"))
        $null = New-Item -ItemType Directory -Path $temporary
        $archive = Join-Path $temporary "source.zip"
        Get-PhantomArchive "https://codeload.github.com/dangnhatphi001-vibe-AI/PhantomScrape-Local/zip/refs/heads/main" $archive
        Expand-Archive -LiteralPath $archive -DestinationPath $temporary
        $source = Join-Path $temporary "PhantomScrape-Local-main"
    }
    $installer = Join-Path $source "scripts/install.py"
    if (-not (Test-Path $installer)) { throw "The downloaded archive has no installer." }
    $arguments = @("-X", "utf8", $installer)
    if ($Targets) { $arguments += @("--targets", $Targets) }
    if ($NoBrowser) { $arguments += "--no-browser" }
    if ($InstallDir) { $arguments += @("--install-dir", $InstallDir) }
    if ($ConfigHome) { $arguments += @("--config-home", $ConfigHome) }
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Installation failed (exit $LASTEXITCODE). See the error above." }
} finally {
    if ($temporary -and (Test-Path $temporary)) {
        Remove-Item -LiteralPath $temporary -Recurse -Force
    }
}
