"""Shared helpers for tool-call confirmation across interfaces."""

from __future__ import annotations

import json

from .core import Conversation
from .tools import Arguments, Confirm


def render_arguments(arguments: Arguments) -> str:
    """Return a readable representation of tool arguments for the user."""
    return json.dumps(arguments, ensure_ascii=False)


def install_confirmation(conversation: Conversation, confirm: Confirm) -> None:
    """Install an interface callback unless one was supplied explicitly."""
    if conversation.confirm is None:
        conversation.set_confirmation(confirm)
