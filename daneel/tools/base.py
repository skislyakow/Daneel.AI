"""Contracts for tools that the agent may call."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

Arguments = dict[str, Any]
Confirm = Callable[[str, Arguments], Awaitable[bool]]


class Tool(Protocol):
    """A callable operation exposed to the model."""

    name: str
    description: str
    parameters: dict[str, Any]
    requires_confirmation: bool

    async def run(self, arguments: Arguments) -> str:
        """Execute the tool and return a textual result."""


@dataclass(slots=True)
class FunctionTool:
    """Adapt an async function to the Tool contract."""

    name: str
    description: str
    parameters: dict[str, Any]
    runner: Callable[[Arguments], Awaitable[str]]
    requires_confirmation: bool = True

    async def run(self, arguments: Arguments) -> str:
        """Call the wrapped function."""
        return await self.runner(arguments)


class ToolError(RuntimeError):
    """Base class for tool execution errors."""


class ToolNotFoundError(ToolError):
    """The model requested a tool that is not registered."""


class ToolDenied(ToolError):
    """The user did not confirm the tool call."""
