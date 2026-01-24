"""
Workspace Panel - Left pane companion for Claude Code workflow
Run in left Windows Terminal pane, Claude Code in right panes
"""

import os
import subprocess
import time
from pathlib import Path

from textual.app import App, ComposeResult
from textual.message import Message
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
FILE_POLL_INTERVAL = 2.0  # seconds
SHADOW_REVIEW_COOLDOWN = 10.0  # seconds between auto-reviews


# --- File Watcher ---

class FileWatcher:
    """Tracks file changes in a directory by comparing mtimes."""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self._last_snapshot: dict[Path, float] = {}
        self._take_snapshot()

    def _take_snapshot(self) -> dict[Path, float]:
        """Capture current file mtimes."""
        snapshot = {}
        try:
            for path in self.root_path.rglob("*"):
                if path.is_file() and ".git" not in path.parts:
                    try:
                        snapshot[path] = path.stat().st_mtime
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
        return snapshot

    def check_for_changes(self) -> tuple[bool, list[Path], list[Path], list[Path]]:
        """
        Check if any files changed since last check.
        Returns: (changed, added, modified, deleted)
        """
        new_snapshot = self._take_snapshot()
        old_paths = set(self._last_snapshot.keys())
        new_paths = set(new_snapshot.keys())

        added = list(new_paths - old_paths)
        deleted = list(old_paths - new_paths)
        modified = [
            p for p in (old_paths & new_paths)
            if self._last_snapshot[p] != new_snapshot[p]
        ]

        changed = bool(added or deleted or modified)
        self._last_snapshot = new_snapshot
        return changed, added, modified, deleted


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

    class ShadowReviewComplete(Message):
        """Posted when shadow review finishes."""
        def __init__(self, result: str, status: str) -> None:
            self.result = result
            self.status = status  # "safe", "warning", "error"
            super().__init__()

    def __init__(self):
        super().__init__()
        self.last_output = ""
        self.shadow_enabled = False
        self._last_diff_hash: int = 0
        self._reviewing = False

    def compose(self) -> ComposeResult:
        yield ModelSelector()
        yield Static("", id="lm-status")
        yield Horizontal(
            Button("Diff", id="btn-diff", variant="primary"),
            Button("Staged", id="btn-staged"),
            Button("Commit", id="btn-commit"),
            Button("Ping", id="btn-ping"),
            Button("Copy", id="btn-copy"),
            Static("│", classes="separator"),
            Button("Shadow", id="btn-shadow"),
            Static("[dim]off[/]", id="shadow-status"),
            id="button-row"
        )
        yield RichLog(id="model-output", wrap=True, highlight=True)

    def toggle_shadow(self) -> None:
        """Toggle shadow review on/off."""
        self.shadow_enabled = not self.shadow_enabled
        btn = self.query_one("#btn-shadow", Button)
        status = self.query_one("#shadow-status", Static)
        if self.shadow_enabled:
            btn.variant = "success"
            status.update("[dim]watching[/]")
        else:
            btn.variant = "default"
            status.update("[dim]off[/]")

    async def run_shadow_review(self) -> None:
        """Run an automatic review of the current diff."""
        if not self.shadow_enabled or self._reviewing:
            return

        selector = self.query_one(ModelSelector)
        client: LMStudioClient = self.app.lmstudio

        if not client.connected or not selector.selected_model:
            return

        # Get current diff
        diff = get_git_diff()
        if diff in ("(no unstaged changes)", "") or diff.startswith("Error:"):
            # Try staged changes instead
            diff = get_git_staged()
            if diff in ("(nothing staged)", "") or diff.startswith("Error:"):
                return

        # Check if diff changed since last review
        diff_hash = hash(diff)
        if diff_hash == self._last_diff_hash:
            return
        self._last_diff_hash = diff_hash

        # Run the review
        self._reviewing = True
        status = self.query_one("#shadow-status", Static)
        status.update("[yellow]Reviewing...[/]")

        review_prompt = """You are a code reviewer. Analyze this diff for:
1. Security issues (API keys, credentials, injection vulnerabilities)
2. Obvious bugs or regressions
3. Debug code that should be removed (console.log, print statements, TODO comments)

Be VERY brief. If everything looks fine, just say "LGTM".
If there are issues, list them in 1-2 sentences max.
Start your response with one of: [SAFE], [WARNING], or [CRITICAL]"""

        response = await client.query_chat(
            prompt=review_prompt,
            context=diff,
            model=selector.selected_model,
        )

        self._reviewing = False

        # Determine status from response
        if response.startswith("Error:"):
            review_status = "error"
            indicator = "[red]ERR[/]"
        elif "[CRITICAL]" in response.upper():
            review_status = "critical"
            indicator = "[red bold]CRITICAL[/]"
        elif "[WARNING]" in response.upper():
            review_status = "warning"
            indicator = "[yellow]WARN[/]"
        else:
            review_status = "safe"
            indicator = "[green]OK[/]"

        status.update(indicator)
        self.post_message(self.ShadowReviewComplete(response, review_status))

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

        # Handle Shadow toggle
        if event.button.id == "btn-shadow":
            self.toggle_shadow()
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

    def on_model_panel_shadow_review_complete(self, event: ShadowReviewComplete) -> None:
        """Handle shadow review completion - show in output if critical/warning."""
        if event.status in ("critical", "warning"):
            output = self.query_one("#model-output", RichLog)
            output.clear()
            output.write(f"[bold]Shadow Review:[/]\n{event.result}")
            self.last_output = event.result


