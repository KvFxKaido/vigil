# lastshot.ps1 - Copy most recent screenshot path to clipboard
# Usage: .\lastshot.ps1 or just 'lastshot' if folder is in PATH

$SearchPaths = @(
    "$env:USERPROFILE\Pictures\Screenshots",
    "$env:USERPROFILE\OneDrive\Pictures\Screenshots",
    "$env:USERPROFILE\Videos\Captures"
)

$files = @()

foreach ($path in $SearchPaths) {
    if (Test-Path $path) {
        $files += Get-ChildItem $path -File -ErrorAction SilentlyContinue
    }
}

if ($files.Count -eq 0) {
    Write-Host "No screenshots found" -ForegroundColor Yellow
    exit 1
}

$latest = $files | Sort-Object LastWriteTime -Descending | Select-Object -First 1

$latest.FullName | Set-Clipboard
Write-Host "Copied: $($latest.FullName)" -ForegroundColor Green
