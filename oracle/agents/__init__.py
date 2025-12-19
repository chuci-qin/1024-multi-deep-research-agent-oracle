"""
Research Agents for the Multi-Agent Oracle.

Each agent independently researches a question and collects sources.
"""

from oracle.agents.base import BaseAgent, SearchStrategy
from oracle.agents.gemini import GeminiDeepResearchAgent

__all__ = [
    "BaseAgent",
    "SearchStrategy",
    "GeminiDeepResearchAgent",
]
