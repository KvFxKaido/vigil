# Vigil - Project Context

A local-first companion panel for Claude Code workflows. Textual TUI that sits in the left pane of Windows Terminal while Claude Code runs on the right.

## Philosophy

Read `architecture/local_first_dual_pane_terminal_design_spec.md` for the full design philosophy. Key principles:

- **Shell is law** - Terminal is ground truth, AI never executes implicitly
- **Local-first** - Works fully offline, cloud is optional
- **Boring is correct** - Predictable over clever
- **Explicit seams** - User always knows which component is acting

## Project Structure

```
Vigil/
├── app.py              # Main Textual app - widgets and layout
├── services/
│   ├── git.py          # Git diff/staged helpers
│   ├── lm_studio.py    # LM Studio API client
│   └── mcp_client.py   # MCP server spawning and resource reading
├── requirements.txt    # textual, httpx
└── README.md

architecture/           # Design specs and planning docs
workspace.ps1           # Windows Terminal 3-pane layout launcher
workspace.cmd           # CMD wrapper for workspace.ps1
```

## Key Patterns

- **Textual widgets**: Each major UI section is a widget class (`ModelPanel`, `InspectorPanel`, `ModelSelector`)
- **Async throughout**: All I/O (LM Studio, MCP, git) uses async/await
- **CSS-in-class**: Styles live in `WorkspacePanel.CSS` string, not separate files
- **Services are stateless-ish**: `LMStudioClient` caches connection state, `McpClient` spawns fresh processes per query

## Development

```powershell
pip install -r Vigil/requirements.txt
python Vigil/app.py [optional-path]
```

Requires LM Studio running on `127.0.0.1:1234` for model features. Git repo in target directory for diff/staged buttons.

## Conventions

- No type stubs, keep it simple
- Minimal dependencies (textual, httpx, mcp)
- Dark theme only, GitHub-inspired colors
- Copy button uses Windows `clip` command directly
