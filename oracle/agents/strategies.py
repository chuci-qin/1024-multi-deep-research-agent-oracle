"""
Agent Differentiation Strategies

Defines diversified search strategies for research agents to ensure
independent and comprehensive research from multiple angles.

Task ID: 2.6.1 - 2.6.7 from IMPLEMENTATION-TRACKER.md
"""

from enum import Enum

import structlog
from pydantic import BaseModel, Field

from oracle.agents.base import AgentConfig, SearchStrategy

logger = structlog.get_logger()


class StrategyProfile(str, Enum):
    """
    Predefined strategy profiles for agent differentiation.

    Task 2.6.1: Define strategy profiles.
    """

    # Core strategies
    COMPREHENSIVE = "comprehensive"  # Broad coverage, all source types
    FOCUSED_OFFICIAL = "focused_official"  # Focus on official/government sources
    NEWS_CENTRIC = "news_centric"  # Focus on major news outlets
    DIVERSE_PERSPECTIVES = "diverse_perspectives"  # Maximize viewpoint diversity

    # Verification strategies
    SKEPTICAL = "skeptical"  # Look for counter-evidence
    FACT_CHECK = "fact_check"  # Focus on fact-checking sources
    CROSS_REFERENCE = "cross_reference"  # Verify across multiple sources

    # Domain-specific
    CRYPTO_FINANCIAL = "crypto_financial"  # Crypto and financial sources
    SOCIAL_SENTIMENT = "social_sentiment"  # Social media analysis
    ACADEMIC = "academic"  # Academic and research sources


class StrategyConfig(BaseModel):
    """
    Detailed configuration for a search strategy.

    Task 2.6.2: Define StrategyConfig.
    """

    profile: StrategyProfile
    description: str

    # Search parameters
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=8192)

    # Source preferences
    preferred_domains: list[str] = Field(default_factory=list)
    excluded_domains: list[str] = Field(default_factory=list)
    min_sources: int = Field(default=50)

    # Category weighting (total should sum to ~100)
    category_weights: dict[str, int] = Field(default_factory=dict)

    # Search query templates
    query_templates: list[str] = Field(default_factory=list)

    # Verification emphasis
    verification_focus: str = Field(
        default="balanced", description="verification focus: balanced, confirming, disconfirming"
    )

    # Prompt customization
    system_prompt_additions: str = Field(default="")


# ============================================================================
# Predefined Strategy Configurations
# ============================================================================

