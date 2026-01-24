# Vigil

A Textual-based left pane for your Claude Code workflow: file tree, MCP Inspector, and local model integration (LM Studio).

## Setup

From the repo root:

```powershell
.\Vigil\setup.cmd
```

Or manually:

```powershell
pip install -r .\Vigil\requirements.txt
```

## Usage

```powershell
python .\Vigil\app.py                    # Current directory
python .\Vigil\app.py C:\dev\sentinel    # Specific project

.\workspace.cmd                          # Launch Windows Terminal layout
```

## Layout

```
┌─────────────────────┬──────────────────────────────┐
│ [Files] [Inspector] │                              │
├─────────────────────┤       Shell                  │
│ DirectoryTree       │                              │
│   or                │                              │
│ MCP Resources       ├──────────────────────────────┤
├─────────────────────┤                              │
│ ● qwen2.5:14b       │       Claude Code            │
│ [Diff] [Staged]     │                              │
│ [Commit] [Shadow]   │       (or any AI agent)      │
│ Model output here   │                              │
└─────────────────────┴──────────────────────────────┘
```

The right panes are just a suggestion - Vigil works as a standalone panel for any workflow. The `workspace.cmd` launcher sets up this specific layout with Claude Code, but you can run Vigil on its own.

## Tabs

**Files** — Directory tree browser. Press Enter or double-click to open files in their default app.

**Inspector** — Generic MCP resource browser. Reads `.mcp.json` from the project root and lets you browse any configured MCP server's resources.

## Requirements

- LM Studio running on `127.0.0.1:1234` (or `localhost:1234`)
- At least one model loaded (picked via the dropdown)
- Git repository (for the buttons to do anything useful)
- `.mcp.json` in project root (for Inspector tab)

You can override the endpoint/auth if needed:
- `LMSTUDIO_BASE_URL` (examples: `http://127.0.0.1:1234/v1`, `http://localhost:1234/api/v0`)
- `LMSTUDIO_API_KEY` (if your server returns 401/403 without a Bearer token)

## MCP Inspector

The Inspector tab reads `.mcp.json` and connects to configured MCP servers:

```json
{
  "mcpServers": {
    "sentinel-campaign": {
      "command": "python",
      "args": ["-m", "sentinel_campaign.server"],
      "cwd": "C:\\dev\\SENTINEL\\sentinel-campaign\\src"
    }
  }
}
```

It spawns the server fresh for each query (simple but slightly slower). Click any resource to view its content.

## Keybindings

- `q` — Quit
- `r` — Refresh file tree
- `s` — Toggle Shadow review (auto-reviews diffs for security issues)
- `Enter` — Open selected file in default app (Files tab)

## Shadow Review

Press `s` or click the Shadow button to enable automatic code review. When files change, your local LM Studio model reviews the git diff for:

- Security issues (API keys, credentials, injection vulnerabilities)
- Obvious bugs or regressions
- Debug code that should be removed

Status indicator shows: `OK` (safe), `WARN` (issues found), or `CRITICAL` (security problem). Warnings and critical issues auto-display in the output panel.

## Integration with Windows Terminal

The `workspace.ps1` script launches a 3-pane layout:
- Left: Vigil
- Top-right: Shell
- Bottom-right: Claude Code

`$PSScriptRoot` is the folder where `workspace.ps1` lives, so moving the repo/folder keeps it working. The `.cmd` wrapper stays untouched.

## Utilities

**Copy latest screenshot path to clipboard:**

```powershell
pwsh -File .\Vigil\lastshot.ps1
```

## Customization

**Change LM Studio endpoint / refresh behavior:**
Edit `WorkspacePanel.__init__()` in `app.py` (or `services/lm_studio.py`)

**Add more buttons:**
Add a new `Button()` in `ModelPanel.compose()`, then handle it in `on_button_pressed()`

**Change prompts:**
Edit the prompt strings in `on_button_pressed()` - they're just plain text

**Adjust layout:**
The `CSS` string in `WorkspacePanel` controls sizing. `grid-rows: 1fr 1fr` means equal split; change to `2fr 1fr` for larger file tree, etc.

## What This Doesn't Do

- Run Claude Code (that stays in Windows Terminal)
- Stream model responses (waits for full response)
- Persist output between sessions
- Keep persistent MCP connections (spawns fresh each query)

These could be added, but the goal was minimal viable panel.
