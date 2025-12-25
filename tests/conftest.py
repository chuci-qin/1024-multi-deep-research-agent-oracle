"""
Pytest fixtures for Multi-Agent Oracle tests.
"""

from unittest.mock import MagicMock

import pytest

from oracle.models import (
    AgentResult,
    Outcome,
    ResearchSource,
    SourceCategory,
)


@pytest.fixture
def sample_source():
    """Create a sample research source."""
    return ResearchSource(
        url="https://reuters.com/article/sample",
        title="Sample Article from Reuters",
        snippet="This is a sample snippet from the article.",
        category=SourceCategory.NEWS,
        relevance_score=0.9,
        credibility_score=0.95,
        cited_by=["agent-1"],
    )


@pytest.fixture
def sample_sources():
    """Create a list of sample sources meeting minimum requirements."""
    sources = []

    # Official sources (5+)
    for i in range(6):
        sources.append(
            ResearchSource(
                url=f"https://example.gov/page-{i}",
                title=f"Official Source {i}",
                category=SourceCategory.OFFICIAL,
                relevance_score=0.9,
                credibility_score=0.95,
            )
        )

    # News sources (15+)
    news_outlets = ["reuters.com", "apnews.com", "bbc.com", "bloomberg.com", "cnn.com"]
    for i in range(16):
        outlet = news_outlets[i % len(news_outlets)]
        sources.append(
            ResearchSource(
                url=f"https://{outlet}/article-{i}",
                title=f"News Article {i}",
                category=SourceCategory.NEWS,
                relevance_score=0.85,
                credibility_score=0.9,
            )
        )

    # Social sources (10+)
    for i in range(12):
        sources.append(
            ResearchSource(
                url=f"https://twitter.com/user/status/{i}",
                title=f"Tweet {i}",
                category=SourceCategory.SOCIAL,
                relevance_score=0.7,
                credibility_score=0.7,
            )
        )

    # Domain-specific sources (10+)
    for i in range(12):
        sources.append(
            ResearchSource(
                url=f"https://industry-site-{i}.com/article",
                title=f"Industry Article {i}",
                category=SourceCategory.DOMAIN_SPECIFIC,
                relevance_score=0.8,
                credibility_score=0.8,
            )
        )

    # Fact-check sources (3+)
    for i in range(4):
        sources.append(
            ResearchSource(
                url=f"https://snopes.com/fact-check/{i}",
                title=f"Fact Check {i}",
                category=SourceCategory.FACT_CHECK,
                relevance_score=0.95,
                credibility_score=0.95,
            )
        )

    return sources


@pytest.fixture
def sample_agent_result(sample_sources):
    """Create a sample agent result."""
    return AgentResult(
        agent_id="test-agent-1",
        model="gemini-2.0-flash-exp",
        strategy="comprehensive",
        outcome=Outcome.YES,
        confidence=0.85,
        reasoning="Based on analysis of 50+ sources, the event has occurred.",
        sources=sample_sources,
        research_duration_seconds=45.2,
    )


@pytest.fixture
def sample_agent_results(sample_sources):
    """Create multiple agent results for consensus testing."""
    return [
        AgentResult(
            agent_id="agent-1",
            model="gemini-2.0-flash-exp",
            strategy="comprehensive",
            outcome=Outcome.YES,
            confidence=0.85,
            reasoning="Evidence supports YES",
            sources=sample_sources[:50],
            research_duration_seconds=40.0,
        ),
        AgentResult(
            agent_id="agent-2",
            model="gemini-2.0-flash-exp",
            strategy="focused",
            outcome=Outcome.YES,
            confidence=0.82,
            reasoning="Confirmed YES based on research",
            sources=sample_sources[:50],
            research_duration_seconds=35.0,
        ),
        AgentResult(
            agent_id="agent-3",
            model="gemini-2.0-flash-exp",
            strategy="diverse",
            outcome=Outcome.YES,
            confidence=0.88,
            reasoning="Multiple sources confirm YES",
            sources=sample_sources[:50],
            research_duration_seconds=42.0,
        ),
    ]


@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response with grounding metadata."""
    response = MagicMock()
    response.text = """OUTCOME: YES
CONFIDENCE: 85%

REASONING:
Based on comprehensive analysis of 52 sources, the event has clearly occurred.
Multiple official sources and news outlets confirm this.

KEY EVIDENCE:
1. Official government announcement confirms the event
2. Reuters and AP both reported the occurrence
3. Industry experts verified the outcome
"""

    # Mock candidates
    candidate = MagicMock()
    candidate.grounding_metadata = MagicMock()
    candidate.grounding_metadata.grounding_chunks = [
        MagicMock(web=MagicMock(uri="https://reuters.com/article", title="Reuters Article")),
        MagicMock(web=MagicMock(uri="https://example.gov/news", title="Government News")),
    ]
    response.candidates = [candidate]

    return response
