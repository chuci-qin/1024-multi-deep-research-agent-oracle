"""
Research Agents for the Multi-Agent Oracle.

Each agent independently researches a question and collects sources.

Components:
- BaseAgent: Abstract base class for agents
- GeminiDeepResearchAgent: Gemini-powered research agent
- StrategyFactory: Factory for creating differentiated agent configurations
"""

from oracle.agents.base import BaseAgent, SearchStrategy, AgentConfig
from oracle.agents.gemini import GeminiDeepResearchAgent
from oracle.agents.strategies import (
    StrategyProfile,
    StrategyConfig,
    StrategyFactory,
    STRATEGY_CONFIGS,
)

__all__ = [
    # Base
    "BaseAgent",
    "SearchStrategy",
    "AgentConfig",
    # Implementations
    "GeminiDeepResearchAgent",
    # Strategies
    "StrategyProfile",
    "StrategyConfig",
    "StrategyFactory",
    "STRATEGY_CONFIGS",
]
