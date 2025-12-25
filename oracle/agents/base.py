"""
Base Agent - Abstract base class for all research agents.
"""

import uuid
from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel, Field

from oracle.models import AgentResult, ResearchSource


class SearchStrategy(str, Enum):
    """Research strategies for agents."""

    COMPREHENSIVE = "comprehensive"  # Broad search, many queries
    FOCUSED = "focused"  # Deep dive on key terms
    DIVERSE = "diverse"  # Maximize source variety
    SKEPTICAL = "skeptical"  # Look for counterarguments


class AgentConfig(BaseModel):
    """Configuration for a research agent."""

    min_sources: int = Field(default=50, description="Minimum sources required")
    min_categories: int = Field(default=5, description="Minimum source categories")
    temperature: float = Field(default=0.1, description="LLM temperature")
    max_tokens: int = Field(default=8192, description="Max output tokens")
    timeout_seconds: int = Field(default=300, description="Research timeout")
    max_retries: int = Field(default=3, description="Max retry attempts")

    # Category requirements
    category_requirements: dict[str, int] = Field(
        default_factory=lambda: {
            "official": 5,
            "news": 15,
            "social": 10,
            "domain_specific": 10,
            "fact_check": 3,
        }
    )


class BaseAgent(ABC):
    """
    Abstract base class for all research agents.

    Each agent must:
    1. Collect 50+ sources from 5+ categories
    2. Provide confidence scores and reasoning
    3. Be independent (no communication with other agents)
    """

    def __init__(
        self,
        agent_id: str | None = None,
        strategy: SearchStrategy = SearchStrategy.COMPREHENSIVE,
        config: AgentConfig | None = None,
    ):
        self.agent_id = agent_id or f"agent-{uuid.uuid4().hex[:8]}"
        self.strategy = strategy
        self.config = config or AgentConfig()

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the LLM model name."""
        pass

    @abstractmethod
    async def research(
        self,
        question: str,
        resolution_criteria: str,
        deadline: str | None = None,
    ) -> AgentResult:
        """
        Conduct deep research on a question.

        Args:
            question: The question to research
            resolution_criteria: Criteria for determining the answer
            deadline: Optional deadline for the question

        Returns:
            AgentResult with outcome, confidence, sources, and reasoning
        """
        pass

    def validate_sources(self, sources: list[ResearchSource]) -> dict:
        """Validate that sources meet minimum requirements."""
        categories: dict[str, int] = {}
        for source in sources:
            cat = source.category.value if hasattr(source.category, "value") else source.category
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_sources": len(sources),
            "total_categories": len(categories),
            "category_distribution": categories,
            "meets_total_requirement": len(sources) >= self.config.min_sources,
            "meets_category_requirement": len(categories) >= self.config.min_categories,
            "is_valid": (
                len(sources) >= self.config.min_sources
                and len(categories) >= self.config.min_categories
            ),
        }

    def generate_search_queries(self, question: str) -> list[str]:
        """Generate diverse search queries based on strategy."""
        queries = [question]

        if self.strategy == SearchStrategy.COMPREHENSIVE:
            queries.extend(
                [
                    f"{question} latest news",
                    f"{question} official announcement",
                    f"{question} confirmed",
                    f"{question} reuters",
                    f"{question} bloomberg",
                    f"{question} AP news",
                    f"{question} BBC",
                    f"{question} fact check",
                    f"{question} analysis",
                    f"{question} update 2025",
                    f"{question} twitter",
                    f"{question} reddit",
                    f"{question} official statement",
                    f"{question} press release",
                    f"{question} government",
                ]
            )
        elif self.strategy == SearchStrategy.FOCUSED:
            queries.extend(
                [
                    f'"{question}" confirmed',
                    f'"{question}" official',
                    f'"{question}" evidence',
                    f"{question} site:reuters.com",
                    f"{question} site:gov",
                ]
            )
        elif self.strategy == SearchStrategy.DIVERSE:
            queries.extend(
                [
                    f"{question} news",
                    f"{question} social media reaction",
                    f"{question} expert opinion",
                    f"{question} industry analysis",
                    f"{question} fact check snopes",
                ]
            )
        elif self.strategy == SearchStrategy.SKEPTICAL:
            queries.extend(
                [
                    f"{question} false",
                    f"{question} debunked",
                    f"{question} controversy",
                    f"{question} criticism",
                    f"{question} skepticism",
                ]
            )

        return queries
