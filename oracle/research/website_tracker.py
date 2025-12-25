"""
Website Visit Tracker

Tracks all websites visited during research with credibility scoring
and source categorization.

Task ID: 2.3.1 - 2.3.7 from IMPLEMENTATION-TRACKER.md
"""

from datetime import datetime
from enum import Enum
from urllib.parse import urlparse

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class CredibilityTier(str, Enum):
    """Credibility tiers for source domains."""

    TIER_1 = "tier_1"  # Highest: .gov, major wire services (0.9-1.0)
    TIER_2 = "tier_2"  # High: major news outlets (0.7-0.89)
    TIER_3 = "tier_3"  # Medium: industry publications (0.5-0.69)
    TIER_4 = "tier_4"  # Low: blogs, forums (0.3-0.49)
    TIER_5 = "tier_5"  # Unverified: unknown sources (0.0-0.29)


class SourceType(str, Enum):
    """Types of sources."""

    OFFICIAL = "official"  # Government, regulatory bodies
    WIRE_SERVICE = "wire_service"  # Reuters, AP, AFP
    MAJOR_NEWS = "major_news"  # BBC, CNN, Bloomberg
    FINANCIAL = "financial"  # Financial data providers
    CRYPTO = "crypto"  # Crypto-specific sources
    SOCIAL = "social"  # Twitter/X, Reddit
    ACADEMIC = "academic"  # Research papers, journals
    BLOG = "blog"  # Personal blogs
    FORUM = "forum"  # Forums, discussion boards
    UNKNOWN = "unknown"  # Unclassified


class WebsiteVisit(BaseModel):
    """
    Record of a single website visit during research.

    Task 2.3.1-2.3.2: Define WebsiteVisit data class.
    """

    # Core fields (Task 2.3.2)
    url: str = Field(..., description="Full URL of the visited page")
    title: str = Field(default="", description="Page title")
    visited_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(), description="ISO timestamp of visit"
    )
    content_snippet: str = Field(
        default="", description="Excerpt of relevant content from the page"
    )

    # Analysis fields
    domain: str = Field(default="", description="Extracted domain name")
    source_type: SourceType = Field(default=SourceType.UNKNOWN, description="Type of source")
    credibility_tier: CredibilityTier = Field(
        default=CredibilityTier.TIER_5, description="Credibility tier"
    )
    credibility_score: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Credibility score (0-1)"
    )
    relevance_score: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Relevance to the research question (0-1)"
    )

    # Metadata
    agent_id: str | None = Field(None, description="Agent that visited")
    facts_extracted: list[str] = Field(
        default_factory=list, description="Key facts extracted from this source"
    )

    def model_post_init(self, __context) -> None:
        """Extract domain from URL after initialization."""
        if self.url and not self.domain:
            try:
                parsed = urlparse(self.url)
                self.domain = parsed.netloc.lower()
            except Exception:
                self.domain = ""


# ============================================================================
# Credible Domain Lists
# ============================================================================

# Task 2.3.5: Define credible domain lists

# Tier 1: Official and government sources
TIER_1_DOMAINS = {
    # Government
    ".gov",
    ".gov.uk",
    ".gov.au",
    ".gov.cn",
    "sec.gov",
    "treasury.gov",
    "federalreserve.gov",
    "europa.eu",
    "un.org",
    # Wire services
    "reuters.com",
    "apnews.com",
    "afp.com",
    # Major reference
    "wikipedia.org",
}

# Tier 2: Major news outlets
TIER_2_DOMAINS = {
    # News
    "bbc.com",
    "bbc.co.uk",
    "cnn.com",
    "nytimes.com",
    "washingtonpost.com",
    "wsj.com",
    "ft.com",
    "theguardian.com",
    "economist.com",
    # Financial news
    "bloomberg.com",
    "cnbc.com",
    "marketwatch.com",
    # Tech news
    "techcrunch.com",
    "wired.com",
    "theverge.com",
}

