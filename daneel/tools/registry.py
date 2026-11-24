"""Registry of tools exposed to Ollama."""

from __future__ import annotations

from typing import Any

from .base import Confirm, Tool, ToolDenied, ToolNotFoundError


class ToolRegistry:
    """Collects tools, builds their API schema, and executes confirmed calls."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        """Add or replace a tool by name."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Return a registered tool, if any."""
        return self._tools.get(name)

    def as_schema(self) -> list[dict[str, Any]]:
        """Return tool definitions in the Ollama /api/chat format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    async def call(
        self,
        name: str,
        arguments: dict[str, Any],
        confirm: Confirm | None = None,
    ) -> str:
        """Confirm and execute a tool call.

        Confirmation is mandatory for tools that require it. With no confirmation
        callback, such calls are denied rather than executed silently.
        """
        tool = self.get(name)
        if tool is None:
            raise ToolNotFoundError(f"Unknown tool: {name}")

        if tool.requires_confirmation:
            if confirm is None or not await confirm(name, arguments):
                raise ToolDenied(f"Tool call denied: {name}")

        return await tool.run(arguments)
