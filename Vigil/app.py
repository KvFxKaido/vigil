"""
Workspace Panel - Left pane companion for Claude Code workflow
Run in left Windows Terminal pane, Claude Code in right panes
"""

import os
import subprocess

from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import (
    DirectoryTree, Static, Button, RichLog, Select,
    TabbedContent, TabPane, ListView, ListItem, Label,
)
from textual.binding import Binding

from services.git import get_git_diff, get_git_staged
from services.lm_studio import LMStudioClient
from services.mcp_client import McpClient


# --- Configuration ---

STARTING_PATH = "C:/dev/SENTINEL"  # Override with command line arg later


# --- Widgets ---

class ModelSelector(Horizontal):
    """Model selection dropdown with connection status."""

    def __init__(self):
        super().__init__()
        self.selected_model = None

    def compose(self) -> ComposeResult:
        yield Static("", id="status-indicator")
        yield Select([], prompt="Select model", id="model-select")
        yield Button("↻", id="btn-refresh-models", variant="default")

    async def on_mount(self) -> None:
        await self.refresh_models(force=True)
        self.set_interval(2.0, self.refresh_models)

    def _update_status_text(self, *, connected: bool, models_count: int, error: str | None) -> None:
        try:
            status = self.app.query_one("#lm-status", Static)
        except Exception:
            return

        if connected:
            status.update(f"[green]LM Studio connected[/] ([dim]{models_count} models[/])")
        else:
            message = error or "Not connected."
            status.update(f"[red]LM Studio offline[/] ([dim]{message}[/])")

    async def refresh_models(self, *, force: bool = False) -> None:
        """Fetch and populate available models."""
        client: LMStudioClient = self.app.lmstudio
        select = self.query_one("#model-select", Select)
        indicator = self.query_one("#status-indicator", Static)

        models = await client.refresh_models(force=force)

        if client.connected:
            select.set_options([(m, m) for m in models])
            if models:
                if self.selected_model not in models:
                    self.selected_model = models[0]
                select.value = self.selected_model
            else:
                self.selected_model = None
                select.value = Select.BLANK
            indicator.update("[green]●[/]")
        else:
            select.set_options([])
            self.selected_model = None
            select.value = Select.BLANK
            indicator.update("[red]●[/]")

        self._update_status_text(
            connected=client.connected,
            models_count=len(models),
            error=client.last_error,
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle model selection change."""
        if event.select.id == "model-select" and event.value != Select.BLANK:
            self.selected_model = event.value

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle refresh button."""
        if event.button.id == "btn-refresh-models":
            await self.refresh_models(force=True)


class InspectorPanel(Vertical):
    """MCP resource inspector panel."""

    def __init__(self):
        super().__init__()
        self.mcp = McpClient()
        self.current_server = None
        self.resources = []

    def compose(self) -> ComposeResult:
        servers = self.mcp.get_server_names()
        if servers:
            options = [(s, s) for s in servers]
            yield Select(options, prompt="Select server", id="server-select", value=servers[0])
        else:
            yield Static("[dim]No MCP servers configured[/]", id="no-servers")
        yield ListView(id="resource-list")
        yield VerticalScroll(
            Static("", id="resource-content"),
            id="resource-scroll",
        )

    async def on_mount(self) -> None:
        servers = self.mcp.get_server_names()
        if servers:
            self.current_server = servers[0]
            await self.load_resources()

    async def load_resources(self) -> None:
        """Load resources from the current server."""
        if not self.current_server:
            return

        list_view = self.query_one("#resource-list", ListView)
        list_view.clear()

        content = self.query_one("#resource-content", Static)
        content.update("[dim]Loading resources...[/]")

        self.resources = await self.mcp.list_resources(self.current_server)

        if self.resources:
            for r in self.resources:
                item = ListItem(Label(f"[#58a6ff]{r.name}[/]"))
                item.resource_uri = r.uri  # Store URI on the item
                list_view.append(item)
            content.update(f"[dim]{len(self.resources)} resources available[/]")
        else:
            content.update("[yellow]No resources found (is the server running?)[/]")

    async def on_select_changed(self, event: Select.Changed) -> None:
        """Handle server selection change."""
        if event.select.id == "server-select" and event.value != Select.BLANK:
            self.current_server = event.value
            await self.load_resources()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle resource selection."""
        if not hasattr(event.item, 'resource_uri'):
            return

        uri = event.item.resource_uri
        content = self.query_one("#resource-content", Static)
        content.update("[dim]Loading...[/]")

        result = await self.mcp.read_resource(self.current_server, uri)

        # Try to pretty-format JSON
        try:
            import json
            data = json.loads(result)
            result = json.dumps(data, indent=2)
        except Exception:
            pass

        content.update(result)


class ModelPanel(Vertical):
    """Bottom-left panel with model controls and output."""

    def __init__(self):
        super().__init__()
        self.last_output = ""

    def compose(self) -> ComposeResult:
        yield ModelSelector()
        yield Static("", id="lm-status")
        yield Horizontal(
            Button("Explain Diff", id="btn-diff", variant="primary"),
            Button("Summarize Staged", id="btn-staged"),
            Button("Suggest Commit", id="btn-commit"),
            Button("Ping", id="btn-ping"),
            Button("Copy", id="btn-copy"),
            id="button-row"
        )
        yield RichLog(id="model-output", wrap=True, highlight=True)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        # Ignore refresh button (handled by ModelSelector)
        if event.button.id == "btn-refresh-models":
            return

        output = self.query_one("#model-output", RichLog)

        # Handle Copy button separately
        if event.button.id == "btn-copy":
            if self.last_output:
                subprocess.run(["clip"], input=self.last_output.encode(), check=True)
                output.write("[green]Copied to clipboard[/]")
            else:
                output.write("[yellow]Nothing to copy[/]")
            return

        selector = self.query_one(ModelSelector)
        client: LMStudioClient = self.app.lmstudio

        if not client.connected:
            await selector.refresh_models(force=True)

        if not client.connected:
            output.write("[red]LM Studio not connected[/]")
            return

        if not selector.selected_model:
            output.write("[yellow]No model selected[/]")
            return

        output.clear()
        output.write("[dim]Thinking...[/]")

        if event.button.id == "btn-ping":
            context = ""
            prompt = "Reply with exactly: pong"

        elif event.button.id == "btn-diff":
            context = get_git_diff()
            prompt = "Explain what this diff does. Be concise."

        elif event.button.id == "btn-staged":
            context = get_git_staged()
            prompt = "Summarize these staged changes. What's the intent?"

        elif event.button.id == "btn-commit":
            context = get_git_staged()
            if context == "(nothing staged)":
                context = get_git_diff()
            prompt = "Suggest a commit message for these changes. Just the message, no explanation."

        else:
            return

        response = await client.query_chat(
            prompt=prompt,
            context=context,
            model=selector.selected_model,
        )
        self.last_output = response
        output.clear()
        output.write(response)


# --- Main App ---

class WorkspacePanel(App):
    """Left-pane workspace companion."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.lmstudio = LMStudioClient(
            base_url=os.environ.get("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1"),
            api_key=os.environ.get("LMSTUDIO_API_KEY"),
        )

    CSS = """
    Screen {
        background: #000000;
        layout: grid;
        grid-size: 1 2;
        grid-rows: 2fr 1fr;
    }

    DirectoryTree {
        height: 1fr;
        background: #000000;
    }

    TabPane > DirectoryTree {
        height: 1fr;
    }

    TabPane > InspectorPanel {
        height: 1fr;
    }

    DirectoryTree > .directory-tree--folder {
        color: #58a6ff;
    }

    DirectoryTree > .directory-tree--file {
        color: #e6edf3;
    }

    DirectoryTree:focus {
        border: solid #58a6ff;
    }

    ModelPanel {
        height: 100%;
        background: #000000;
        border: solid #333333;
        padding: 1;
    }

    ModelSelector {
        height: 3;
        margin-bottom: 1;
        background: #000000;
    }

    #status-indicator {
        width: 2;
        height: 1;
        margin-top: 1;
        content-align: center middle;
    }

    #model-select {
        width: 1fr;
        height: auto;
    }

    #model-select > SelectCurrent {
        min-height: 3;
        background: #0d1117;
        border: tall #333333;
    }

    #model-select:focus > SelectCurrent {
        border: tall #58a6ff;
        background-tint: #e6edf3 5%;
    }

    #btn-refresh-models {
        width: 3;
        min-width: 3;
        height: 3;
        margin-left: 1;
        padding: 1 0;
        content-align: center middle;
    }

    #lm-status {
        height: 1;
        margin-bottom: 1;
        color: #8b949e;
    }

    #button-row {
        height: auto;
        margin-bottom: 1;
        background: #000000;
    }

    #button-row Button {
        margin-right: 1;
        min-width: 8;
        height: 1;
        padding: 0 1;
    }

    Button {
        background: #21262d;
        color: #e6edf3;
        border: none;
        min-width: 4;
        height: 1;
        padding: 0 1;
    }

    Button:hover {
        background: #30363d;
    }

    Button.-primary {
        background: #238636;
    }

    Button.-primary:hover {
        background: #2ea043;
    }

    #model-output {
        height: 1fr;
        background: #0d1117;
        border: solid #333333;
        padding: 1;
    }

    RichLog {
        background: #0d1117;
    }

    /* Top panel wrapper */
    #top-panel {
        min-height: 0;
    }

    /* Tabs */
    #top-panel TabbedContent {
        height: 1fr;
        min-height: 0;
        border: solid #333333;
    }

    Tabs {
        background: #000000;
        width: 100%;
    }

    Tab {
        background: #21262d;
        color: #8b949e;
        padding: 0 2;
    }

    Tab:hover {
        background: #30363d;
    }

    Tab.-active {
        background: #0d1117;
        color: #58a6ff;
    }

    /* Inspector Panel */
    InspectorPanel {
        height: 100%;
        background: #000000;
    }

    #server-select {
        height: 3;
        margin: 1;
    }

    #resource-list {
        height: 1fr;
        background: #0d1117;
        border: solid #333333;
        margin: 0 1;
    }

    #resource-list > ListItem {
        padding: 0 1;
    }

    #resource-list > ListItem:hover {
        background: #21262d;
    }

    #resource-list > ListItem.-highlight {
        background: #30363d;
    }

    #resource-scroll {
        height: 1fr;
        background: #0d1117;
        border: solid #333333;
        margin: 1;
        padding: 1;
    }

    #resource-content {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="top-panel"):
            with TabbedContent():
                yield TabPane("Files", DirectoryTree(STARTING_PATH, id="file-tree"))
                yield TabPane("Inspector", InspectorPanel())
        yield ModelPanel()

    def action_refresh(self) -> None:
        """Refresh the file tree."""
        tree = self.query_one("#file-tree", DirectoryTree)
        tree.reload()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Open file in default application."""
        os.startfile(event.path)


# --- Entry Point ---

if __name__ == "__main__":
    import sys

    # Allow passing starting directory as argument
    if len(sys.argv) > 1:
        STARTING_PATH = sys.argv[1]

    app = WorkspacePanel()
    app.run()
