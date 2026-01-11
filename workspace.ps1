# Unified Terminal Workspace Launcher
# Layout: Vigil (left 30%) | Shell (right top) | Claude Code (right bottom)
#
# Usage: .\workspace.ps1 [project-path]
# Example: .\workspace.ps1 C:\dev\my-project

param(
    [string]$ProjectPath = (Get-Location).Path
)

# Resolve to absolute path
$ProjectPath = (Resolve-Path $ProjectPath -ErrorAction SilentlyContinue)?.Path ?? $ProjectPath

if (-not (Test-Path $ProjectPath)) {
    Write-Host "Warning: Path '$ProjectPath' does not exist. Using current directory." -ForegroundColor Yellow
    $ProjectPath = (Get-Location).Path
}

Write-Host "Launching workspace in: $ProjectPath" -ForegroundColor Cyan

# Launch Windows Terminal with split panes
# Left (30%): Vigil (file tree + MCP inspector + local model)
# Right top (70%): Shell
# Right bottom: Claude Code
$AppPath = Join-Path $PSScriptRoot "Vigil\\app.py"
cmd /c "wt -d `"$ProjectPath`" --title `"Vigil`" python `"$AppPath`" `"$ProjectPath`" ; split-pane -V -s 0.7 -d `"$ProjectPath`" --title `"Shell`" ; split-pane -H -s 0.3 -d `"$ProjectPath`" --title `"Claude Code`""