# --- Main App ---

class WorkspacePanel(App):
    """Left-pane workspace companion."""

    def __init__(self, *args, watch_path: str = STARTING_PATH, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.watch_path = watch_path
        self.lmstudio = LMStudioClient(
            base_url=os.environ.get("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1"),
            api_key=os.environ.get("LMSTUDIO_API_KEY"),
        )
        self.file_watcher = FileWatcher(watch_path)
        self._last_shadow_review = 0.0

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
        min-width: 4;
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

    /* Shadow review */
    .separator {
        width: 1;
        height: 1;
        margin: 0 1;
        color: #333333;
    }

    #shadow-status {
        width: auto;
        min-width: 6;
        height: 1;
        margin-left: 1;
        content-align: left middle;
        color: #8b949e;
    }

    #btn-shadow {
        min-width: 6;
    }

    #btn-shadow.-success {
        background: #238636;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "toggle_shadow", "Shadow"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="top-panel"):
            with TabbedContent():
                yield TabPane("Files", DirectoryTree(self.watch_path, id="file-tree"))
                yield TabPane("Inspector", InspectorPanel())
        yield ModelPanel()

    def on_mount(self) -> None:
        """Start file polling on mount."""
        self.set_interval(FILE_POLL_INTERVAL, self._check_for_file_changes)

    async def _check_for_file_changes(self) -> None:
        """Poll for file changes and refresh tree if needed."""
        changed, added, modified, deleted = self.file_watcher.check_for_changes()

        if changed:
            # Refresh the file tree
            tree = self.query_one("#file-tree", DirectoryTree)
            tree.reload()

            # Trigger shadow review if enabled and cooldown passed
            model_panel = self.query_one(ModelPanel)
            now = time.monotonic()
            if (model_panel.shadow_enabled and
                now - self._last_shadow_review >= SHADOW_REVIEW_COOLDOWN):
                self._last_shadow_review = now
                await model_panel.run_shadow_review()

    def action_refresh(self) -> None:
        """Refresh the file tree."""
        tree = self.query_one("#file-tree", DirectoryTree)
        tree.reload()

    def action_toggle_shadow(self) -> None:
        """Toggle shadow review via keyboard."""
        model_panel = self.query_one(ModelPanel)
        model_panel.toggle_shadow()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Open file in default application."""
        os.startfile(event.path)


# --- Entry Point ---

if __name__ == "__main__":
    import sys

    # Allow passing starting directory as argument
    watch_path = STARTING_PATH
    if len(sys.argv) > 1:
        watch_path = sys.argv[1]

    app = WorkspacePanel(watch_path=watch_path)
    app.run()
