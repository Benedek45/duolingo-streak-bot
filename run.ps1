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

New-Item -ItemType Directory -Force -Path "logs" | Out-Null

python agent.py
$status = $LASTEXITCODE

if ($status -eq 0) {
    Write-Host "[run.ps1] Streak saved — $(Get-Date)"
} else {
    Write-Host "[run.ps1] Agent failed — $(Get-Date)"
}

exit $status
