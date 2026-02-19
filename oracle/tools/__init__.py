"""
Oracle Tools — Extensible tool registry for Gemini function calling.

All tools are auto-registered on import. To add a new tool:
  1. Create oracle/tools/your_tool.py with a BaseTool subclass
  2. Import and register it here
"""

from oracle.tools.base import (
    BaseTool,
    register_tool,
    get_tool,
    get_all_tools,
    get_function_declarations,
)
from oracle.tools.crypto_price import CryptoPriceAtTimestamp, CryptoPriceCurrent

# Auto-register all built-in tools
register_tool(CryptoPriceAtTimestamp())
register_tool(CryptoPriceCurrent())

__all__ = [
    "BaseTool",
    "register_tool",
    "get_tool",
    "get_all_tools",
    "get_function_declarations",
]
