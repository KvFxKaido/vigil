"""
Generic MCP Client for connecting to any configured MCP server.
Reads server config from .mcp.json and provides resource browsing.
"""

import json
from pathlib import Path
from dataclasses import dataclass

from pydantic import AnyUrl
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession


@dataclass
class McpResource:
    """A resource from an MCP server."""
    uri: str
    name: str
    description: str
    mime_type: str | None = None


@dataclass
class McpServer:
    """Configuration for an MCP server."""
    name: str
    command: str
    args: list[str]
    cwd: str | None = None


class McpClient:
    """Client for connecting to MCP servers."""

    def __init__(self, config_path: Path | str | None = None):
        if config_path is None:
            self.config_path = self._find_config()
        else:
            self.config_path = Path(config_path)
        self.servers: dict[str, McpServer] = {}
        self._load_config()

    def _find_config(self) -> Path:
        """Find .mcp.json in current directory or parents."""
        current = Path.cwd()
        while current != current.parent:
            config = current / ".mcp.json"
            if config.exists():
                return config
            current = current.parent
        return Path.cwd() / ".mcp.json"

    def _load_config(self) -> None:
        """Load server configurations from .mcp.json."""
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path) as f:
                data = json.load(f)

            for name, config in data.get("mcpServers", {}).items():
                self.servers[name] = McpServer(
                    name=name,
                    command=config["command"],
                    args=config.get("args", []),
                    cwd=config.get("cwd"),
                )
        except Exception:
            pass  # Silently fail if config is invalid

    def get_server_names(self) -> list[str]:
        """Get list of configured server names."""
        return list(self.servers.keys())

    async def list_resources(self, server_name: str) -> list[McpResource]:
        """Connect to a server and list its resources."""
        if server_name not in self.servers:
            return []

        server = self.servers[server_name]
        params = StdioServerParameters(
            command=server.command,
            args=server.args,
            cwd=server.cwd,
        )

        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_resources()

                    return [
                        McpResource(
                            uri=str(r.uri),
                            name=r.name or str(r.uri),
                            description=r.description or "",
                            mime_type=r.mimeType,
                        )
                        for r in result.resources
                    ]
        except Exception as e:
            return []

    async def read_resource(self, server_name: str, uri: str) -> str:
        """Connect to a server and read a specific resource."""
        if server_name not in self.servers:
            return f"Server not found: {server_name}"

        server = self.servers[server_name]
        params = StdioServerParameters(
            command=server.command,
            args=server.args,
            cwd=server.cwd,
        )

        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    # Convert string URI to AnyUrl
                    resource_uri = AnyUrl(uri)
                    result = await session.read_resource(resource_uri)

                    # Combine all content parts
                    parts = []
                    for content in result.contents:
                        if hasattr(content, 'text'):
                            parts.append(content.text)
                        elif hasattr(content, 'blob'):
                            parts.append(f"[Binary data: {len(content.blob)} bytes]")
                    return "\n".join(parts)
        except Exception as e:
            return f"Error reading resource: {e}"