STRATEGY_CONFIGS: dict[StrategyProfile, StrategyConfig] = {
    StrategyProfile.COMPREHENSIVE: StrategyConfig(
        profile=StrategyProfile.COMPREHENSIVE,
        description="Broad coverage across all source types for comprehensive understanding",
        temperature=0.1,
        category_weights={
            "official": 20,
            "news": 30,
            "domain_specific": 25,
            "social": 15,
            "fact_check": 10,
        },
        query_templates=[
            "{question}",
            "{question} latest news",
            "{question} official announcement",
            "{question} confirmed",
            "{question} reuters bloomberg",
            "{question} AP news BBC",
            "{question} analysis expert",
            "{question} update 2024 2025",
        ],
        verification_focus="balanced",
    ),
    StrategyProfile.FOCUSED_OFFICIAL: StrategyConfig(
        profile=StrategyProfile.FOCUSED_OFFICIAL,
        description="Focus on official government and regulatory sources",
        temperature=0.05,
        preferred_domains=[
            ".gov",
            ".gov.uk",
            "sec.gov",
            "treasury.gov",
            "europa.eu",
            "un.org",
            "who.int",
        ],
        category_weights={
            "official": 50,
            "news": 30,
            "domain_specific": 15,
            "fact_check": 5,
        },
        query_templates=[
            '"{question}" site:gov',
            '"{question}" official announcement',
            '"{question}" government statement',
            '"{question}" regulatory filing',
            '"{question}" press release official',
        ],
        verification_focus="confirming",
        system_prompt_additions=(
            "Prioritize official government sources, regulatory filings, "
            "and official press releases. Be skeptical of unofficial sources."
        ),
    ),
    StrategyProfile.NEWS_CENTRIC: StrategyConfig(
        profile=StrategyProfile.NEWS_CENTRIC,
        description="Focus on major news outlets and wire services",
        temperature=0.1,
        preferred_domains=[
            "reuters.com",
            "apnews.com",
            "bbc.com",
            "bbc.co.uk",
            "bloomberg.com",
            "cnn.com",
            "nytimes.com",
            "wsj.com",
            "ft.com",
            "theguardian.com",
            "cnbc.com",
        ],
        category_weights={
            "news": 60,
            "official": 20,
            "domain_specific": 15,
            "fact_check": 5,
        },
        query_templates=[
            "{question} site:reuters.com",
            "{question} site:apnews.com",
            "{question} site:bbc.com OR site:bbc.co.uk",
            "{question} site:bloomberg.com",
            "{question} breaking news",
            "{question} latest report",
        ],
        verification_focus="balanced",
    ),
    StrategyProfile.SKEPTICAL: StrategyConfig(
        profile=StrategyProfile.SKEPTICAL,
        description="Look for counter-evidence and contradictions",
        temperature=0.15,
        category_weights={
            "fact_check": 30,
            "news": 25,
            "official": 20,
            "domain_specific": 15,
            "social": 10,
        },
        query_templates=[
            "{question} false",
            "{question} debunked",
            "{question} not true",
            "{question} controversy",
            "{question} criticism",
            "{question} failed OR denied",
            "{question} misinformation",
            "{question} fact check",
        ],
        verification_focus="disconfirming",
        system_prompt_additions=(
            "Actively look for evidence that contradicts the expected outcome. "
            "Be skeptical of claims without strong verification. "
            "Identify potential misinformation or bias in sources."
        ),
    ),
    StrategyProfile.FACT_CHECK: StrategyConfig(
        profile=StrategyProfile.FACT_CHECK,
        description="Focus on fact-checking organizations and verification",
        temperature=0.05,
        preferred_domains=[
            "snopes.com",
            "factcheck.org",
            "politifact.com",
            "fullfact.org",
            "apnews.com/hub/ap-fact-check",
            "reuters.com/fact-check",
        ],
        category_weights={
            "fact_check": 50,
            "official": 25,
            "news": 20,
            "domain_specific": 5,
        },
        query_templates=[
            "{question} fact check",
            "{question} site:snopes.com",
            "{question} site:factcheck.org",
            "{question} verified OR confirmed",
            "{question} true or false",
        ],
        verification_focus="confirming",
    ),
    StrategyProfile.CRYPTO_FINANCIAL: StrategyConfig(
        profile=StrategyProfile.CRYPTO_FINANCIAL,
        description="Focus on crypto and financial sources",
        temperature=0.1,
        preferred_domains=[
            "coindesk.com",
            "cointelegraph.com",
            "theblock.co",
            "decrypt.co",
            "bloomberg.com",
            "wsj.com",
            "coingecko.com",
            "coinmarketcap.com",
        ],
        category_weights={
            "domain_specific": 50,
            "news": 25,
            "official": 15,
            "social": 10,
        },
        query_templates=[
            "{question} crypto",
            "{question} site:coindesk.com",
            "{question} site:cointelegraph.com",
            "{question} bitcoin ethereum",
            "{question} blockchain",
            "{question} price market",
        ],
        verification_focus="balanced",
    ),
    StrategyProfile.SOCIAL_SENTIMENT: StrategyConfig(
        profile=StrategyProfile.SOCIAL_SENTIMENT,
        description="Analyze social media sentiment and discussions",
        temperature=0.2,
        preferred_domains=[
            "twitter.com",
            "x.com",
            "reddit.com",
            "discord.com",
            "telegram.org",
        ],
        category_weights={
            "social": 50,
            "news": 25,
            "domain_specific": 15,
            "official": 10,
        },
        query_templates=[
            "{question} site:twitter.com OR site:x.com",
            "{question} site:reddit.com",
            "{question} trending",
            "{question} viral",
            "{question} community reaction",
        ],
        verification_focus="balanced",
        system_prompt_additions=(
            "Analyze social media sentiment and community discussions. "
            "Note the volume and nature of public discourse. "
            "Be aware that social media can contain misinformation."
        ),
    ),
    StrategyProfile.DIVERSE_PERSPECTIVES: StrategyConfig(
        profile=StrategyProfile.DIVERSE_PERSPECTIVES,
        description="Maximize viewpoint diversity from different source types",
        temperature=0.15,
        category_weights={
            "news": 25,
            "official": 20,
            "domain_specific": 20,
            "social": 20,
            "fact_check": 15,
        },
        query_templates=[
            "{question} analysis",
            "{question} opinion editorial",
            "{question} different perspectives",
            "{question} debate",
            "{question} supporters critics",
        ],
        verification_focus="balanced",
        system_prompt_additions=(
            "Seek diverse perspectives on the topic. "
            "Consider viewpoints from different stakeholders. "
            "Note areas of consensus and disagreement."
        ),
    ),
    StrategyProfile.CROSS_REFERENCE: StrategyConfig(
        profile=StrategyProfile.CROSS_REFERENCE,
        description="Cross-reference facts across multiple independent sources",
        temperature=0.1,
        category_weights={
            "news": 35,
            "official": 25,
            "domain_specific": 20,
            "fact_check": 20,
        },
        query_templates=[
            "{question} multiple sources",
            "{question} confirmed by",
            "{question} according to",
            "{question} independently verified",
        ],
        verification_focus="confirming",
        system_prompt_additions=(
            "Focus on cross-referencing key facts across multiple independent sources. "
            "A fact is more reliable if confirmed by multiple unrelated sources. "
            "Note which facts are independently verified and which are single-source."
        ),
    ),
    StrategyProfile.ACADEMIC: StrategyConfig(
        profile=StrategyProfile.ACADEMIC,
        description="Focus on academic and research sources",
        temperature=0.1,
        preferred_domains=[
            ".edu",
            "arxiv.org",
            "scholar.google.com",
            "researchgate.net",
            "nature.com",
            "science.org",
        ],
        category_weights={
            "official": 40,
            "domain_specific": 40,
            "news": 15,
            "fact_check": 5,
        },
        query_templates=[
            "{question} research paper",
            "{question} site:arxiv.org",
            "{question} academic study",
            "{question} peer reviewed",
        ],
        verification_focus="confirming",
    ),
}