# Tier 3: Industry-specific and crypto
TIER_3_DOMAINS = {
    # Crypto
    "coindesk.com",
    "cointelegraph.com",
    "theblock.co",
    "decrypt.co",
    "bitcoinmagazine.com",
    # Financial data
    "coingecko.com",
    "coinmarketcap.com",
    "tradingview.com",
    # Finance
    "investopedia.com",
    "forbes.com",
    "fortune.com",
    "seekingalpha.com",
    "yahoo.com",
}

# Tier 4: Social and user-generated
TIER_4_DOMAINS = {
    "twitter.com",
    "x.com",
    "reddit.com",
    "medium.com",
    "substack.com",
    "discord.com",
    "telegram.org",
}


class WebsiteTracker(BaseModel):
    """
    Tracks all websites visited during research.

    Task 2.3.3-2.3.7: Implement WebsiteTracker class.
    """

    agent_id: str = Field(..., description="ID of the tracking agent")
    visits: list[WebsiteVisit] = Field(default_factory=list, description="List of website visits")

    def add_visit(
        self,
        url: str,
        title: str = "",
        content_snippet: str = "",
        relevance_score: float = 0.5,
        facts_extracted: list[str] | None = None,
    ) -> WebsiteVisit:
        """
        Record a new website visit.

        Args:
            url: URL visited
            title: Page title
            content_snippet: Relevant excerpt
            relevance_score: Relevance to research question
            facts_extracted: Facts found on this page

        Returns:
            The created WebsiteVisit record
        """
        # Extract domain
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
        except Exception:
            domain = ""

        # Calculate credibility
        credibility_score = self._calculate_credibility(domain)
        credibility_tier = self._get_credibility_tier(credibility_score)
        source_type = self._categorize_source(domain)

        visit = WebsiteVisit(
            url=url,
            title=title,
            content_snippet=content_snippet,
            domain=domain,
            source_type=source_type,
            credibility_tier=credibility_tier,
            credibility_score=credibility_score,
            relevance_score=relevance_score,
            agent_id=self.agent_id,
            facts_extracted=facts_extracted or [],
        )

        self.visits.append(visit)

        logger.debug(
            "Recorded website visit",
            agent_id=self.agent_id,
            domain=domain,
            credibility=credibility_score,
            source_type=source_type.value,
        )

        return visit

    def _calculate_credibility(self, domain: str) -> float:
        """
        Calculate credibility score for a domain.

        Task 2.3.4: Implement _calculate_credibility() method.

        Args:
            domain: Domain name to evaluate

        Returns:
            Credibility score from 0.0 to 1.0
        """
        if not domain:
            return 0.3

        domain_lower = domain.lower()

        # Check Tier 1 (0.9-1.0)
        for pattern in TIER_1_DOMAINS:
            if pattern in domain_lower or domain_lower.endswith(pattern):
                return 0.95

        # Check Tier 2 (0.75-0.89)
        for pattern in TIER_2_DOMAINS:
            if pattern in domain_lower:
                return 0.82

        # Check Tier 3 (0.6-0.74)
        for pattern in TIER_3_DOMAINS:
            if pattern in domain_lower:
                return 0.67

        # Check Tier 4 (0.4-0.59)
        for pattern in TIER_4_DOMAINS:
            if pattern in domain_lower:
                return 0.45

        # Unknown sources (Tier 5)
        # Apply some heuristics
        if ".edu" in domain_lower or ".ac." in domain_lower:
            return 0.75  # Academic sources
        if ".org" in domain_lower:
            return 0.55  # Non-profits

        return 0.35  # Default for unknown

    def _get_credibility_tier(self, score: float) -> CredibilityTier:
        """Get credibility tier from score."""
        if score >= 0.9:
            return CredibilityTier.TIER_1
        elif score >= 0.7:
            return CredibilityTier.TIER_2
        elif score >= 0.5:
            return CredibilityTier.TIER_3
        elif score >= 0.3:
            return CredibilityTier.TIER_4
        else:
            return CredibilityTier.TIER_5

    def _categorize_source(self, domain: str) -> SourceType:
        """
        Categorize a source by its domain.

        Task 2.3.6: Implement _categorize_source() method.
        """
        if not domain:
            return SourceType.UNKNOWN

        domain_lower = domain.lower()

        # Official
        if any(x in domain_lower for x in [".gov", "sec.", "federal", "treasury"]):
            return SourceType.OFFICIAL

        # Wire services
        if any(x in domain_lower for x in ["reuters", "apnews", "afp"]):
            return SourceType.WIRE_SERVICE

        # Major news
        if any(
            x in domain_lower
            for x in [
                "bbc",
                "cnn",
                "nytimes",
                "wsj",
                "bloomberg",
                "theguardian",
                "ft.com",
                "washingtonpost",
            ]
        ):
            return SourceType.MAJOR_NEWS

        # Financial
        if any(x in domain_lower for x in ["tradingview", "yahoo", "marketwatch", "seekingalpha"]):
            return SourceType.FINANCIAL

        # Crypto
        if any(
            x in domain_lower
            for x in [
                "coindesk",
                "cointelegraph",
                "coingecko",
                "coinmarketcap",
                "theblock",
                "decrypt",
                "bitcoin",
            ]
        ):
            return SourceType.CRYPTO

        # Social
        if any(x in domain_lower for x in ["twitter", "x.com", "reddit", "discord", "telegram"]):
            return SourceType.SOCIAL

        # Academic
        if any(x in domain_lower for x in [".edu", ".ac.", "arxiv", "scholar"]):
            return SourceType.ACADEMIC

        # Blog platforms
        if any(x in domain_lower for x in ["medium", "substack", "blog"]):
            return SourceType.BLOG

        return SourceType.UNKNOWN

    def get_top_sources(
        self,
        limit: int = 10,
        min_credibility: float = 0.5,
    ) -> list[WebsiteVisit]:
        """
        Get top sources by credibility and relevance.

        Task 2.3.7: Implement get_top_sources() method.

        Args:
            limit: Maximum number of sources to return
            min_credibility: Minimum credibility score

        Returns:
            List of top WebsiteVisit records
        """
        # Filter by minimum credibility
        filtered = [v for v in self.visits if v.credibility_score >= min_credibility]

        # Sort by combined score (credibility * relevance)
        sorted_visits = sorted(
            filtered,
            key=lambda v: v.credibility_score * v.relevance_score,
            reverse=True,
        )

        return sorted_visits[:limit]

    def get_by_tier(self, tier: CredibilityTier) -> list[WebsiteVisit]:
        """Get all visits for a specific credibility tier."""
        return [v for v in self.visits if v.credibility_tier == tier]

    def get_by_source_type(self, source_type: SourceType) -> list[WebsiteVisit]:
        """Get all visits for a specific source type."""
        return [v for v in self.visits if v.source_type == source_type]

    def get_statistics(self) -> dict:
        """Get statistics about visited sources."""
        if not self.visits:
            return {
                "total_visits": 0,
                "unique_domains": 0,
                "avg_credibility": 0.0,
                "tier_distribution": {},
                "type_distribution": {},
            }

        # Unique domains
        domains = {v.domain for v in self.visits if v.domain}

        # Average credibility
        avg_cred = sum(v.credibility_score for v in self.visits) / len(self.visits)

        # Tier distribution
        tier_dist: dict[str, int] = {}
        for v in self.visits:
            tier = v.credibility_tier.value
            tier_dist[tier] = tier_dist.get(tier, 0) + 1

        # Type distribution
        type_dist: dict[str, int] = {}
        for v in self.visits:
            st = v.source_type.value
            type_dist[st] = type_dist.get(st, 0) + 1

        return {
            "total_visits": len(self.visits),
            "unique_domains": len(domains),
            "avg_credibility": round(avg_cred, 3),
            "tier_distribution": tier_dist,
            "type_distribution": type_dist,
            "top_domains": list(domains)[:10],
        }

    def to_dict(self) -> dict:
        """Serialize tracker to dictionary."""
        return {
            "agent_id": self.agent_id,
            "visits": [v.model_dump() for v in self.visits],
            "statistics": self.get_statistics(),
        }
