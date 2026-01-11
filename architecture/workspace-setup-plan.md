# Unified Terminal Workspace

A single-window workspace for Claude Code + file navigation + shell commands. Reduces context-switching across monitors and applications.

## Layout

```
+------------+-------------------------+
|            |                         |
|   broot    |      Claude Code        |
|  (Files)   |                         |
|            +-------------------------+
|            |         Shell           |
+------------+-------------------------+
```

- **Left (30%)**: broot file browser for navigation/orientation
- **Right top (70%)**: Claude Code primary interaction
- **Right bottom**: Shell for commands, tests, `lastshot`, etc.

## What's Installed

### broot (Terminal File Browser)

Installed via winget:
```powershell
winget install Dystroy.broot
```

**Basic usage:**
- Type to fuzzy-search files
- `Enter` to open/navigate
- `Alt+Enter` to cd into directory
- `Ctrl+Q` to quit
- `br` command launches broot with shell integration

### PowerShell Profile Functions

Location: `$PROFILE` (C:\Users\ishaw\OneDrive\Documents\PowerShell\Microsoft.PowerShell_profile.ps1)

#### `workspace [path]`
Launches the three-pane workspace layout. Defaults to current directory.

```powershell
workspace              # Opens workspace in current directory
workspace C:\dev\proj  # Opens workspace in specified path
```

#### `lastshot`
Copies the most recent screenshot path to clipboard. Checks multiple locations:
- `$env:USERPROFILE\Pictures\Screenshots`
- `$env:USERPROFILE\OneDrive\Pictures\Screenshots`
- `$env:USERPROFILE\Videos\Captures`

**Workflow:**
1. Take screenshot with `Win+Shift+S`
2. In shell pane, type `lastshot`
3. Paste path into Claude Code conversation

## Files

| File | Purpose |
|------|---------|
| `workspace.ps1` | Launch script (can pass project path as argument) |
| `workspace.cmd` | Double-clickable launcher for taskbar/desktop |

## Quick Reference

| Action | Command/Key |
|--------|-------------|
| Launch workspace | `workspace` |
| Get screenshot path | `lastshot` |
| Resize panes | `Alt+Shift+Arrow` |
| Close a pane | `Ctrl+Shift+W` |
| Exit broot | `Ctrl+Q` |
| Search in broot | Just start typing |
| cd in broot | `Alt+Enter` |

## Customization

To adjust pane sizes, edit the `workspace` function in `$PROFILE`:

```powershell
# Current: broot 30%, Claude 70% width, shell 30% height
split-pane -V -s 0.7  # Controls Claude pane width (0.7 = 70%)
split-pane -H -s 0.3  # Controls shell pane height (0.3 = 30%)
```
