param(
    [string]$AdbHost = "localhost",
    [int]$AdbPort = 5555
)

# Load .env
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^\s*([^#=]+)=(.+)$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            Set-Item -Path "Env:$name" -Value $value
        }
    }
}

Write-Host "[run.ps1] Waiting for emulator ADB..."
$connected = $false
for ($i = 1; $i -le 20; $i++) {
    $state = adb -s "${AdbHost}:${AdbPort}" get-state 2>$null
    if ($state -eq "device") {
        Write-Host "[run.ps1] Emulator ready."
        $connected = $true
        break
    }
    Write-Host "[run.ps1] Not ready yet ($i/20)..."
    Start-Sleep -Seconds 10
}

if (-not $connected) {
    Write-Host "[run.ps1] Emulator did not become ready in time."
    exit 1
}

python agent.py
$status = $LASTEXITCODE

if ($status -eq 0) {
    Write-Host "[run.ps1] Streak saved — $(Get-Date)"
} else {
    Write-Host "[run.ps1] Agent failed — $(Get-Date)"
}

exit $status
