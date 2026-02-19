"""
Oracle Tool Framework — Base classes for external data tools.

Tools let Gemini agents call real APIs (Binance, CoinGecko, etc.) via
function calling, instead of relying solely on Google Search grounding.

To add a new tool:
  1. Create a new file in oracle/tools/
  2. Subclass BaseTool, implement execute()
  3. Call register_tool() in oracle/tools/__init__.py
"""

from abc import ABC, abstractmethod

import structlog

logger = structlog.get_logger()


class BaseTool(ABC):
    """Abstract base class for all Oracle tools."""

    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    async def execute(self, **kwargs) -> dict:
        """Execute the tool and return structured data."""
        ...

    def to_function_declaration(self) -> dict:
        """Convert to Gemini function_declaration format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


# Global tool registry
_TOOL_REGISTRY: dict[str, BaseTool] = {}


def register_tool(tool: BaseTool) -> None:
    _TOOL_REGISTRY[tool.name] = tool
    logger.info("Registered oracle tool", tool_name=tool.name)


def get_tool(name: str) -> BaseTool | None:
    return _TOOL_REGISTRY.get(name)


def get_all_tools() -> list[BaseTool]:
    return list(_TOOL_REGISTRY.values())


def get_function_declarations() -> list[dict]:
    """Return all tool declarations in Gemini function_declaration format."""
    return [t.to_function_declaration() for t in _TOOL_REGISTRY.values()]