class StrategyFactory:
    """
    Factory for creating agent configurations based on strategy profiles.

    Task 2.6.3-2.6.5: Implement StrategyFactory.
    """

    @staticmethod
    def get_config(profile: StrategyProfile) -> StrategyConfig:
        """
        Get strategy configuration by profile.

        Task 2.6.4: Implement get_config().
        """
        if profile not in STRATEGY_CONFIGS:
            logger.warning(f"Unknown strategy profile: {profile}, using COMPREHENSIVE")
            return STRATEGY_CONFIGS[StrategyProfile.COMPREHENSIVE]
        return STRATEGY_CONFIGS[profile]

    @staticmethod
    def get_agent_config(profile: StrategyProfile) -> AgentConfig:
        """
        Convert strategy config to agent config.

        Task 2.6.5: Convert to AgentConfig.
        """
        strategy_config = StrategyFactory.get_config(profile)

        # Convert category weights to requirements
        # Assuming min_sources = 50, scale weights to absolute numbers
        min_sources = strategy_config.min_sources
        category_requirements = {}

        total_weight = sum(strategy_config.category_weights.values())
        if total_weight > 0:
            for cat, weight in strategy_config.category_weights.items():
                category_requirements[cat] = max(1, int(min_sources * weight / total_weight))

        return AgentConfig(
            min_sources=min_sources,
            min_categories=len(strategy_config.category_weights),
            temperature=strategy_config.temperature,
            max_tokens=strategy_config.max_tokens,
            category_requirements=category_requirements,
        )

    @staticmethod
    def get_search_strategy(profile: StrategyProfile) -> SearchStrategy:
        """Map profile to base SearchStrategy enum."""
        mapping = {
            StrategyProfile.COMPREHENSIVE: SearchStrategy.COMPREHENSIVE,
            StrategyProfile.FOCUSED_OFFICIAL: SearchStrategy.FOCUSED,
            StrategyProfile.NEWS_CENTRIC: SearchStrategy.FOCUSED,
            StrategyProfile.SKEPTICAL: SearchStrategy.SKEPTICAL,
            StrategyProfile.FACT_CHECK: SearchStrategy.FOCUSED,
            StrategyProfile.CRYPTO_FINANCIAL: SearchStrategy.FOCUSED,
            StrategyProfile.SOCIAL_SENTIMENT: SearchStrategy.DIVERSE,
            StrategyProfile.DIVERSE_PERSPECTIVES: SearchStrategy.DIVERSE,
            StrategyProfile.CROSS_REFERENCE: SearchStrategy.COMPREHENSIVE,
            StrategyProfile.ACADEMIC: SearchStrategy.FOCUSED,
        }
        return mapping.get(profile, SearchStrategy.COMPREHENSIVE)

    @staticmethod
    def generate_queries(profile: StrategyProfile, question: str) -> list[str]:
        """
        Generate search queries based on strategy profile.

        Task 2.6.6: Implement generate_queries().
        """
        config = StrategyFactory.get_config(profile)
        queries = []

        for template in config.query_templates:
            query = template.format(question=question)
            queries.append(query)

        return queries

    @staticmethod
    def get_recommended_profiles(
        agent_count: int = 5,
    ) -> list[StrategyProfile]:
        """
        Get recommended strategy profiles for a set of agents.

        Task 2.6.7: Recommend diverse profiles.

        Ensures diversity in research approaches.
        """
        if agent_count <= 0:
            return []

        # Recommended combination for maximum diversity
        recommended = [
            StrategyProfile.COMPREHENSIVE,  # Broad coverage
            StrategyProfile.FOCUSED_OFFICIAL,  # Official sources
            StrategyProfile.NEWS_CENTRIC,  # News coverage
            StrategyProfile.SKEPTICAL,  # Counter-evidence
            StrategyProfile.FACT_CHECK,  # Verification
            StrategyProfile.DIVERSE_PERSPECTIVES,  # Multiple viewpoints
            StrategyProfile.CROSS_REFERENCE,  # Cross-verification
        ]

        # Return requested number
        if agent_count <= len(recommended):
            return recommended[:agent_count]

        # If more agents needed, repeat with slight variation
        result = recommended.copy()
        while len(result) < agent_count:
            # Add more agents with slightly different configs
            result.extend(recommended[: agent_count - len(result)])

        return result[:agent_count]

    @staticmethod
    def list_all_profiles() -> list[dict]:
        """List all available strategy profiles with descriptions."""
        return [
            {
                "profile": profile.value,
                "description": config.description,
                "verification_focus": config.verification_focus,
                "category_weights": config.category_weights,
            }
            for profile, config in STRATEGY_CONFIGS.items()
        ]
